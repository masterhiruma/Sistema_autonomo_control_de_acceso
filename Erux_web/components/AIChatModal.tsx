
import React, { useState, useRef, useEffect } from 'react';
import { GoogleGenAI, Chat } from '@google/genai';
import { XMarkIcon } from './icons/XMarkIcon';
import { PaperAirplaneIcon } from './icons/PaperAirplaneIcon';
import { QuestionMarkCircleIcon } from './icons/QuestionMarkCircleIcon';
import { ChatMessage, AIAction, RegisteredUser, AccessEvent } from '../types';
import { ArrowUpRightIcon } from './icons/ArrowUpRightIcon';
import { ClockIcon } from './icons/ClockIcon';
import { KeyIcon } from './icons/KeyIcon';

interface AIChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAction: (action: AIAction) => void;
  users: RegisteredUser[];
  accessLog: AccessEvent[];
}

const getSystemInstruction = (users: RegisteredUser[], accessLog: AccessEvent[]): string => {
    const today = new Date().toLocaleDateString('es-ES');
    return `Eres un asistente de IA experto para un sistema de control de acceso avanzado. Tu nombre es 'Centinela'.
Tu propósito es ayudar a los operadores a usar el sistema de manera eficiente, segura, y a analizar datos de acceso.
La fecha de hoy es ${today}.

**CONTEXTO DEL SISTEMA:**
- Lista de Usuarios Registrados: ${JSON.stringify(users.map(u => ({id: u.id, name: u.name, schedule: u.schedule})))}
- Últimos 50 Registros de Acceso: ${JSON.stringify(accessLog.slice(0, 50).map(e => ({name: e.name, date: e.date, time: e.time, status: e.status})))}

**REGLAS DE RESPUESTA:**
1.  **Tono Profesional:** Sé servicial, conciso y prioriza la seguridad.
2.  **Análisis de Datos:** Puedes responder preguntas sobre los datos de acceso. Usa el contexto provisto.
    -   Para contar, filtra los datos y da un número.
    -   Para saber quién llegó tarde, compara la hora del evento con el horario del usuario.
    -   Para preguntas sobre fechas, como "ayer" o "la semana pasada", calcula las fechas correspondientes a partir de hoy.
    -   Ejemplos: "¿Cuánta gente entró hoy?", "¿Quién llegó tarde ayer?", "Muéstrame los accesos de Ana Torres".
3.  **Acciones:** Si el usuario quiere realizar una acción, responde **ÚNICAMENTE con un bloque de código JSON Markdown**.
    -   La estructura del JSON debe ser: \`{ "response": "Texto para el usuario.", "action": { "type": "TIPO_DE_ACCION", "payload": { ... } } }\`

**TIPOS DE ACCIÓN VÁLIDOS:**

a) **Navegación:** Para llevar al usuario a una pantalla.
   -   El campo 'type' es "navigate".
   -   El campo 'payload' es una de las siguientes claves: 'open_user_management', 'open_reports', 'open_settings'.
   -   **Ejemplo:** Pregunta: "¿Cómo añado un usuario?" -> Respuesta JSON:
       \`\`\`json
       {
         "response": "Claro, te llevo a la pantalla de gestión de usuarios. Recuerda que necesitas contraseña de administrador.",
         "action": { "type": "navigate", "payload": "open_user_management" }
       }
       \`\`\`

b) **Programar Reporte:** Para automatizar el envío de reportes. Extrae el email, la hora y el formato del mensaje del usuario. Si faltan datos, usa valores por defecto (ej: 8:00, PDF).
   -   El campo 'type' es "schedule_report".
   -   El campo 'payload' es un JSON con: \`{ "email": "correo@ejemplo.com", "time": "HH:MM", "format": "pdf" }\`.
   -   **Ejemplo:** Pregunta: "Manda los reportes a gerencia@miempresa.com a las 8" -> Respuesta JSON:
       \`\`\`json
       {
         "response": "Entendido. He preparado la programación del reporte para 'gerencia@miempresa.com' a las 08:00 en formato PDF. Por favor, confirma la acción.",
         "action": { "type": "schedule_report", "payload": { "email": "gerencia@miempresa.com", "time": "08:00", "format": "pdf" } }
       }
       \`\`\`

4.  **Si NO hay acción:** Responde en texto plano. No uses JSON.
    -   Ejemplo: "¿Cuál es el propósito del botón de emergencia?" -> Respuesta: "El botón de emergencia activa una alerta inmediata, registra el evento y comienza a grabar video para asegurar la evidencia."
`;
}


const getActionInfo = (action: AIAction): { label: string; icon: React.ReactNode } => {
    switch (action.type) {
        case 'navigate':
            switch (action.payload) {
                case 'open_user_management': return { label: 'Ir a Gestión de Usuarios', icon: <ArrowUpRightIcon className="h-4 w-4" /> };
                case 'open_reports': return { label: 'Abrir Reportes', icon: <ArrowUpRightIcon className="h-4 w-4" /> };
                case 'open_settings': return { label: 'Abrir Configuración', icon: <ArrowUpRightIcon className="h-4 w-4" /> };
            }
        case 'schedule_report':
            return { label: 'Confirmar Programación', icon: <ClockIcon className="h-4 w-4" /> };
        default:
            return { label: 'Realizar Acción', icon: <ArrowUpRightIcon className="h-4 w-4" /> };
    }
}


const AIChatModal: React.FC<AIChatModalProps> = ({ isOpen, onClose, onAction, users, accessLog }) => {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [apiKey, setApiKey] = useState('');
    const [isKeySubmitted, setIsKeySubmitted] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const chatRef = useRef<Chat | null>(null);

    useEffect(() => {
        if (isOpen && isKeySubmitted) {
            if (!apiKey) return;
            
            const ai = new GoogleGenAI({ apiKey });
            chatRef.current = ai.chats.create({
                model: 'gemini-2.5-flash-preview-04-17',
                config: {
                    systemInstruction: getSystemInstruction(users, accessLog),
                }
            });
             if (messages.length === 0) {
                setMessages([
                    { id: Date.now(), text: 'Hola, soy Centinela. Puedes hacerme preguntas sobre la actividad o pedirme que realice acciones.', sender: 'ai' }
                ]);
            }
        }
    }, [isOpen, isKeySubmitted, apiKey, users, accessLog]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleKeySubmit = () => {
        if (apiKey.trim()) {
            setIsKeySubmitted(true);
        }
    }
    
    const handleSend = async () => {
        if (!input.trim() || isLoading) return;

        const userMessage: ChatMessage = { id: Date.now(), text: input, sender: 'user' };
        setMessages(prev => [...prev, userMessage]);
        const currentInput = input;
        setInput('');
        setIsLoading(true);

        if (!chatRef.current) {
            const aiResponse: ChatMessage = { id: Date.now() + 1, text: "Error: El chat no está inicializado. Verifique la clave de API.", sender: 'ai' };
            setMessages(prev => [...prev, aiResponse]);
            setIsLoading(false);
            return;
        }

        try {
            const stream = await chatRef.current.sendMessageStream({ message: currentInput });
            let aiResponseText = '';
            const aiMessageId = Date.now() + 1;
            
            setMessages(prev => [...prev, { id: aiMessageId, text: '', sender: 'ai' }]);
            
            for await (const chunk of stream) {
                aiResponseText += chunk.text;
                setMessages(prev => prev.map(msg => 
                    msg.id === aiMessageId ? { ...msg, text: aiResponseText } : msg
                ));
            }
            
            const fenceRegex = /^```json\s*\n?(.*?)\n?\s*```$/s;
            const match = aiResponseText.match(fenceRegex);

            if (match && match[1]) {
                try {
                    const parsed = JSON.parse(match[1]);
                    if (parsed.response && parsed.action && parsed.action.type) {
                         setMessages(prev => prev.map(msg => 
                            msg.id === aiMessageId 
                                ? { ...msg, text: parsed.response, action: parsed.action } 
                                : msg
                        ));
                    }
                } catch(e) {
                    console.error("Failed to parse AI action JSON:", e, "\nReceived text:", aiResponseText);
                     setMessages(prev => prev.map(msg => 
                        msg.id === aiMessageId ? { ...msg, text: aiResponseText } : msg
                    ));
                }
            }

        } catch (error) {
            console.error("Error calling Gemini API:", error);
            const errorResponse: ChatMessage = { id: Date.now() + 1, text: "Lo siento, he encontrado un error al procesar tu solicitud.", sender: 'ai' };
            setMessages(prev => [...prev, errorResponse]);
        } finally {
            setIsLoading(false);
        }
    };
    
    if (!isOpen) return null;

    const renderApiKeyPrompt = () => (
        <div className="flex flex-col items-center justify-center h-full p-6 text-center">
            <KeyIcon className="h-12 w-12 text-cyan-400 mb-4" />
            <h3 className="text-lg font-bold text-white mb-2">Se necesita una Clave de API</h3>
            <p className="text-sm text-gray-400 mb-4">
                Para usar el asistente de IA, por favor ingresa tu clave de API de Google Gemini.
                Esta clave se usará solo para esta sesión.
            </p>
            <div className="w-full space-y-3">
                <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleKeySubmit()}
                    placeholder="Ingresa tu Clave de API de Gemini"
                    className="w-full bg-gray-900 border border-gray-600 text-white rounded-md p-2 text-center"
                />
                <button 
                    onClick={handleKeySubmit}
                    disabled={!apiKey.trim()}
                    className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-bold py-2 px-4 rounded-lg transition-colors disabled:bg-gray-600 disabled:cursor-not-allowed">
                    Guardar y Continuar
                </button>
            </div>
             <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener noreferrer" className="text-xs text-cyan-500 hover:underline mt-4">
                Obtener una clave de API de Google AI Studio
            </a>
        </div>
    );

    const renderChat = () => (
         <>
            {/* Messages */}
            <div className="flex-grow p-4 overflow-y-auto space-y-2">
                {messages.map(msg => {
                    const actionInfo = msg.action ? getActionInfo(msg.action) : null;
                    return (
                        <div key={msg.id} className={`flex flex-col gap-1 ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}>
                            <div className={`flex gap-3 w-full items-start ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                                {msg.sender === 'ai' && <div className="w-8 h-8 rounded-full bg-cyan-500/20 flex items-center justify-center flex-shrink-0 text-cyan-300 font-bold">C</div>}
                                <div className={`max-w-[85%] p-3 rounded-lg ${msg.sender === 'user' ? 'bg-cyan-600 text-white' : 'bg-gray-700 text-gray-200'}`}>
                                    <p className="text-sm" style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</p>
                                </div>
                            </div>
                            {msg.action && actionInfo && (
                                <button
                                    onClick={() => onAction(msg.action!)}
                                    className="ml-11 mt-1 bg-gray-700 hover:bg-gray-600 border border-gray-600/50 text-cyan-300 text-sm font-semibold py-1.5 px-3 rounded-lg flex items-center gap-1.5 transition-colors">
                                    {actionInfo.icon}
                                    {actionInfo.label}
                                </button>
                            )}
                        </div>
                    )
                })}
                {isLoading && (messages.length === 0 || messages[messages.length - 1]?.sender === 'user') && (
                     <div className="flex gap-3 items-start">
                         <div className="w-8 h-8 rounded-full bg-cyan-500/20 flex items-center justify-center flex-shrink-0 text-cyan-300 font-bold">C</div>
                        <div className="max-w-[80%] p-3 rounded-lg bg-gray-700 text-gray-200">
                            <div className="flex items-center gap-2">
                                <div className="h-2 w-2 bg-cyan-400 rounded-full animate-pulse [animation-delay:-0.3s]"></div>
                                <div className="h-2 w-2 bg-cyan-400 rounded-full animate-pulse [animation-delay:-0.15s]"></div>
                                <div className="h-2 w-2 bg-cyan-400 rounded-full animate-pulse"></div>
                            </div>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>
            {/* Input */}
            <div className="p-4 border-t border-gray-700 flex-shrink-0">
                <div className="flex items-center gap-2 bg-gray-900 rounded-lg border border-gray-600 focus-within:border-cyan-500 transition-colors">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                        placeholder="Escribe tu pregunta o comando..."
                        className="flex-grow bg-transparent p-3 text-white placeholder-gray-500 focus:outline-none"
                        disabled={isLoading}
                    />
                    <button onClick={handleSend} disabled={!input.trim() || isLoading} className="p-3 text-gray-400 hover:text-white disabled:text-gray-600 disabled:cursor-not-allowed transition-colors">
                        <PaperAirplaneIcon className="h-6 w-6" />
                    </button>
                </div>
            </div>
        </>
    );

    return (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-end justify-end z-50 p-0 md:p-8" onClick={onClose}>
            <div
                className="bg-gray-800 w-full h-full md:w-[440px] md:h-[70vh] rounded-none md:rounded-2xl shadow-2xl border-t-2 md:border border-gray-700 flex flex-col transform transition-transform duration-300 ease-in-out"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-gray-700 flex-shrink-0">
                    <h2 className="text-lg font-bold text-white flex items-center gap-2">
                        <QuestionMarkCircleIcon className="h-6 w-6 text-cyan-400" />
                        Asistente Centinela (IA)
                    </h2>
                    <button onClick={onClose} className="p-1 rounded-full hover:bg-gray-700 transition-colors">
                        <XMarkIcon className="h-6 w-6 text-gray-400" />
                    </button>
                </div>
                
                {isKeySubmitted ? renderChat() : renderApiKeyPrompt()}

            </div>
        </div>
    );
};

export default AIChatModal;

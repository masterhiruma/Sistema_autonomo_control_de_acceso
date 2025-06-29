
import React, { useState, useEffect } from 'react';
import { XMarkIcon } from './icons/XMarkIcon';
import { KeyIcon } from './icons/KeyIcon';

interface PasswordPromptModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  title: string;
}

const PasswordPromptModal: React.FC<PasswordPromptModalProps> = ({ isOpen, onClose, onSuccess, title }) => {
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    
    useEffect(() => {
        if (isOpen) {
             setTimeout(() => {
                const input = document.getElementById('password-input');
                input?.focus();
            }, 100);
        } else {
            // Reset state after closing animation
            const timer = setTimeout(() => {
                setPassword('');
                setError('');
            }, 200);
            return () => clearTimeout(timer);
        }
    }, [isOpen]);

    const handleConfirm = () => {
        // In a real application, this should be a secure check against a hashed password.
        if (password === '123456') {
            setError('');
            onSuccess();
        } else {
            setError('Contraseña incorrecta. Intente de nuevo.');
            setPassword('');
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter') {
            handleConfirm();
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
            <div className="bg-gray-800 w-full max-w-md rounded-2xl shadow-2xl border border-gray-700 transform transition-all" onClick={e => e.stopPropagation()}>
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-gray-700">
                    <h2 className="text-xl font-bold text-white flex items-center gap-2">
                        <KeyIcon className="h-6 w-6 text-cyan-400" />
                        {title || 'Acceso Protegido'}
                    </h2>
                    <button onClick={onClose} className="p-1 rounded-full hover:bg-gray-700 transition-colors">
                        <XMarkIcon className="h-6 w-6 text-gray-400" />
                    </button>
                </div>

                {/* Body */}
                <div className="p-6 space-y-4">
                    <label htmlFor="password-input" className="block text-sm font-medium text-gray-300">
                        Por favor, ingrese la contraseña para continuar.
                    </label>
                    <input
                        id="password-input"
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        onKeyPress={handleKeyPress}
                        className="bg-gray-900 border border-gray-600 text-white text-lg rounded-lg focus:ring-cyan-500 focus:border-cyan-500 block w-full p-2.5 font-mono tracking-widest text-center"
                    />
                    {error && (
                        <p className="text-sm text-red-400 text-center">{error}</p>
                    )}
                </div>

                {/* Footer */}
                <div className="bg-gray-800/50 p-4 border-t border-gray-700/60 rounded-b-2xl flex justify-end gap-3">
                    <button onClick={onClose} className="px-4 py-2 text-sm font-medium text-gray-300 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">
                        Cancelar
                    </button>
                    <button onClick={handleConfirm} className="px-4 py-2 text-sm font-medium text-white bg-cyan-600 hover:bg-cyan-500 rounded-lg transition-colors">
                        Confirmar
                    </button>
                </div>
            </div>
        </div>
    );
};

export default PasswordPromptModal;

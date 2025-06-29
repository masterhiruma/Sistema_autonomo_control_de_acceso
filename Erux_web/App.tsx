
import React, { useState, useEffect, useCallback } from 'react';
import { AccessEvent, AccessStatus, RegisteredUser, EmergencyEvent, AIAction } from './types';
import { useCurrentTime } from './hooks/useCurrentTime';
import Header from './components/Header';
import CameraFeed from './components/CameraFeed';
import InfoPanel from './components/InfoPanel';
import ControlPanel from './components/ControlPanel';
import AccessLog from './components/AccessLog';
import SettingsModal from './components/SettingsModal';
import PasswordPromptModal from './components/PasswordPromptModal';
import UserManagementModal from './components/UserManagementModal';
import ReportsModal from './components/ReportsModal';
import HelpButton from './components/HelpButton';
import AIChatModal from './components/AIChatModal';


const MOCK_NAMES = ["Ana Torres", "Carlos Gomez", "Sofia Rossi", "Luis Fernandez", "Usuario Desconocido"];
const MOCK_USERS: RegisteredUser[] = [
  { id: '1', name: 'Ana Torres', dni: '12345678A', userLevel: 'Administrador', uid: 'A1B2C3D4', schedule: 'Acceso Total', avatar: 'https://i.pravatar.cc/40?u=AnaTorres' },
  { id: '2', name: 'Carlos Gomez', dni: '87654321B', userLevel: 'Usuario', uid: 'B2C3D4E5', schedule: 'Diurno (8:00-18:00)', avatar: 'https://i.pravatar.cc/40?u=CarlosGomez' },
  { id: '3', name: 'Sofia Rossi', dni: '11223344C', userLevel: 'Usuario', uid: 'C3D4E5F6', schedule: 'Diurno (8:00-18:00)', avatar: 'https://i.pravatar.cc/40?u=SofiaRossi' },
  { id: '4', name: 'Luis Fernandez', dni: '55667788D', userLevel: 'Visitante', uid: 'D4E5F6G7', schedule: 'Temporal', avatar: 'https://i.pravatar.cc/40?u=LuisFernandez' },
];


const App: React.FC = () => {
  const [accessLog, setAccessLog] = useState<AccessEvent[]>([]);
  const [detectedUser, setDetectedUser] = useState<string>('Detectando...');
  const [users, setUsers] = useState<RegisteredUser[]>(MOCK_USERS);
  const [emergencyEvents, setEmergencyEvents] = useState<EmergencyEvent[]>([]);
  
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isUserManagementOpen, setIsUserManagementOpen] = useState(false);
  const [isReportsOpen, setIsReportsOpen] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);
  
  const [isPasswordPromptOpen, setIsPasswordPromptOpen] = useState(false);
  const [passwordTarget, setPasswordTarget] = useState<'settings' | 'users' | 'reports' | 'manualAccess' | null>(null);
  const [passwordPromptTitle, setPasswordPromptTitle] = useState('');


  const { time, date } = useCurrentTime();

  const generateMockEvent = useCallback(() => {
    const randomName = MOCK_NAMES[Math.floor(Math.random() * MOCK_NAMES.length)];
    const status = randomName === 'Usuario Desconocido' ? AccessStatus.DENIED : AccessStatus.GRANTED;
    
    // Create late arrivals for Carlos Gomez sometimes
    const isLateAttempt = randomName === 'Carlos Gomez' && Math.random() > 0.7;
    const eventHour = isLateAttempt ? 19 : new Date().getHours();
    const eventTime = new Date();
    eventTime.setHours(eventHour);

    const newEvent: AccessEvent = {
      id: Date.now() + Math.random(),
      name: randomName,
      time: eventTime.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      date: new Date().toLocaleDateString('es-ES'),
      status: status,
      avatar: `https://i.pravatar.cc/40?u=${randomName.replace(' ','')}`
    };

    setDetectedUser(randomName);
    setAccessLog(prevLog => [newEvent, ...prevLog.slice(0, 49)]);
    
    setTimeout(() => {
        setDetectedUser('Detectando...');
    }, 2500);

  }, []);

  useEffect(() => {
    generateMockEvent();
    const intervalId = setInterval(generateMockEvent, 8000);
    return () => clearInterval(intervalId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  
  const handleOpenSettings = () => {
    setPasswordTarget('settings');
    setPasswordPromptTitle('Acceso a Configuración');
    setIsPasswordPromptOpen(true);
  };

  const handleOpenUserManagement = () => {
    setPasswordTarget('users');
    setPasswordPromptTitle('Acceso a Gestión de Usuarios');
    setIsPasswordPromptOpen(true);
  };

  const handleOpenReports = () => {
    setPasswordTarget('reports');
    setPasswordPromptTitle('Acceso a Reportes');
    setIsPasswordPromptOpen(true);
  };

  const handleOpenManualAccess = () => {
    setPasswordTarget('manualAccess');
    setPasswordPromptTitle('Acceso Manual');
    setIsPasswordPromptOpen(true);
  };
  
  const handleEmergency = () => {
    const newEmergency: EmergencyEvent = {
        id: Date.now(),
        timestamp: new Date(),
        videoUrl: `/videos/emergency_${Date.now()}.mp4`
    };
    setEmergencyEvents(prev => [newEmergency, ...prev]);
    // Optionally, open reports to show the event was logged
    alert('¡Emergencia declarada! Evento registrado y grabación iniciada.');
  };

  const handlePasswordSuccess = () => {
    setIsPasswordPromptOpen(false);
    if (passwordTarget === 'settings') {
      setIsSettingsOpen(true);
    } else if (passwordTarget === 'users') {
      setIsUserManagementOpen(true);
    } else if (passwordTarget === 'reports') {
      setIsReportsOpen(true);
    } else if (passwordTarget === 'manualAccess') {
      alert('Acceso manual concedido.');
    }
    setPasswordTarget(null);
  };

  const handleClosePasswordPrompt = () => {
    setIsPasswordPromptOpen(false);
    setPasswordTarget(null);
  };
  
  const handleAiAction = (action: AIAction) => {
    setIsChatOpen(false); // Close chat to show the result
    
    // Wait a bit for the modal to close before acting
    setTimeout(() => {
        switch (action.type) {
            case 'navigate':
                switch (action.payload) {
                    case 'open_user_management':
                        handleOpenUserManagement();
                        break;
                    case 'open_reports':
                        handleOpenReports();
                        break;
                    case 'open_settings':
                        handleOpenSettings();
                        break;
                }
                break;
            case 'schedule_report':
                 alert(`¡Reporte programado!\n\nSe enviará un reporte en formato ${action.payload.format.toUpperCase()} a '${action.payload.email}' todos los días a las ${action.payload.time}.`);
                 console.log("AI scheduled report:", action.payload);
                 break;
            default:
                console.warn('Unknown AI action:', action);
        }
    }, 300);
  };

  return (
    <div className="min-h-screen bg-gray-900 flex flex-col font-sans">
      <Header onOpenSettings={handleOpenSettings} />
      <main className="flex-grow flex flex-col md:flex-row gap-8 p-4 md:p-8">
        {/* Left Column */}
        <div className="w-full md:w-2/3 lg:w-3/5 flex flex-col gap-8">
          <CameraFeed />
          <InfoPanel name={detectedUser} time={time} date={date} />
          <ControlPanel 
            onOpenManualAccess={handleOpenManualAccess}
            onOpenUserManagement={handleOpenUserManagement}
            onOpenReports={handleOpenReports}
            onEmergency={handleEmergency}
          />
        </div>

        {/* Right Column */}
        <div className="w-full md:w-1/3 lg:w-2/5">
          <AccessLog events={accessLog} />
        </div>
      </main>
      
      <PasswordPromptModal
        isOpen={isPasswordPromptOpen}
        onClose={handleClosePasswordPrompt}
        onSuccess={handlePasswordSuccess}
        title={passwordPromptTitle}
      />
      <SettingsModal 
        isOpen={isSettingsOpen} 
        onClose={() => setIsSettingsOpen(false)} 
      />
       <UserManagementModal
        isOpen={isUserManagementOpen}
        onClose={() => setIsUserManagementOpen(false)}
        users={users}
        setUsers={setUsers}
      />
       <ReportsModal
        isOpen={isReportsOpen}
        onClose={() => setIsReportsOpen(false)}
        accessLog={accessLog}
        users={users}
        emergencyEvents={emergencyEvents}
      />
      <AIChatModal 
        isOpen={isChatOpen}
        onClose={() => setIsChatOpen(false)}
        onAction={handleAiAction}
        users={users}
        accessLog={accessLog}
      />

      <HelpButton onClick={() => setIsChatOpen(true)} />
    </div>
  );
};

export default App;

import React, { useState, useMemo } from 'react';
import { AccessEvent, RegisteredUser, EmergencyEvent, AccessStatus } from '../types';
import { XMarkIcon } from './icons/XMarkIcon';
import { ChartBarIcon } from './icons/ChartBarIcon';
import { DocumentArrowDownIcon } from './icons/DocumentArrowDownIcon';
import { ClockIcon } from './icons/ClockIcon';
import ReportAutomationModal from './ReportAutomationModal';
import { ExclamationTriangleIcon } from './icons/ExclamationTriangleIcon';

// --- Helper Functions & Components ---

// Simple Doughnut Chart Component
const DoughnutChart: React.FC<{ granted: number; denied: number }> = ({ granted, denied }) => {
    const total = granted + denied;
    if (total === 0) return <p className="text-gray-400">No hay datos para el gráfico.</p>;
    
    const grantedPercent = (granted / total) * 100;
    const deniedPercent = (denied / total) * 100;
    const circumference = 2 * Math.PI * 40; // 2 * pi * r
    const grantedStroke = (grantedPercent / 100) * circumference;
    const deniedStroke = (deniedPercent / 100) * circumference;

    return (
        <div className="relative w-48 h-48 flex items-center justify-center">
            <svg className="w-full h-full" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="40" fill="transparent" stroke="#4b5563" strokeWidth="10" />
                <circle
                    cx="50"
                    cy="50"
                    r="40"
                    fill="transparent"
                    stroke="#2dd4bf"
                    strokeWidth="10"
                    strokeDasharray={`${grantedStroke} ${circumference}`}
                    transform="rotate(-90 50 50)"
                />
                 <circle
                    cx="50"
                    cy="50"
                    r="40"
                    fill="transparent"
                    stroke="#f87171"
                    strokeWidth="10"
                    strokeDasharray={`${deniedStroke} ${circumference}`}
                    transform={`rotate(${-90 + grantedPercent * 3.6} 50 50)`}
                />
            </svg>
            <div className="absolute text-center">
                <p className="text-2xl font-bold text-white">{total}</p>
                <p className="text-sm text-gray-400">Accesos</p>
            </div>
        </div>
    );
};

// Simple Bar Chart Component
const BarChart: React.FC<{ data: { label: string, value: number }[] }> = ({ data }) => {
    const maxValue = Math.max(...data.map(d => d.value), 1);
    return (
        <div className="w-full h-48 flex items-end justify-around gap-2 p-2 bg-gray-900/50 rounded-md">
            {data.map(item => (
                <div key={item.label} className="flex-1 flex flex-col items-center justify-end gap-1">
                    <div 
                        className="w-full bg-cyan-500 rounded-t-sm"
                        style={{ height: `${(item.value / maxValue) * 100}%` }}
                        title={`${item.value} accesos`}
                    />
                    <span className="text-xs text-gray-400">{item.label}</span>
                </div>
            ))}
        </div>
    );
};

// Check if an access event is a late arrival
const isLate = (event: AccessEvent, user: RegisteredUser | undefined): boolean => {
    if (!user || user.schedule === 'Acceso Total' || user.schedule === 'Temporal') {
        return false;
    }
    const scheduleMatch = user.schedule.match(/(\d{1,2}):\d{2}-(\d{1,2}):\d{2}/);
    if (!scheduleMatch) return false;

    const startHour = parseInt(scheduleMatch[1], 10);
    const endHour = parseInt(scheduleMatch[2], 10);
    const eventHour = parseInt(event.time.split(':')[0], 10);

    return eventHour < startHour || eventHour >= endHour;
};


// --- Main Component ---

interface ReportsModalProps {
  isOpen: boolean;
  onClose: () => void;
  accessLog: AccessEvent[];
  users: RegisteredUser[];
  emergencyEvents: EmergencyEvent[];
}

type ActiveTab = 'all' | 'late' | 'emergency';

const ReportsModal: React.FC<ReportsModalProps> = ({ isOpen, onClose, accessLog, users, emergencyEvents }) => {
    const [activeTab, setActiveTab] = useState<ActiveTab>('all');
    const [isAutomationModalOpen, setIsAutomationModalOpen] = useState(false);

    const analytics = useMemo(() => {
        const granted = accessLog.filter(e => e.status === AccessStatus.GRANTED).length;
        const denied = accessLog.filter(e => e.status === AccessStatus.DENIED).length;
        
        const hourlyData = Array(24).fill(0).map((_, i) => ({ label: `${i.toString().padStart(2, '0')}`, value: 0 }));
        accessLog.forEach(e => {
            const hour = parseInt(e.time.split(':')[0], 10);
            if(hourlyData[hour]) hourlyData[hour].value++;
        });

        const lateArrivals = accessLog.filter(event => {
            const user = users.find(u => u.name === event.name);
            return isLate(event, user);
        });

        return { granted, denied, hourlyData, lateArrivals };
    }, [accessLog, users]);
    
    const handleGenerateReport = () => {
        const reportData = {
            summary: {
                totalAccesses: accessLog.length,
                granted: analytics.granted,
                denied: analytics.denied,
                lateArrivals: analytics.lateArrivals.length,
                emergencyEvents: emergencyEvents.length,
                generatedAt: new Date().toISOString()
            },
            accessLog,
            lateArrivals: analytics.lateArrivals,
            emergencyEvents,
        };
        const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `reporte_acceso_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    if (!isOpen) return null;

    const renderLog = () => {
        switch (activeTab) {
            case 'late':
                return analytics.lateArrivals.map(event => <LogItem key={event.id} event={event} />);
            case 'emergency':
                return emergencyEvents.map(event => <EmergencyItem key={event.id} event={event} />);
            case 'all':
            default:
                return accessLog.map(event => <LogItem key={event.id} event={event} />);
        }
    }

  return (
    <>
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-gray-800 w-full max-w-7xl h-[90vh] rounded-2xl shadow-2xl border border-gray-700 flex flex-col" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700 flex-shrink-0">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <ChartBarIcon className="h-6 w-6 text-cyan-400"/>
            Reportes y Analíticas
          </h2>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-gray-700 transition-colors">
            <XMarkIcon className="h-6 w-6 text-gray-400" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-grow flex flex-col lg:flex-row gap-6 p-6 overflow-hidden">
            {/* Left Column: Analytics & Actions */}
            <div className="w-full lg:w-1/3 flex flex-col gap-6">
                <div className="p-4 bg-gray-900/50 rounded-lg border border-gray-700">
                    <h3 className="text-lg font-semibold text-white mb-4">Resumen de Accesos</h3>
                    <div className="flex items-center justify-center gap-4">
                        <DoughnutChart granted={analytics.granted} denied={analytics.denied} />
                        <div className="text-sm space-y-2">
                            <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-cyan-400"></span> Concedidos: {analytics.granted}</div>
                            <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-red-500"></span> Denegados: {analytics.denied}</div>
                        </div>
                    </div>
                </div>
                 <div className="p-4 bg-gray-900/50 rounded-lg border border-gray-700">
                    <h3 className="text-lg font-semibold text-white mb-2">Actividad por Hora</h3>
                    <BarChart data={analytics.hourlyData.slice(6, 23)} />
                </div>
                 <div className="p-4 bg-gray-900/50 rounded-lg border border-gray-700 space-y-3">
                     <h3 className="text-lg font-semibold text-white">Acciones de Reporte</h3>
                      <button onClick={handleGenerateReport} className="w-full flex items-center justify-center gap-2 bg-cyan-600 hover:bg-cyan-500 text-white font-bold py-2 px-4 rounded-lg transition-colors">
                        <DocumentArrowDownIcon className="h-5 w-5"/>
                        Generar Reporte
                      </button>
                       <button onClick={() => setIsAutomationModalOpen(true)} className="w-full flex items-center justify-center gap-2 bg-gray-700 hover:bg-gray-600 text-gray-200 font-bold py-2 px-4 rounded-lg transition-colors">
                        <ClockIcon className="h-5 w-5"/>
                        Automatizar Reporte
                      </button>
                </div>
            </div>

            {/* Right Column: Detailed Logs */}
            <div className="w-full lg:w-2/3 flex flex-col bg-gray-900/50 rounded-lg border border-gray-700">
                <div className="p-2 border-b border-gray-700 flex-shrink-0">
                    <div className="flex gap-2">
                        <TabButton label="Todos los Accesos" count={accessLog.length} isActive={activeTab === 'all'} onClick={() => setActiveTab('all')} />
                        <TabButton label="Llegadas Tarde" count={analytics.lateArrivals.length} isActive={activeTab === 'late'} onClick={() => setActiveTab('late')} />
                        <TabButton label="Emergencias" count={emergencyEvents.length} isActive={activeTab === 'emergency'} onClick={() => setActiveTab('emergency')} />
                    </div>
                </div>
                <div className="flex-grow overflow-y-auto p-3">
                    <ul className="space-y-2">
                       {renderLog()}
                    </ul>
                </div>
            </div>
        </div>
      </div>
    </div>
    <ReportAutomationModal isOpen={isAutomationModalOpen} onClose={() => setIsAutomationModalOpen(false)} />
    </>
  );
};

// --- Sub-Components for Logs ---

const TabButton: React.FC<{ label: string, count: number, isActive: boolean, onClick: () => void }> = ({ label, count, isActive, onClick }) => (
    <button onClick={onClick} className={`px-3 py-1.5 text-sm font-semibold rounded-md transition-colors ${isActive ? 'bg-cyan-500/20 text-cyan-300' : 'text-gray-400 hover:bg-gray-700/70 hover:text-gray-200'}`}>
        {label} <span className="text-xs bg-gray-700/80 px-1.5 py-0.5 rounded-full">{count}</span>
    </button>
);

const LogItem: React.FC<{ event: AccessEvent }> = ({ event }) => {
    const isGranted = event.status === AccessStatus.GRANTED;
    return (
        <li className={`flex items-center gap-4 p-2 rounded-md bg-gray-800 border-l-4 ${isGranted ? 'border-cyan-400' : 'border-red-500'}`}>
            <img src={event.avatar} alt={event.name} className="w-10 h-10 rounded-full object-cover border-2 border-gray-600"/>
            <div className="flex-grow">
                <p className="font-semibold text-white">{event.name}</p>
                <p className="text-xs text-gray-400">{event.time} - {event.date}</p>
            </div>
            <span className={`text-xs font-bold ${isGranted ? 'text-green-400' : 'text-red-400'}`}>{event.status.toUpperCase()}</span>
        </li>
    );
};

const EmergencyItem: React.FC<{ event: EmergencyEvent }> = ({ event }) => (
    <li className="flex items-center gap-4 p-3 rounded-md bg-red-900/50 border-l-4 border-red-500">
        <div className="p-2 bg-red-500/20 rounded-full"><ExclamationTriangleIcon className="h-6 w-6 text-red-400"/></div>
        <div className="flex-grow">
            <p className="font-semibold text-white">Evento de Emergencia Registrado</p>
            <p className="text-xs text-gray-300">{event.timestamp.toLocaleString('es-ES')}</p>
        </div>
        <button className="text-sm font-semibold text-cyan-400 hover:text-cyan-300">Ver Grabación</button>
    </li>
);

export default ReportsModal;

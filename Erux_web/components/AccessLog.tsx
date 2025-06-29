
import React from 'react';
import { AccessEvent, AccessStatus } from '../types';
import { CheckCircleIcon } from './icons/CheckCircleIcon';
import { XCircleIcon } from './icons/XCircleIcon';

interface AccessLogProps {
  events: AccessEvent[];
}

const LogItem: React.FC<{ event: AccessEvent }> = ({ event }) => {
    const isGranted = event.status === AccessStatus.GRANTED;
    const statusColor = isGranted ? 'text-green-400' : 'text-red-400';
    const statusBg = isGranted ? 'bg-green-500/10' : 'bg-red-500/10';
    const statusIcon = isGranted ? <CheckCircleIcon className="h-5 w-5" /> : <XCircleIcon className="h-5 w-5" />;

    return (
        <li className="flex items-center gap-4 p-3 bg-gray-800/50 hover:bg-gray-700/50 rounded-lg transition-colors duration-200 border-l-4" style={{borderColor: isGranted ? '#2dd4bf' : '#f87171'}}>
            <img src={event.avatar} alt={event.name} className="w-10 h-10 rounded-full object-cover border-2 border-gray-600"/>
            <div className="flex-grow">
                <p className="font-semibold text-white">{event.name}</p>
                <p className="text-xs text-gray-400">{event.time} - {event.date}</p>
            </div>
            <div className={`flex items-center gap-1.5 text-xs font-bold px-2 py-1 rounded-full ${statusColor} ${statusBg}`}>
                {statusIcon}
                <span>{event.status.toUpperCase()}</span>
            </div>
        </li>
    );
};

const AccessLog: React.FC<AccessLogProps> = ({ events }) => {
  return (
    <div className="bg-gray-800/50 rounded-xl shadow-2xl flex flex-col h-full max-h-[calc(100vh-10rem)] border border-gray-700">
      <div className="p-4 border-b border-gray-700">
        <h2 className="text-xl font-bold text-white">Registro de Actividad</h2>
        <p className="text-sm text-gray-400">Mostrando los últimos 20 eventos</p>
      </div>
      <div className="flex-grow p-4 overflow-y-auto">
        {events.length > 0 ? (
          <ul className="space-y-3">
             {events.map((event) => (
                <LogItem key={event.id} event={event} />
            ))}
          </ul>
        ) : (
          <div className="text-center py-10 text-gray-500">
            <p>No hay eventos registrados.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default AccessLog;

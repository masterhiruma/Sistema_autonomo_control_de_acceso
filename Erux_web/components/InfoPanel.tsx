
import React from 'react';
import { UserCircleIcon } from './icons/UserCircleIcon';
import { ClockIcon } from './icons/ClockIcon';
import { CalendarIcon } from './icons/CalendarIcon';


interface InfoPanelProps {
  name: string;
  time: string;
  date: string;
}

const InfoCard: React.FC<{ icon: React.ReactNode; label: string; value: string; isDetecting?: boolean }> = ({ icon, label, value, isDetecting }) => (
    <div className="bg-gray-800/60 p-4 rounded-lg flex items-center gap-4 border border-gray-700/80 flex-1 min-w-[200px]">
        {icon}
        <div>
            <p className="text-sm text-gray-400">{label}</p>
            <p className={`text-lg font-semibold text-white ${isDetecting ? 'animate-pulse' : ''}`}>{value}</p>
        </div>
    </div>
);


const InfoPanel: React.FC<InfoPanelProps> = ({ name, time, date }) => {
  return (
    <div className="w-full flex flex-wrap gap-4">
      <InfoCard
        icon={<UserCircleIcon className="h-10 w-10 text-cyan-400" />}
        label="Última Detección"
        value={name}
        isDetecting={name === 'Detectando...'}
      />
      <InfoCard
        icon={<ClockIcon className="h-10 w-10 text-cyan-400" />}
        label="Hora Actual"
        value={time}
      />
      <InfoCard
        icon={<CalendarIcon className="h-10 w-10 text-cyan-400" />}
        label="Fecha"
        value={date}
      />
    </div>
  );
};

export default InfoPanel;

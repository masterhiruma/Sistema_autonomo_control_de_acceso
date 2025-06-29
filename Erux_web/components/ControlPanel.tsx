
import React from 'react';
import { UserPlusIcon } from './icons/UserPlusIcon';
import { LockOpenIcon } from './icons/LockOpenIcon';
import { ChartBarIcon } from './icons/ChartBarIcon';
import { ExclamationTriangleIcon } from './icons/ExclamationTriangleIcon';

const ControlButton: React.FC<{ icon: React.ReactNode; label: string; className?: string; onClick?: () => void }> = ({ icon, label, className = '', onClick }) => {
  const baseClasses = "flex-1 text-center font-semibold py-3 px-6 rounded-lg shadow-md transition-all duration-300 ease-in-out transform hover:-translate-y-1 flex items-center justify-center gap-3";
  
  return (
    <button onClick={onClick} className={`${baseClasses} ${className}`}>
      {icon}
      <span>{label}</span>
    </button>
  );
};

interface ControlPanelProps {
  onOpenManualAccess: () => void;
  onOpenUserManagement: () => void;
  onOpenReports: () => void;
  onEmergency: () => void;
}

const ControlPanel: React.FC<ControlPanelProps> = ({ onOpenManualAccess, onOpenUserManagement, onOpenReports, onEmergency }) => {
  return (
    <div className="bg-gray-800/50 rounded-xl p-4 shadow-lg border border-gray-700">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-bold text-gray-200">Acciones</h3>
         <button 
          onClick={onEmergency}
          className="bg-red-600 hover:bg-red-500 text-white font-bold py-2 px-4 rounded-lg flex items-center gap-2 transition-transform transform hover:scale-105"
          aria-label="Botón de Emergencia"
        >
          <ExclamationTriangleIcon className="h-5 w-5" />
          <span>Emergencia</span>
        </button>
      </div>
      <div className="flex flex-col sm:flex-row gap-4">
        <ControlButton 
          icon={<LockOpenIcon className="h-6 w-6" />} 
          label="Acceso Manual" 
          className="bg-cyan-500 hover:bg-cyan-400 text-white"
          onClick={onOpenManualAccess}
        />
        <ControlButton 
          icon={<UserPlusIcon className="h-6 w-6" />} 
          label="Usuarios" 
          className="bg-gray-700 hover:bg-gray-600 text-gray-200 border border-gray-600"
          onClick={onOpenUserManagement}
        />
        <ControlButton 
          icon={<ChartBarIcon className="h-6 w-6" />} 
          label="Reportes" 
          className="bg-gray-700 hover:bg-gray-600 text-gray-200 border border-gray-600"
          onClick={onOpenReports}
        />
      </div>
    </div>
  );
};

export default ControlPanel;

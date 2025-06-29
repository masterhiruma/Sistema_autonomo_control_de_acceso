
import React, { useState } from 'react';
import { XMarkIcon } from './icons/XMarkIcon';
import { SignalIcon } from './icons/SignalIcon';
import { VideoCameraIcon } from './icons/VideoCameraIcon';
import { CpuChipIcon } from './icons/CpuChipIcon';
import { Cog6ToothIcon } from './icons/Cog6ToothIcon';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const SettingsRow: React.FC<{ icon: React.ReactNode; label: string; children: React.ReactNode }> = ({ icon, label, children }) => (
    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-4 py-4 border-b border-gray-700/60 last:border-b-0">
        <div className="flex items-center gap-3">
            {icon}
            <label className="text-gray-200 font-medium whitespace-nowrap">{label}</label>
        </div>
        <div className="w-full sm:w-auto flex-grow sm:flex-grow-0">
            {children}
        </div>
    </div>
);


const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
    const [isConnecting, setIsConnecting] = useState(false);

    const handleWirelessConnect = () => {
        setIsConnecting(true);
        console.log("Searching for ESP32 modules...");
        setTimeout(() => {
            setIsConnecting(false);
            console.log("Connection attempt finished.");
        }, 3000);
    };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-gray-800 w-full max-w-2xl rounded-2xl shadow-2xl border border-gray-700 transform transition-all" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Cog6ToothIcon className="h-6 w-6 text-cyan-400"/>
            Configuración del Sistema
          </h2>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-gray-700 transition-colors">
            <XMarkIcon className="h-6 w-6 text-gray-400" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-2">
            <SettingsRow icon={<SignalIcon className="h-5 w-5 text-gray-400" />} label="Conexión por Cable">
                <select className="bg-gray-900 border border-gray-600 text-white text-sm rounded-lg focus:ring-cyan-500 focus:border-cyan-500 block w-full p-2.5">
                    <option>COM1</option>
                    <option>COM3</option>
                    <option>COM4</option>
                    <option>COM8</option>
                </select>
            </SettingsRow>
             <SettingsRow icon={<SignalIcon className="h-5 w-5 text-cyan-400" />} label="Conexión Inalámbrica">
                <button
                    onClick={handleWirelessConnect}
                    disabled={isConnecting}
                    className="w-full justify-center text-sm bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-bold py-2.5 px-4 rounded-lg transition-colors flex items-center gap-2"
                >
                    {isConnecting ? 'Buscando ESP32...' : 'Conectar a Dispositivo'}
                </button>
            </SettingsRow>
            <SettingsRow icon={<VideoCameraIcon className="h-5 w-5 text-gray-400" />} label="Seleccionar Cámara">
                 <select className="bg-gray-900 border border-gray-600 text-white text-sm rounded-lg focus:ring-cyan-500 focus:border-cyan-500 block w-full p-2.5">
                    <option>Cámara Web Integrada</option>
                    <option>DroidCam Source 3</option>
                    <option>Logitech C920</option>
                </select>
            </SettingsRow>
             <SettingsRow icon={<CpuChipIcon className="h-5 w-5 text-gray-400" />} label="Máscara DIP">
                <div className="bg-gray-900 p-2.5 rounded-md font-mono text-lg text-cyan-300 tracking-[0.2em] text-center w-full">
                    10110
                </div>
            </SettingsRow>
        </div>
        
        {/* Footer */}
        <div className="bg-gray-800/50 p-4 border-t border-gray-700/60 rounded-b-2xl flex justify-end gap-3">
            <button onClick={onClose} className="px-4 py-2 text-sm font-medium text-gray-300 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">
                Cancelar
            </button>
            <button onClick={onClose} className="px-4 py-2 text-sm font-medium text-white bg-cyan-600 hover:bg-cyan-500 rounded-lg transition-colors">
                Guardar Cambios
            </button>
        </div>
      </div>
    </div>
  );
};

export default SettingsModal;

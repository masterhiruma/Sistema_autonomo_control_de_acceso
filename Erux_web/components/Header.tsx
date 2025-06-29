
import React from 'react';
import { ShieldCheckIcon } from './icons/ShieldCheckIcon';
import { Cog6ToothIcon } from './icons/Cog6ToothIcon';

interface HeaderProps {
  onOpenSettings: () => void;
}

const Header: React.FC<HeaderProps> = ({ onOpenSettings }) => {
  return (
    <header className="bg-gray-900/80 backdrop-blur-sm border-b border-gray-700/50 shadow-lg sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center">
            <ShieldCheckIcon className="h-8 w-8 text-cyan-400" />
            <h1 className="ml-3 text-2xl font-bold text-gray-100 tracking-tight">
              Sistema de Control de Acceso
            </h1>
          </div>
          <div>
            <button
              onClick={onOpenSettings}
              aria-label="Abrir configuración"
              className="p-2 rounded-full text-gray-400 hover:text-white hover:bg-gray-700 transition-colors duration-200"
            >
              <Cog6ToothIcon className="h-6 w-6" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;


import React from 'react';
import { XMarkIcon } from './icons/XMarkIcon';
import { ClockIcon } from './icons/ClockIcon';

interface ReportAutomationModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const ReportAutomationModal: React.FC<ReportAutomationModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  const handleSchedule = (e: React.FormEvent) => {
    e.preventDefault();
    console.log("Report scheduled!");
    onClose();
  }

  return (
    <div className="fixed inset-0 bg-gray-900/50 backdrop-blur-md flex items-center justify-center z-[60] p-4" onClick={onClose}>
      <div className="bg-gray-700 w-full max-w-lg rounded-xl shadow-2xl border border-gray-600" onClick={e => e.stopPropagation()}>
        <form onSubmit={handleSchedule}>
          <div className="flex items-center justify-between p-4 border-b border-gray-600">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <ClockIcon className="h-6 w-6 text-cyan-400" />
              Programar Reporte Automático
            </h3>
            <button type="button" onClick={onClose} className="p-1 rounded-full hover:bg-gray-600 transition-colors">
              <XMarkIcon className="h-6 w-6 text-gray-400" />
            </button>
          </div>
          <div className="p-6 space-y-4">
            <div>
              <label htmlFor="report-time" className="block text-sm font-medium text-gray-300 mb-1">Hora de Generación</label>
              <input type="time" id="report-time" defaultValue="08:00" className="bg-gray-800 border border-gray-500 text-white rounded-lg w-full p-2.5" />
            </div>
            <div>
              <label htmlFor="report-format" className="block text-sm font-medium text-gray-300 mb-1">Formato</label>
              <select id="report-format" className="bg-gray-800 border border-gray-500 text-white rounded-lg w-full p-2.5">
                <option>JSON</option>
                <option>PDF</option>
                <option>CSV</option>
              </select>
            </div>
            <div>
              <label htmlFor="report-emails" className="block text-sm font-medium text-gray-300 mb-1">Enviar a Correos (separados por coma)</label>
              <textarea id="report-emails" rows={3} placeholder="admin@empresa.com, seguridad@empresa.com" className="bg-gray-800 border border-gray-500 text-white rounded-lg w-full p-2.5"></textarea>
            </div>
            <div className="flex items-center justify-between">
              <label htmlFor="report-whatsapp" className="text-sm font-medium text-gray-300">¿Alertas por WhatsApp?</label>
              <label className="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" id="report-whatsapp" value="" className="sr-only peer" />
                <div className="w-11 h-6 bg-gray-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyan-600"></div>
              </label>
            </div>
          </div>
          <div className="bg-gray-700/50 p-4 border-t border-gray-600/60 rounded-b-xl flex justify-end gap-3">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm font-medium text-gray-300 bg-gray-600 hover:bg-gray-500 rounded-lg transition-colors">Cancelar</button>
            <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-cyan-600 hover:bg-cyan-500 rounded-lg transition-colors">Programar</button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ReportAutomationModal;

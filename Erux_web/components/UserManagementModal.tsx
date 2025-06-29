import React, { useState, useEffect } from 'react';
import { RegisteredUser } from '../types';
import { XMarkIcon } from './icons/XMarkIcon';
import { UserGroupIcon } from './icons/UserGroupIcon';
import { IdentificationIcon } from './icons/IdentificationIcon';
import { QrCodeIcon } from './icons/QrCodeIcon';
import { CameraIcon } from './icons/CameraIcon';
import { PencilIcon } from './icons/PencilIcon';
import { TrashIcon } from './icons/TrashIcon';
import { UserCircleIcon } from './icons/UserCircleIcon';

interface UserManagementModalProps {
  isOpen: boolean;
  onClose: () => void;
  users: RegisteredUser[];
  setUsers: React.Dispatch<React.SetStateAction<RegisteredUser[]>>;
}

const UserManagementModal: React.FC<UserManagementModalProps> = ({ isOpen, onClose, users, setUsers }) => {
    const BLANK_USER: RegisteredUser = { id: '', name: '', dni: '', userLevel: 'Usuario', uid: '', schedule: 'Diurno (8:00-18:00)', avatar: '' };
    const [formData, setFormData] = useState<RegisteredUser>(BLANK_USER);
    const [isEditing, setIsEditing] = useState<string | null>(null);

    useEffect(() => {
        if (!isOpen) {
            // Reset form when modal closes
            setTimeout(() => {
                setFormData(BLANK_USER);
                setIsEditing(null);
            }, 200);
        }
    }, [isOpen]);

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { name, value } = e.target;
        if (name === 'userLevel') {
            setFormData(prev => ({ ...prev, userLevel: value as RegisteredUser['userLevel'] }));
        } else {
            setFormData(prev => ({ ...prev, [name]: value }));
        }
    };

    const handleEditClick = (user: RegisteredUser) => {
        setIsEditing(user.id);
        setFormData(user);
    };

    const handleDeleteClick = (userId: string) => {
        if(window.confirm('¿Está seguro que desea eliminar a este usuario?')) {
            setUsers(prev => prev.filter(u => u.id !== userId));
        }
    };
    
    const handleFormSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (isEditing) {
            // Update user
            setUsers(prev => prev.map(u => u.id === isEditing ? formData : u));
            console.log("Usuario actualizado:", formData);
        } else {
            // Add new user
            const newUser: RegisteredUser = { ...formData, id: String(Date.now()), avatar: `https://i.pravatar.cc/40?u=${formData.name.replace(' ','')}`};
            setUsers(prev => [newUser, ...prev]);
            console.log("Nuevo usuario registrado:", newUser);
        }
        setFormData(BLANK_USER);
        setIsEditing(null);
    };
    
    const clearForm = () => {
        setFormData(BLANK_USER);
        setIsEditing(null);
    }

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-gray-800 w-full max-w-6xl h-[90vh] rounded-2xl shadow-2xl border border-gray-700 flex flex-col" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700 flex-shrink-0">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <UserGroupIcon className="h-6 w-6 text-cyan-400"/>
            Gestión de Usuarios
          </h2>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-gray-700 transition-colors">
            <XMarkIcon className="h-6 w-6 text-gray-400" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-grow flex flex-col md:flex-row gap-6 p-6 overflow-hidden">
            {/* Left Column: Form */}
            <div className="w-full md:w-1/3 lg:w-2/5 flex flex-col gap-4">
                 <h3 className="text-lg font-semibold text-white -mb-2">{isEditing ? "Editando Usuario" : "Registrar Nuevo Usuario"}</h3>
                 <div className="w-full aspect-square bg-gray-900 rounded-lg flex items-center justify-center">
                    <CameraIcon className="h-24 w-24 text-gray-700" />
                 </div>
                 <button className="w-full bg-gray-700 hover:bg-gray-600 text-white font-bold py-2 px-4 rounded-lg transition-colors flex items-center justify-center gap-2">
                     <CameraIcon className="h-5 w-5" />
                     Capturar Rostro
                 </button>
                <form onSubmit={handleFormSubmit} className="space-y-3">
                    <input type="text" name="name" value={formData.name} onChange={handleInputChange} placeholder="Nombre Completo" className="w-full bg-gray-900 border border-gray-600 text-white rounded-md p-2" required />
                    <input type="text" name="dni" value={formData.dni} onChange={handleInputChange} placeholder="DNI" className="w-full bg-gray-900 border border-gray-600 text-white rounded-md p-2" required />
                    <select name="userLevel" value={formData.userLevel} onChange={handleInputChange} className="w-full bg-gray-900 border border-gray-600 text-white rounded-md p-2">
                        <option>Usuario</option>
                        <option>Administrador</option>
                        <option>Visitante</option>
                    </select>
                    <div className="flex gap-2">
                        <input type="text" name="uid" value={formData.uid} onChange={handleInputChange} placeholder="Código UID" className="w-full bg-gray-900 border border-gray-600 text-white rounded-md p-2"/>
                        <button type="button" className="p-2 bg-gray-700 hover:bg-gray-600 rounded-md"><QrCodeIcon className="h-5 w-5 text-white"/></button>
                    </div>
                    <select name="schedule" value={formData.schedule} onChange={handleInputChange} className="w-full bg-gray-900 border border-gray-600 text-white rounded-md p-2">
                        <option>Diurno (8:00-18:00)</option>
                        <option>Nocturno (18:00-8:00)</option>
                        <option>Acceso Total</option>
                        <option>Temporal</option>
                    </select>
                    <div className="flex gap-3 pt-2">
                         <button type="submit" className="w-full text-white font-bold py-2 px-4 rounded-lg transition-colors bg-cyan-600 hover:bg-cyan-500">
                           {isEditing ? 'Actualizar Usuario' : 'Guardar Usuario'}
                        </button>
                        {isEditing && (
                             <button type="button" onClick={clearForm} className="w-full text-gray-300 font-bold py-2 px-4 rounded-lg transition-colors bg-gray-600 hover:bg-gray-500">
                                Cancelar
                            </button>
                        )}
                    </div>
                </form>
            </div>
            {/* Right Column: User List */}
            <div className="w-full md:w-2/3 lg:w-3/5 flex flex-col bg-gray-900/50 rounded-lg border border-gray-700">
                <div className="p-3 border-b border-gray-700">
                     <h3 className="text-lg font-semibold text-white">Usuarios Registrados ({users.length})</h3>
                </div>
                <div className="flex-grow overflow-y-auto p-3">
                    <ul className="space-y-2">
                       {users.map(user => (
                        <li key={user.id} className={`flex items-center gap-4 p-2 rounded-md transition-colors duration-200 ${isEditing === user.id ? 'bg-cyan-500/20' : 'bg-gray-800 hover:bg-gray-700/70'}`}>
                            <img src={user.avatar} alt={user.name} className="w-10 h-10 rounded-full object-cover border-2 border-gray-600"/>
                            <div className="flex-grow grid grid-cols-2 sm:grid-cols-3 gap-x-4 text-sm">
                                <span className="font-semibold text-white col-span-2 sm:col-span-1">{user.name}</span>
                                <span className="text-gray-400"><strong className="text-gray-300 font-medium">DNI:</strong> {user.dni}</span>
                                <span className="text-gray-400"><strong className="text-gray-300 font-medium">UID:</strong> {user.uid}</span>
                            </div>
                            <div className="flex gap-2">
                                <button onClick={() => handleEditClick(user)} className="p-2 text-gray-400 hover:text-white hover:bg-gray-600 rounded-full"><PencilIcon className="h-5 w-5"/></button>
                                <button onClick={() => handleDeleteClick(user.id)} className="p-2 text-gray-400 hover:text-red-400 hover:bg-red-900/50 rounded-full"><TrashIcon className="h-5 w-5"/></button>
                            </div>
                        </li>
                       ))}
                    </ul>
                </div>
            </div>
        </div>
      </div>
    </div>
  );
};

export default UserManagementModal;
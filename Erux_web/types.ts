
export enum AccessStatus {
  GRANTED = 'Concedido',
  DENIED = 'Denegado',
}

export interface AccessEvent {
  id: number;
  name: string;
  time: string;
  date: string;
  status: AccessStatus;
  avatar: string;
}

export interface RegisteredUser {
  id: string;
  name: string;
  dni: string;
  userLevel: 'Administrador' | 'Usuario' | 'Visitante';
  uid: string;
  schedule: string;
  avatar: string;
}

export interface EmergencyEvent {
  id: number;
  timestamp: Date;
  videoUrl: string;
}

export type AIAction = 
    | { type: 'navigate'; payload: 'open_user_management' | 'open_reports' | 'open_settings' }
    | { type: 'schedule_report'; payload: { email: string; time: string; format: string } };


export interface ChatMessage {
    id: number;
    text: string;
    sender: 'user' | 'ai';
    action?: AIAction;
}
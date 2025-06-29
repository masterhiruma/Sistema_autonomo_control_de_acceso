
import React from 'react';
import { QuestionMarkCircleIcon } from './icons/QuestionMarkCircleIcon';

interface HelpButtonProps {
    onClick: () => void;
}

const HelpButton: React.FC<HelpButtonProps> = ({ onClick }) => {
    return (
        <button
            onClick={onClick}
            aria-label="Abrir asistente de ayuda"
            className="fixed bottom-8 right-8 bg-cyan-600 hover:bg-cyan-500 text-white rounded-full p-4 shadow-lg transition-transform transform hover:scale-110 z-40"
        >
            <QuestionMarkCircleIcon className="h-8 w-8" />
        </button>
    );
};

export default HelpButton;
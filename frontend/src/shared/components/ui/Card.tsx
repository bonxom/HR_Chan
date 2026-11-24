import React from 'react';
import { GLASS_PANEL } from './Glass';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  hoverEffect?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  className = '',
  onClick,
  hoverEffect = false,
}) => {
  return (
    <div
      onClick={onClick}
      className={`rounded-panel p-6 ${GLASS_PANEL} ${
        hoverEffect ? 'cursor-pointer transition-all hover:-translate-y-0.5 hover:bg-white/95' : ''
      } ${className}`}
    >
      {children}
    </div>
  );
};

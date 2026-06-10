import { ReactNode } from 'react';

interface GlassPanelProps {
  children: ReactNode;
  className?: string;
  interactive?: boolean;
}

export default function GlassPanel({ children, className = '', interactive = false }: GlassPanelProps) {
  return (
    <div className={`glass rounded-lg ${interactive ? 'glass-interactive' : ''} ${className}`}>
      {children}
    </div>
  );
}

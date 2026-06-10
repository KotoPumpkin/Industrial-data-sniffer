import React, { ReactNode } from 'react';
import CountUp from './CountUp';

interface StatCardProps {
  label: string;
  value: number;
  unit?: string;
  icon?: ReactNode;
  color?: string;
  decimals?: number;
  loading?: boolean;
}

const GLOW_MAP: Record<string, string> = {
  'text-red-400': 'kpi-glow-red',
  'text-green-400': 'kpi-glow-green',
  'text-orange-400': 'kpi-glow-orange',
  'text-blue-400': 'kpi-glow-blue',
};

export default React.memo(function StatCard({ label, value, unit = '', icon, color = 'text-blue-400', decimals = 0, loading = false }: StatCardProps) {
  const glowClass = GLOW_MAP[color] || '';

  return (
    <div className="glass glass-interactive rounded-lg px-4 py-3">
      <div className="text-xs text-gray-500 uppercase tracking-wider mb-1 font-heading font-semibold">
        {label}
      </div>
      <div className="flex items-end gap-1.5">
        {icon && <span className="text-gray-500 mb-0.5">{icon}</span>}
        {loading ? (
          <span className="skeleton inline-block w-20 h-7" />
        ) : (
          <CountUp
            end={value}
            decimals={decimals}
            className={`text-2xl font-bold font-kpi tabular-nums ${color} ${glowClass}`}
          />
        )}
        {unit && (
          <span className="text-xs text-gray-500 mb-1 font-data tabular-nums">
            {unit}
          </span>
        )}
      </div>
    </div>
  );
});

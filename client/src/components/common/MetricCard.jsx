import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

export default function MetricCard({ label, value, unit = '', trend = null, trendValue = null, icon: Icon = null, className = '' }) {
  const renderTrend = () => {
    if (trend === null) return null;
    if (trend === 'up') return <div className="flex items-center gap-1 text-emerald-400 text-xs"><TrendingUp size={12} />{trendValue}</div>;
    if (trend === 'down') return <div className="flex items-center gap-1 text-red-400 text-xs"><TrendingDown size={12} />{trendValue}</div>;
    return <div className="flex items-center gap-1 text-yellow-400 text-xs"><Minus size={12} />{trendValue}</div>;
  };

  return (
    <div className={`bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-4 ${className}`}>
      <div className="flex items-start justify-between mb-2">
        <span className="text-xs text-emerald-400/60 uppercase tracking-wide">{label}</span>
        {Icon && <Icon size={14} className="text-emerald-600" />}
      </div>
      <div className="flex items-end gap-1.5">
        <span className="text-2xl font-bold text-white">{value ?? '—'}</span>
        {unit && <span className="text-sm text-emerald-400/60 mb-0.5">{unit}</span>}
      </div>
      {renderTrend()}
    </div>
  );
}

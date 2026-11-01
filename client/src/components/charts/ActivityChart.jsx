import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-[#0d1a0d] border border-emerald-900/40 rounded-lg px-3 py-2 text-xs">
        <p className="text-emerald-400 font-medium">{label}</p>
        <p className="text-white">{payload[0].value} {payload[0].name}</p>
      </div>
    );
  }
  return null;
};

export default function ActivityChart({ data = [], dataKey = 'value', nameKey = 'day', label = 'minutes', height = 180 }) {
  const formatted = data.map(d => ({ ...d, name: d[nameKey] || d.name }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={formatted} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1a2e1a" />
        <XAxis dataKey="name" tick={{ fill: '#6ee7b7', fontSize: 10 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: '#6ee7b7', fontSize: 10 }} axisLine={false} tickLine={false} />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(16,185,129,0.05)' }} />
        <Bar dataKey={dataKey} name={label} fill="#10b981" radius={[3, 3, 0, 0]} maxBarSize={32} />
      </BarChart>
    </ResponsiveContainer>
  );
}

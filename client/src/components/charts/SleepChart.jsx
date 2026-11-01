import React from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-[#0d1a0d] border border-emerald-900/40 rounded-lg px-3 py-2 text-xs">
        <p className="text-emerald-400 font-medium">{label}</p>
        <p className="text-white">{payload[0].value}h sleep</p>
      </div>
    );
  }
  return null;
};

export default function SleepChart({ data = [], height = 180 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1a2e1a" />
        <XAxis dataKey="day" tick={{ fill: '#6ee7b7', fontSize: 10 }} axisLine={false} tickLine={false} />
        <YAxis domain={[0, 12]} tick={{ fill: '#6ee7b7', fontSize: 10 }} axisLine={false} tickLine={false} />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={8} stroke="#10b981" strokeDasharray="4 4" strokeOpacity={0.4} />
        <Line
          type="monotone"
          dataKey="hours"
          stroke="#34d399"
          strokeWidth={2}
          dot={{ fill: '#10b981', strokeWidth: 0, r: 3 }}
          activeDot={{ r: 5, fill: '#34d399' }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

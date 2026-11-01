import React from 'react';
import {
  LineChart, Line, ResponsiveContainer, Tooltip
} from 'recharts';

export default function TrendLine({ data = [], dataKey = 'value', color = '#10b981', height = 40 }) {
  const formatted = data.map((d, i) => (typeof d === 'number' ? { value: d, i } : d));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={formatted}>
        <Line
          type="monotone"
          dataKey={dataKey}
          stroke={color}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
        <Tooltip
          contentStyle={{ background: '#0d1a0d', border: '1px solid #1a3a1a', borderRadius: 6, fontSize: 10 }}
          itemStyle={{ color: '#34d399' }}
          labelStyle={{ display: 'none' }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

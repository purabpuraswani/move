import React from 'react';

export default function LoadingSpinner({ size = 'md', text = '' }) {
  const sizeClasses = {
    sm: 'w-5 h-5 border-2',
    md: 'w-8 h-8 border-2',
    lg: 'w-12 h-12 border-2',
  };

  return (
    <div className="flex flex-col items-center justify-center gap-3">
      <div className={`${sizeClasses[size] || sizeClasses.md} border-emerald-500 border-t-transparent rounded-full animate-spin`} />
      {text && <p className="text-emerald-400/60 text-sm">{text}</p>}
    </div>
  );
}

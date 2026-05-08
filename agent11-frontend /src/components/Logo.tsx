import React from 'react';

export const Logo = ({ className }: { className?: string }) => {
  return (
    <svg 
      viewBox="0 0 100 100" 
      className={className}
      fill="none" 
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Background Geometric Pattern */}
      <g stroke="#444" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M50 10 L80 40 L50 70 L20 40 Z" opacity="0.1" />
        <path d="M35 15 L15 35 L35 55" />
        <path d="M65 15 L85 35 L65 55" />
        <path d="M35 85 L15 65 L35 45" />
        <path d="M65 85 L85 65 L65 45" />
      </g>

      {/* Stylized "i" */}
      <rect x="38" y="42" width="8" height="35" fill="#333" rx="1" />
      <circle cx="42" cy="32" r="5" fill="#a11" />

      {/* Stylized "1" */}
      <path d="M52 42 L62 32 V77" stroke="#333" strokeWidth="9" strokeLinecap="butt" />
      
      {/* Registered Trademark Symbol */}
      <circle cx="88" cy="12" r="8" stroke="#666" strokeWidth="1" />
      <text x="88" y="15" fontSize="10" textAnchor="middle" fill="#666" fontWeight="bold" fontFamily="sans-serif">R</text>
    </svg>
  );
};

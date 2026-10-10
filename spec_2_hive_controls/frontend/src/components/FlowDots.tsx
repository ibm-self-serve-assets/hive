import React from 'react';

interface FlowDotsProps {
  running?: boolean;
  color?: string;
}

export const FlowDots: React.FC<FlowDotsProps> = ({
  running = true,
  color = '#2850B8',
}) => {
  return (
    <svg
      width={48}
      height={20}
      viewBox="0 0 48 20"
      aria-hidden="true"
      style={{ overflow: 'hidden', flexShrink: 0 }}
    >
      <style>{`
        @keyframes hive-dot-flow {
          from { transform: translateX(0); }
          to   { transform: translateX(10px); }
        }
        @media (prefers-reduced-motion: reduce) {
          .hive-flow-dot { animation: none !important; }
        }
      `}</style>
      {Array.from({ length: 6 }, (_, i) => (
        <circle
          key={i}
          className="hive-flow-dot"
          cx={i * 10 - 5}
          cy={10}
          r={2.5}
          fill={color}
          style={{
            animation: 'hive-dot-flow 1.4s linear infinite',
            animationPlayState: running ? 'running' : 'paused',
          }}
        />
      ))}
    </svg>
  );
};

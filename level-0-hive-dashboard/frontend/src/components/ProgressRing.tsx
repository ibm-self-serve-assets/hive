import React from 'react';

interface ProgressRingProps {
  /** Optional 0–100 progress */
  percent?: number;
  /** Label shown in the centre (e.g. "+5") */
  label: string;
  size?: number;
  strokeWidth?: number;
  /** Whether the pulsing animation is active (1 cycle every 5 seconds) */
  spinning?: boolean;
}

/**
 * Dot spinner with stationary dots: each dot pulses its opacity sequentially
 * (1 full cycle every 5 seconds) to simulate circular motion without rotating the container.
 */
export const ProgressRing: React.FC<ProgressRingProps> = ({
  label,
  size = 80,
  spinning = true,
}) => {
  const numDots = 12;
  const cx = size / 2;
  const cy = size / 2;
  const ringRadius = size * 0.37;
  const dotRadius = size * 0.052;
  const cycleSeconds = 5;

  const dots = Array.from({ length: numDots }, (_, i) => {
    // Clockwise angles: 0 (12 o'clock), 30 (1 o'clock), 60 (2 o'clock)... 330 (11 o'clock)
    const angle = (i * 360) / numDots;
    const rad = (angle * Math.PI) / 180;
    const x = cx + ringRadius * Math.sin(rad);
    const y = cy - ringRadius * Math.cos(rad);
    // Staggered delay for reverse motion direction
    const delay = -((((numDots - i) % numDots) * cycleSeconds) / numDots);
    return { x, y, delay, key: i };
  });

  return (
    <div className="relative inline-block select-none" style={{ width: size, height: size }}>
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{ display: 'block' }}
      >
        {dots.map(({ x, y, delay, key }) => (
          <circle
            key={key}
            cx={x}
            cy={y}
            r={dotRadius}
            fill="#2850B8"
            style={{
              opacity: spinning ? undefined : 0.1,
              animation: spinning ? `dotClockwiseFade ${cycleSeconds}s linear infinite` : 'none',
              animationDelay: spinning ? `${delay.toFixed(3)}s` : undefined,
            }}
          />
        ))}
      </svg>
      {/* Centre label — fixed orientation */}
      <div
        className="absolute inset-0 flex items-center justify-center font-bold text-[#031040] pointer-events-none"
        style={{
          fontSize: `${Math.round(size * 0.22)}px`,
          fontFamily: 'IBM Plex Sans, sans-serif',
        }}
      >
        {label}
      </div>
    </div>
  );
};

import React from 'react';

interface ProgressRingProps {
  /** 0–100 — how full the ring appears */
  percent: number;
  /** Label shown in the centre (e.g. "+5") */
  label: string;
  size?: number;
  strokeWidth?: number;
}

/**
 * SVG arc ring: dark-blue track + blue filled arc + centred bold label.
 * Matches the design comp style exactly.
 */
export const ProgressRing: React.FC<ProgressRingProps> = ({
  percent,
  label,
  size = 80,
  strokeWidth = 7,
}) => {
  const r = (size - strokeWidth) / 2;
  const cx = size / 2;
  const circumference = 2 * Math.PI * r;
  const filled = Math.min(100, Math.max(0, percent));
  // Arc starts at top (−90°), goes clockwise
  const dashOffset = circumference - (filled / 100) * circumference;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ display: 'block' }}>
      {/* Track */}
      <circle
        cx={cx}
        cy={cx}
        r={r}
        fill="none"
        stroke="#DDEAFF"
        strokeWidth={strokeWidth}
      />
      {/* Progress arc */}
      <circle
        cx={cx}
        cy={cx}
        r={r}
        fill="none"
        stroke="#2850B8"
        strokeWidth={strokeWidth}
        strokeDasharray={circumference}
        strokeDashoffset={dashOffset}
        strokeLinecap="round"
        transform={`rotate(-90 ${cx} ${cx})`}
      />
      {/* Centre label */}
      <text
        x={cx}
        y={cx}
        dominantBaseline="central"
        textAnchor="middle"
        fill="#031040"
        fontSize={size * 0.22}
        fontWeight="700"
        fontFamily="IBM Plex Sans, sans-serif"
      >
        {label}
      </text>
    </svg>
  );
};

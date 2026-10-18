import React from 'react';

/** Horizontal dotted connector between the three lanes. */
export const FlowDots: React.FC = () => (
  <div className="flex items-center justify-center" style={{ width: '48px', flexShrink: 0 }}>
    <div className="flex gap-1">
      {[0, 1, 2, 3, 4].map((i) => (
        <span
          key={i}
          className="block rounded-full bg-[#2850B8]"
          style={{ width: 6, height: 6, opacity: 0.5 + i * 0.1 }}
        />
      ))}
    </div>
  </div>
);

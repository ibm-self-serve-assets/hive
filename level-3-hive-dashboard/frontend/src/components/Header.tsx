import React from 'react';

export const Header: React.FC = () => {
  return (
    <header
      className="flex items-center justify-between px-6 border-b border-[#1A2760] select-none shrink-0"
      style={{ background: '#031040', height: '56px' }}
    >
      {/* Left: wordmark + subtitle + nav */}
      <div className="flex items-center gap-8">
        <div className="flex items-center gap-3">
          <span className="font-bold text-white tracking-widest text-xl leading-none">Hive Robotics
          </span>
        </div>
        <nav className="flex items-end h-14">
          <button className="relative px-4 h-14 text-sm font-semibold text-white flex items-center">
            Manufacturing
            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#6FA1FE]" />
          </button>
        </nav>
      </div>

    </header>
  );
};

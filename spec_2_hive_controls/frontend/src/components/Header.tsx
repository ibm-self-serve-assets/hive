import React from 'react';

interface HeaderProps {
  streamHealth: 'live' | 'stale' | 'awaiting_events';
  factoryId: string | null;
}

export const Header: React.FC<HeaderProps> = ({ streamHealth, factoryId: _factoryId }) => {
  const isLive = streamHealth === 'live';

  return (
    <header
      className="flex items-center justify-between px-6 border-b border-[#1A2760] select-none shrink-0"
      style={{ background: '#031040', height: '56px' }}
    >
      {/* Left: wordmark + subtitle + nav */}
      <div className="flex items-center gap-8">
        <div className="flex items-center gap-3">
          <span className="font-bold text-white tracking-widest text-xl leading-none">HIVE</span>
          <span className="text-[#6FA1FE] text-xs font-medium hidden sm:block">
            Enterprise Robotic Bee Simulation
          </span>
        </div>
        <nav className="flex items-end h-14">
          <button className="relative px-4 h-14 text-sm font-semibold text-white flex items-center">
            Manufacturing
            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#6FA1FE]" />
          </button>
        </nav>
      </div>

      {/* Right: stream status pill */}
      <div className="flex items-center gap-3">
        <div
          className="flex items-center gap-2.5 bg-[#2850B8] text-white text-xs font-semibold px-4 py-1.5 rounded-full"
        >
          <div className="flex items-center gap-1.5">
            {isLive ? (
              <img src="/icons/factory_status_connected.png" width={10} height={10} alt="live" />
            ) : (
              <span className={`w-2 h-2 rounded-full ${streamHealth === 'stale' ? 'bg-amber-400' : 'bg-[#4A5A8A]'}`} />
            )}
            <span className="text-[11px] text-[#00000]">
              {isLive ? 'connected' : streamHealth === 'stale' ? 'stale' : 'connecting'}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};

import React from 'react';
import { FactorySnapshot } from '../types';

// Provisioning states the sim server can return before factory is usable
const PROVISIONING_STATUSES = new Set(['provisioning', 'pending']);

interface SidebarProps {
  snapshot: FactorySnapshot | null;
  simTimeMs: number;
  commandReceipt: any;
  onSendCommand: (command: string, extra?: any) => Promise<void>;
  isCommandPending: boolean;
}

function fmtSimTime(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export const Sidebar: React.FC<SidebarProps> = ({
  snapshot,
  simTimeMs,
  commandReceipt: _commandReceipt,
  onSendCommand,
  isCommandPending,
}) => {
  const isRunning = snapshot?.running ?? false;
  const lifecycleStatus = snapshot?.lifecycle_status ?? 'paused';

  const isStopped = lifecycleStatus === 'stopped';
  const isExpired = lifecycleStatus === 'expired';
  const hasSnapshot = snapshot !== null;
  // Factory exists but probe writes are still in progress — block all commands
  const isProvisioning = !hasSnapshot || PROVISIONING_STATUSES.has(lifecycleStatus);

  const handleLeftButton = () => {
    if (isRunning) {
      onSendCommand('stop');
    } else if (isStopped) {
      onSendCommand('restart', { start: true });
    } else {
      onSendCommand('start');
    }
  };

  return (
    <aside
      className="flex flex-col justify-between select-none border-r border-[#1A2760] shrink-0"
      style={{ width: '216px', background: '#031040', color: '#fff' }}
    >
      <div className="p-5 space-y-5">

        {/* ── Simulation controls ── */}
        <section>
          <h2 className="text-xs font-bold text-white mb-3">Simulation controls</h2>
          {isProvisioning && (
            <div className="mb-3 px-3 py-2 rounded text-xs text-[#8AA0D0] border border-[#1A2760] bg-[#0C1A52] leading-snug">
              Factory provisioning — Confluent probe writes in progress. Controls will unlock shortly.
            </div>
          )}
          <div className="flex gap-2">
            <button
              onClick={handleLeftButton}
              disabled={isCommandPending || isExpired || isProvisioning}
              className="flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded text-sm font-bold bg-[#2850B8] hover:bg-[#3460C8] text-white disabled:opacity-40 disabled:cursor-not-allowed transition"
            >
              {isRunning ? (
                <>
                  <img src="/icons/simulation-controls__pause__pause.png" width={14} height={14} alt="Stop" />
                  <span>Stop</span>
                </>
              ) : isStopped ? (
                <span>Restart</span>
              ) : (
                <>
                  <img src="/icons/simulation-controls__run__play.png" width={14} height={14} alt="Run" />
                  <span>Run</span>
                </>
              )}
            </button>

            {isRunning && (
              <button
                onClick={() => onSendCommand('pause')}
                disabled={isCommandPending}
                className="flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded text-sm font-bold bg-[#1A3080] hover:bg-[#243D96] text-white disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                <img src="/icons/simulation-controls__pause__pause.png" width={14} height={14} alt="Pause" />
                <span>Pause</span>
              </button>
            )}
          </div>
        </section>

        {/* ── System time ── */}
        <section>
          <div className="flex items-center gap-2 text-[#8AA0D0] text-xs mb-1">
            <img src="/icons/clock.png" width={16} height={16} alt="clock" className="shrink-0 opacity-70" />
            <span>System time</span>
          </div>
          <div className="font-bold font-mono text-white text-xl tabular-nums tracking-tight">
            {hasSnapshot ? fmtSimTime(simTimeMs) : '--:--:--'}
          </div>
        </section>

      </div>

      <div className="px-5 py-3 border-t border-[#1A2760] text-[10px] text-[#4A5A8A]">
        Closing this app does not pause the hosted factory.
      </div>
    </aside>
  );
};

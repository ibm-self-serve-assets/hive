import React from 'react';
import { FactorySnapshot } from '../types';

// Provisioning states the sim server can return before factory is usable
const PROVISIONING_STATUSES = new Set(['provisioning', 'pending']);

interface SidebarProps {
  streamHealth: 'live' | 'stale' | 'awaiting_events';
  level: number;
  onLevelChange: (level: number) => void;
  snapshot: FactorySnapshot | null;
  simTimeMs: number;
  commandReceipt: any;
  onSendCommand: (command: string, extra?: any) => Promise<void>;
  isCommandPending: boolean;
}

const MAX_SIM_MS = 3_600_000; // factory TTL is 1 hour

function fmtSimTime(ms: number): string {
  const clamped = Math.min(ms, MAX_SIM_MS);
  const totalSec = Math.floor(clamped / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export const Sidebar: React.FC<SidebarProps> = ({
  streamHealth,
  level,
  onLevelChange,
  snapshot,
  simTimeMs,
  commandReceipt: _commandReceipt,
  onSendCommand,
  isCommandPending,
}) => {
  const isLive = streamHealth === 'live';
  const isRunning = snapshot?.running ?? false;
  const lifecycleStatus = snapshot?.lifecycle_status ?? 'paused';

  const isStopped = lifecycleStatus === 'stopped';
  const isExpired = lifecycleStatus === 'expired';
  const hasSnapshot = snapshot !== null;
  // Factory exists but probe writes are still in progress — block all commands
  const isProvisioning = !hasSnapshot || PROVISIONING_STATUSES.has(lifecycleStatus);

  const handleRestart = () => {
    onSendCommand('restart', { start: true });
  };

  return (
    <aside
      className="flex flex-col justify-between select-none border-r border-[#1A2760] shrink-0"
      style={{ width: '216px', background: '#031040', color: '#fff' }}
    >
      <div className="p-5 space-y-5">

        {/* ── Stream status pill ── */}
        <div className="inline-flex items-center gap-1.5 bg-[#2850B8] text-white text-xs font-semibold px-4 py-1.5 rounded-full">
          {isLive ? (
            <img src="/icons/simulation_status_connected.png" width={10} height={10} alt="live" />
          ) : (
            <span className={`w-2 h-2 rounded-full ${streamHealth === 'stale' ? 'bg-amber-400' : 'bg-[#4A5A8A]'}`} />
          )}
          <span className="text-[11px]">
            {isLive ? 'connected' : streamHealth === 'stale' ? 'stale' : 'connecting'}
          </span>
        </div>

        {/* ── Simulation controls ── */}
        <section>
          <h2 className="text-xs font-bold text-white mb-3">Simulation controls</h2>

          {isExpired && (
            <div className="mb-3 px-3 py-2 rounded text-xs text-amber-300 border border-amber-800 bg-[#2a1800] leading-snug">
              Simulation complete. Start a new run below.
            </div>
          )}
          {!isExpired && isProvisioning && (
            <div className="mb-3 px-3 py-2 rounded text-xs text-[#8AA0D0] border border-[#1A2760] bg-[#0C1A52] leading-snug">
              Factory provisioning — Confluent probe writes in progress. Controls will unlock shortly.
            </div>
          )}

          {/* Expired: show Restart as the primary action */}
          {isExpired && (
            <button
              onClick={handleRestart}
              disabled={isCommandPending}
              className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded text-sm font-bold bg-[#2850B8] hover:bg-[#3460C8] text-white disabled:opacity-40 disabled:cursor-not-allowed transition"
            >
              <img src="/icons/simulation_controls_run.png" width={14} height={14} alt="Restart" />
              <span>Restart</span>
            </button>
          )}

          {/* Normal controls — hidden when expired */}
          {!isExpired && (
            <div className="flex gap-2">
              {/* Stopped → Restart only; Paused → Run; Running → Stop */}
              {isStopped ? (
                <button
                  onClick={handleRestart}
                  disabled={isCommandPending || isProvisioning}
                  className="flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded text-sm font-bold bg-[#2850B8] hover:bg-[#3460C8] text-white disabled:opacity-40 disabled:cursor-not-allowed transition"
                >
                  <img src="/icons/simulation_controls_run.png" width={14} height={14} alt="Restart" />
                  <span>Restart</span>
                </button>
              ) : (
                <button
                  onClick={() => isRunning ? onSendCommand('stop') : onSendCommand('start')}
                  disabled={isCommandPending || isProvisioning}
                  className="flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded text-sm font-bold bg-[#2850B8] hover:bg-[#3460C8] text-white disabled:opacity-40 disabled:cursor-not-allowed transition"
                >
                  {isRunning ? (
                    <>
                      <img src="/icons/simulation_controls_pause.png" width={14} height={14} alt="Stop" />
                      <span>Stop</span>
                    </>
                  ) : (
                    <>
                      <img src="/icons/simulation_controls_run.png" width={14} height={14} alt="Run" />
                      <span>Run</span>
                    </>
                  )}
                </button>
              )}

              {isRunning && (
                <button
                  onClick={() => onSendCommand('pause')}
                  disabled={isCommandPending}
                  className="flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded text-sm font-bold bg-[#1A3080] hover:bg-[#243D96] text-white disabled:opacity-40 disabled:cursor-not-allowed transition"
                >
                  <img src="/icons/simulation_controls_pause.png" width={14} height={14} alt="Pause" />
                  <span>Pause</span>
                </button>
              )}
            </div>
          )}
        </section>

        {/* ── Sim time ── */}
        <section>
          <div className="flex items-center gap-2 text-[#8AA0D0] text-xs mb-1">
            <img src="/icons/clock.png" width={16} height={16} alt="clock" className="shrink-0 opacity-70" />
            <span>Sim time</span>
          </div>
          <div className="font-bold font-mono text-white text-xl tabular-nums tracking-tight">
            {hasSnapshot ? fmtSimTime(simTimeMs) : '--:--:--'}
          </div>
        </section>

      </div>

      <div className="border-t border-[#1A2760]">
        <label className="flex items-center justify-between gap-2 px-5 py-3 text-xs font-semibold text-[#6FA1FE]">
          Levels
          <select
            value={level}
            onChange={(e) => onLevelChange(Number(e.target.value))}
            aria-label="Levels"
            className="bg-[#0C1A52] text-white text-xs font-semibold rounded border border-[#1A2760] px-2 py-1 focus:outline-none focus:ring-2 focus:ring-[#6FA1FE]"
          >
            <option value={1}>Level 1</option>
            <option value={2}>Level 2</option>
          </select>
        </label>
        <div className="px-5 pb-3 text-[10px] text-[#4A5A8A]">
          Closing this app does not pause the hosted factory.
        </div>
      </div>
    </aside>
  );
};

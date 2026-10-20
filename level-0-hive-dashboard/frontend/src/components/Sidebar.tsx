import React from 'react';
import { DashboardState, fmtSimTime } from '../types';
import { LEVELS } from '../levels/registry';

interface SidebarProps {
  state: DashboardState;
  csrfToken: string;
  isCommandPending: boolean;
  onSendCommand: (command: string, extra?: Record<string, unknown>) => Promise<void>;
  levelId: string;
  onLevelChange: (levelId: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  state,
  csrfToken: _csrfToken,
  isCommandPending,
  onSendCommand,
  levelId,
  onLevelChange,
}) => {
  const { stream_health, lifecycle_status, running, sim_time_minutes, active_factory_id } = state;
  const isLive = stream_health === 'live';
  const isExpired = lifecycle_status === 'expired';
  const isStopped = lifecycle_status === 'stopped';
  const hasFactory = Boolean(active_factory_id);
  const hasState = stream_health !== 'awaiting_events' || hasFactory;

  return (
    <aside
      className="shrink-0 flex flex-col justify-between border-r border-[#1A2760]"
      style={{ width: '216px', background: '#031040', color: '#fff' }}
    >
      <div className="p-5 space-y-5">

        {/* ── Connection status pill ── */}
        <div className="inline-flex items-center gap-1.5 bg-[#2850B8] text-white text-xs font-semibold px-4 py-1.5 rounded-full">
          {isLive ? (
            <img src="/icons/simulation_status_connected.png" width={10} height={10} alt="live" />
          ) : (
            <span
              className={`w-2 h-2 rounded-full ${
                stream_health === 'stale' ? 'bg-amber-400' : hasFactory ? 'bg-emerald-400' : 'bg-[#4A5A8A]'
              }`}
            />
          )}
          <span className="text-[11px]">
            {isLive ? 'connected' : stream_health === 'stale' ? 'stale' : hasFactory ? 'connected' : 'connecting'}
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

          {isExpired ? (
            <button
              onClick={() => onSendCommand('restart', { start: true })}
              disabled={isCommandPending}
              className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded text-sm font-bold bg-[#2850B8] hover:bg-[#3460C8] text-white disabled:opacity-40 disabled:cursor-not-allowed transition"
            >
              <img src="/icons/simulation_controls_run.png" width={14} height={14} alt="Restart" />
              <span>{isCommandPending ? 'Starting…' : 'Restart'}</span>
            </button>
          ) : isStopped ? (
            <button
              onClick={() => onSendCommand('restart', { start: true })}
              disabled={isCommandPending}
              className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded text-sm font-bold bg-[#2850B8] hover:bg-[#3460C8] text-white disabled:opacity-40 disabled:cursor-not-allowed transition"
            >
              <img src="/icons/simulation_controls_run.png" width={14} height={14} alt="Restart" />
              <span>{isCommandPending ? 'Starting…' : 'Restart'}</span>
            </button>
          ) : (
            <div className="flex gap-2">
              <button
                onClick={() => onSendCommand(running ? 'stop' : 'start')}
                disabled={isCommandPending || !hasFactory}
                className="flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded text-sm font-bold bg-[#2850B8] hover:bg-[#3460C8] text-white disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                {running ? (
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
              {running && (
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
            <img src="/icons/clock.png" width={16} height={16} alt="clock" className="opacity-70" />
            <span>Sim time</span>
          </div>
          <div className="font-bold font-mono text-white text-xl tabular-nums tracking-tight">
            {hasState ? fmtSimTime(sim_time_minutes) : '--'}
          </div>
        </section>

        {/* ── Level selector ── */}
        <section>
          <label htmlFor="level-select" className="block text-sm font-bold text-[#8AA0D0] mb-2">
            Levels
          </label>
          <select
            id="level-select"
            value={levelId}
            onChange={(e) => onLevelChange(e.target.value)}
            className="w-full rounded border border-[#1A2760] bg-[#0A1A55] text-white text-sm font-bold px-3 py-2"
          >
            {LEVELS.map(({ id, label }) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
        </section>

      </div>

      <div className="border-t border-[#1A2760] px-5 py-3 text-[10px] text-[#4A5A8A]">
        Closing this app does not pause the hosted factory.
      </div>
    </aside>
  );
};

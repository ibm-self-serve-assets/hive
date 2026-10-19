/** Shape of the state object sent from the backend SSE stream. */
export interface DashboardState {
  stream_health: 'live' | 'stale' | 'awaiting_events';
  active_factory_id: string | null;
  run_generation: number;
  sim_time_minutes: number;
  lifecycle_status: 'paused' | 'running' | 'stopped' | 'expired';
  running: boolean;

  // Completed counts keyed by resource_id / station_id / output_id
  gathering_completed: Record<string, number>;
  manufacturing_completed: Record<string, number>;
  assembly_completed: Record<string, number>;

  // Active (in-progress) flags
  gathering_active: Record<string, boolean>;
  manufacturing_active: Record<string, boolean>;
  assembly_active: Record<string, boolean>;
}

export const EMPTY_STATE: DashboardState = {
  stream_health: 'awaiting_events',
  active_factory_id: null,
  run_generation: 0,
  sim_time_minutes: 0,
  lifecycle_status: 'paused',
  running: false,
  gathering_completed: {},
  manufacturing_completed: {},
  assembly_completed: {},
  gathering_active: {},
  manufacturing_active: {},
  assembly_active: {},
};

/**
 * Format sim_time_minutes as "Xd XXh XXm".
 * 1 real second = 1 sim minute, so sim_time_minutes counts real seconds elapsed.
 */
export function fmtSimTime(totalMin: number): string {
  const mins = Math.max(0, totalMin);
  const d = Math.floor(mins / (24 * 60));
  const h = Math.floor((mins % (24 * 60)) / 60);
  const m = mins % 60;
  return `${d}d ${String(h).padStart(2, '0')}h ${String(m).padStart(2, '0')}m`;
}

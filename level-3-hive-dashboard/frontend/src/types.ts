export interface StationJob {
  job_id: string;
  output_id: string;
  started_at_sim_ms: number;
  completes_at_sim_ms: number;
  duration_ms: number;
  consumed_inputs: Record<string, number>;
  progress_percent: number;
}

export interface StationState {
  station_id: string;
  status: 'idle' | 'working' | 'waiting_for_resources' | 'waiting_for_parts';
  missing_inputs: Record<string, number>;
  job: StationJob | null;
}

export interface ResourceDeliveryState {
  name: string;
  interval_sim_ms: number;
  next_delivery_sim_time_ms: number;
  next_delivery_in_ms: number;
  quantity: number;
}

export interface FactorySnapshot {
  lifecycle_status: 'paused' | 'running' | 'stopped' | 'expired';
  running: boolean;
  operational_error: { code: string; message: string } | null;
  speed: number;
  resource_deliveries: ResourceDeliveryState[];
  resources: Record<string, number>;
  parts: {
    chassis: number;
    electronics: number;
    actuator: number;
    battery: number;
  };
  stations: StationState[];
  completed_robots: {
    count: number;
    last_robot_id: string | null;
  };
  last_applied_command_id: string | null;
}

export interface ActivityEvent {
  event_id: string;
  event_type: string;
  occurred_at: string;
  sim_time_minutes: number;
  run_generation: number;
  event_sequence: number;
  summary: string;
  payload: Record<string, any>;
}

export interface ObservedState {
  stream_health: 'live' | 'stale' | 'awaiting_events';
  active_factory_id: string | null;
  server_epoch: string | null;
  run_generation: number;
  state_revision: number;
  latest_event_sequence: number;
  snapshot_occurred_at: string | null;
  snapshot: FactorySnapshot | null;
  sim_time_minutes: number;
  station_recipes: Record<string, Record<string, number>>;
  latest_command_receipt: {
    command: string;
    command_id: string;
    accepted: boolean;
    lifecycle_status: string;
    applied_at: string;
    status_label: string;
  } | null;
}

// Map of station_id → { resource/part_key → quantity } learned from manufacturing.started events
export type StationRecipes = Record<string, Record<string, number>>;

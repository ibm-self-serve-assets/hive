import React from 'react';
import { ActivityEvent } from '../types';

interface EventLogProps {
  events: ActivityEvent[];
}

// ── Bucketing ────────────────────────────────────────────────────────────────
type Bucket = 'resource' | 'manufacturing' | 'assembly';

function getBucket(eventType: string, payload?: Record<string, any>): Bucket {
  if (
    eventType === 'resource.delivered' ||
    eventType === 'resource.received'
  ) return 'resource';
  if (
    eventType === 'robot.assembled' ||
    eventType === 'assembly.started'
  ) return 'assembly';
  // worker_assembly events → assembly panel
  if (payload?.station_id === 'worker_assembly') return 'assembly';
  // part.produced, job.started (other stations), manufacturing.blocked → manufacturing
  return 'manufacturing';
}

// ── Detail formatters ────────────────────────────────────────────────────────
function formatDetails(ev: ActivityEvent): string {
  const p = ev.payload;
  switch (ev.event_type) {
    case 'resource.delivered': {
      const res = p.resources ?? {};
      const parts = Object.entries(res)
        .filter(([, v]) => (v as number) > 0)
        .map(([k, v]) => `${k.charAt(0).toUpperCase() + k.slice(1)} +${v}`)
        .join(', ');
      return parts || 'Delivery';
    }
    case 'part.produced':
      return `${p.part_id ? p.part_id.charAt(0).toUpperCase() + p.part_id.slice(1) : ''} +1`;
    case 'job.started':
      if (p.station_id === 'worker_assembly') {
        return `Worker assembly started`;
      }
      return `${(p.station_id ?? '').replace(/_/g, ' ')} → ${p.output_id ?? ''}`;
    case 'manufacturing.blocked': {
      const missing = p.missing_inputs ?? {};
      const items = Object.entries(missing)
        .map(([k, v]) => `${k} (need ${v})`)
        .join(', ');
      if (p.station_id === 'worker_assembly') {
        return `Waiting for parts: ${items}`;
      }
      return `${(p.station_id ?? '').replace(/_/g, ' ')}: ${items}`;
    }
    case 'robot.assembled':
      return `Worker W-${String(p.display_number ?? 0).padStart(3, '0')} added to inventory`;
    case 'assembly.started':
      return `Worker W-${String(p.display_number ?? 0).padStart(3, '0')}`;
    default:
      return ev.summary || ev.event_type;
  }
}

function formatTime(ev: ActivityEvent): string {
  // Always show simulation time (HH:MM:SS) so the clock matches the sim clock
  // in the sidebar — not the user's wall clock which is unrelated to the sim.
  const s = Math.floor(ev.sim_time_ms / 1000);
  const hh = String(Math.floor(s / 3600)).padStart(2, '0');
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  return `${hh}:${mm}:${ss}`;
}

// ── Per-bucket panel ─────────────────────────────────────────────────────────
interface PanelProps {
  title: string;
  events: ActivityEvent[];
  accentColor: string;
}

const Panel: React.FC<PanelProps> = ({ title, events, accentColor }) => (
  <div className="flex-1 min-w-0 bg-white rounded-lg border border-[#CCDDFF] overflow-hidden flex flex-col">
    {/* Title */}
    <div className="px-4 py-3 border-b border-[#E6EEFF]">
      <h3 className="font-bold text-sm" style={{ color: accentColor }}>{title}</h3>
    </div>

    {/* Rows */}
    <div className="divide-y divide-[#F0F4FF] overflow-y-auto" style={{ maxHeight: '200px' }}>
      {events.length === 0 ? (
        <div className="px-4 py-6 text-center text-xs text-[#8AA0D0] italic">
          No events yet.
        </div>
      ) : (
        events.map((ev) => {
          const isBlocked = ev.event_type === 'manufacturing.blocked';

          return (
            <div
              key={ev.event_id}
              className="flex items-start gap-3 px-4 py-2.5 hover:bg-[#F7FAFF]"
            >
              {/* Time — fixed width, vertically centered against the two lines on the right */}
              <span
                className="font-mono text-[11px] text-[#57606a] shrink-0 pt-px"
                style={{ width: '54px', lineHeight: '1.6' }}
              >
                {formatTime(ev)}
              </span>

              {/* Right column: event type + detail */}
              <div className="min-w-0 flex-1">
                <div
                  className="text-xs font-semibold leading-tight"
                  style={{ color: isBlocked ? '#B45309' : '#2850B8' }}
                >
                  {ev.event_type}
                </div>
                <div className="text-xs text-[#1f2328] mt-0.5 leading-tight">
                  {formatDetails(ev)}
                </div>
              </div>
            </div>
          );
        })
      )}
    </div>
  </div>
);

// ── Main component ────────────────────────────────────────────────────────────
export const EventLog: React.FC<EventLogProps> = ({ events }) => {
  const resourceEvents      = events.filter((e) => getBucket(e.event_type, e.payload) === 'resource');
  const manufacturingEvents = events.filter((e) => getBucket(e.event_type, e.payload) === 'manufacturing');
  const assemblyEvents      = events.filter((e) => getBucket(e.event_type, e.payload) === 'assembly');

  return (
    <div className="flex gap-4">
      <Panel title="Resource events"      events={resourceEvents}      accentColor="#2850B8" />
      <Panel title="Manufacturing events" events={manufacturingEvents} accentColor="#2850B8" />
      <Panel title="Assembly events"      events={assemblyEvents}      accentColor="#2850B8" />
    </div>
  );
};

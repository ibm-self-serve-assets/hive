import React, { useState } from 'react';
import { ActivityEvent } from '../types';

interface EventLogProps {
  events: ActivityEvent[];
}

// ── Bucketing ────────────────────────────────────────────────────────────────
export type Bucket = 'resource' | 'manufacturing' | 'assembly';

export function getBucket(eventType: string): Bucket {
  if (eventType.startsWith('resource.')) return 'resource';
  if (
    eventType === 'assembly.started' ||
    eventType === 'assembly.completed' ||
    eventType === 'assembly.blocked'
  ) return 'assembly';
  return 'manufacturing';
}

// ── Detail formatters ────────────────────────────────────────────────────────
const cap = (s?: string): string => (s ? s.charAt(0).toUpperCase() + s.slice(1) : '');

function formatDetails(ev: ActivityEvent): string {
  const p = ev.payload;
  switch (ev.event_type) {
    case 'resource.started':
      return `${cap(p.resource_id)} +${p.quantity ?? 0} in progress`;
    case 'resource.completed':
      return `${cap(p.resource_id)} +${p.quantity ?? 0} delivered`;
    case 'resource.blocked':
      return `${cap(p.resource_id)} blocked: ${p.reason ?? 'unknown'}`;
    case 'manufacturing.started':
      return `${(p.station_id ?? '').replace(/_/g, ' ')} → ${p.output_id ?? ''}`;
    case 'manufacturing.completed':
      return `${p.part_id ? p.part_id.charAt(0).toUpperCase() + p.part_id.slice(1) : ''} +1`;
    case 'manufacturing.blocked': {
      const missing = p.missing_inputs ?? {};
      const items = Object.entries(missing).map(([k, v]) => `${k} (need ${v})`).join(', ');
      return `${(p.station_id ?? '').replace(/_/g, ' ')}: ${items}`;
    }
    case 'assembly.started':
      return `${cap(p.robot_id)} in progress`;
    case 'assembly.completed':
      return `${cap(p.robot_id)} added to inventory`;
    case 'assembly.blocked': {
      const missing = p.missing_inputs ?? {};
      const items = Object.entries(missing).map(([k, v]) => `${k} (need ${v})`).join(', ');
      return `Waiting for parts: ${items}`;
    }
    default:
      return ev.summary || ev.event_type;
  }
}

/** Format sim_time_minutes as "Xd XXh XXm". */
function formatTime(ev: ActivityEvent): string {
  const mins = Math.max(0, ev.sim_time_minutes);
  const d = Math.floor(mins / (24 * 60));
  const h = Math.floor((mins % (24 * 60)) / 60);
  const m = mins % 60;
  return `${d}d ${String(h).padStart(2, '0')}h ${String(m).padStart(2, '0')}m`;
}

// ── Per-bucket panel ─────────────────────────────────────────────────────────
interface PanelProps {
  title: string;
  events: ActivityEvent[];
  accentColor: string;
  style?: React.CSSProperties;
}

export const Panel: React.FC<PanelProps> = ({ title, events, accentColor, style }) => {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div
      className="min-w-0 bg-white rounded-lg border border-[#CCDDFF] flex flex-col"
      style={{
        ...style,
        flex: style?.flex ?? '1 1 0',
        minHeight: 0,
        overflow: collapsed ? 'visible' : 'hidden',
        alignSelf: collapsed ? 'flex-start' : 'stretch',
      }}
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#E6EEFF] shrink-0 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <h3 className="font-bold text-sm truncate" style={{ color: accentColor }}>{title}</h3>
          <span
            className="text-xs font-semibold tabular-nums px-1.5 py-0.5 rounded"
            style={{ background: '#EEF3FF', color: accentColor }}
          >
            {events.length}
          </span>
        </div>
        <button
          onClick={() => setCollapsed((c) => !c)}
          title={collapsed ? 'Expand' : 'Collapse'}
          className="shrink-0 flex items-center justify-center rounded hover:bg-[#EEF3FF] transition-colors"
          style={{ width: 22, height: 22, border: 'none', background: 'none', cursor: 'pointer', color: '#57606a' }}
        >
          {/* Chevron — points up when expanded, down when collapsed */}
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path
              d={collapsed ? 'M2 4l4 4 4-4' : 'M2 8l4-4 4 4'}
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>

      {/* Rows — only rendered when expanded */}
      {!collapsed && (
        <div className="divide-y divide-[#F0F4FF] overflow-y-auto flex-1 min-h-0">
          {events.length === 0 ? (
            <div className="px-4 py-6 text-center text-xs text-[#8AA0D0] italic">
              No events yet.
            </div>
          ) : (
            events.map((ev) => {
              const isBlocked = ev.event_type.endsWith('.blocked');
              return (
                <div
                  key={ev.event_id}
                  className="flex items-start gap-3 px-4 py-2.5 hover:bg-[#F7FAFF]"
                >
                  <span
                    className="font-mono text-[11px] text-[#57606a] shrink-0 pt-px"
                    style={{ width: '54px', lineHeight: '1.6' }}
                  >
                    {formatTime(ev)}
                  </span>
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
      )}
    </div>
  );
};

// ── Main component ────────────────────────────────────────────────────────────
export const EventLog: React.FC<EventLogProps> = ({ events }) => {
  const resourceEvents      = events.filter((e) => getBucket(e.event_type) === 'resource');
  const manufacturingEvents = events.filter((e) => getBucket(e.event_type) === 'manufacturing');
  const assemblyEvents      = events.filter((e) => getBucket(e.event_type) === 'assembly');

  return (
    <div className="flex gap-4 flex-1 min-h-0" style={{ alignItems: 'flex-start' }}>
      <Panel title="Resource events"      events={resourceEvents}      accentColor="#2850B8" />
      <Panel title="Manufacturing events" events={manufacturingEvents} accentColor="#2850B8" />
      <Panel title="Assembly events"      events={assemblyEvents}      accentColor="#2850B8" />
    </div>
  );
};

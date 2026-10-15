import React, { useEffect, useState } from 'react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { ManufacturingFloor } from './components/ManufacturingFloor';
import { ObservedState, ActivityEvent, FactorySnapshot } from './types';

export const App: React.FC = () => {
  const [observedState, setObservedState] = useState<ObservedState>({
    stream_health: 'awaiting_events',
    active_factory_id: null,
    server_epoch: null,
    run_generation: 0,
    state_revision: 0,
    latest_event_sequence: 0,
    snapshot_occurred_at: null,
    snapshot: null,
    sim_time_ms: 0,
    station_recipes: {},
    latest_command_receipt: null,
  });

  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [csrfToken, setCsrfToken] = useState<string>('');
  const [connectError, setConnectError] = useState<string | null>(null);
  const [isCommandPending, setIsCommandPending] = useState(false);
  const [level, setLevel] = useState<number>(1);

  // On startup: fetch CSRF token and check for missing .env credentials.
  // The backend auto-connects to the sim server on its own startup —
  // the UI just opens the SSE stream and receives state as it arrives.
  useEffect(() => {
    const initApp = async () => {
      try {
        const csrfRes = await fetch('/api/csrf');
        if (!csrfRes.ok) return;
        const { csrf_token } = await csrfRes.json();
        setCsrfToken(csrf_token);

        const configRes = await fetch('/api/config');
        if (!configRes.ok) return;
        const cfg = await configRes.json();
        if (!cfg.fully_configured) {
          setConnectError('Missing credentials in .env — check WORKSHOP_ACCESS_TOKEN, CONFLUENT_BOOTSTRAP_SERVER, CONFLUENT_API_KEY / SECRET.');
        }
      } catch (err) {
        console.error('Init failed:', err);
      }
    };
    initApp();
  }, []);

  // SSE Stream Listener
  useEffect(() => {
    const eventSource = new EventSource('/api/stream');

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'init') {
          if (data.observed_state) {
            setObservedState({ ...data.observed_state, sim_time_ms: data.observed_state.sim_time_ms ?? 0 });
          }
          if (data.events) {
            // Sort newest-first by event_sequence on init so order is stable
            const sorted = [...(data.events as ActivityEvent[])]
              .sort((a, b) => b.event_sequence - a.event_sequence);
            setEvents(sorted);
          }
        } else if (data.type === 'heartbeat') {
          if (data.observed_state) setObservedState((prev) => ({
            ...prev,
            ...data.observed_state,
            sim_time_ms: data.observed_state?.sim_time_ms ?? prev.sim_time_ms ?? 0,
          }));
          // Heartbeat carries the authoritative store log (newest-first, up to 200).
          // Use it as the source of truth — sort by event_sequence descending so the
          // list is stable and never flashes or loses events due to merge races.
          if (data.events?.length) {
            const authoritative: ActivityEvent[] = (data.events as any[])
              .map((e: any) => ({
                event_id: e.event_id,
                event_type: e.event_type,
                occurred_at: e.occurred_at,
                sim_time_ms: e.sim_time_ms,
                run_generation: e.run_generation,
                event_sequence: e.event_sequence,
                summary: e.summary ?? e.event_type,
                payload: e.payload,
              }))
              .sort((a: ActivityEvent, b: ActivityEvent) => b.event_sequence - a.event_sequence);
            setEvents(authoritative);
          }
        } else if (data.type === 'command_receipt') {
          setObservedState((prev) => ({
            ...prev,
            latest_command_receipt: data.receipt,
          }));
        } else if (data.event_type === 'factory.state') {
          // Direct snapshot event — sim_time_ms is the top-level envelope field
          setObservedState((prev) => ({
            ...prev,
            stream_health: 'live',
            run_generation: data.run_generation,
            state_revision: data.state_revision,
            latest_event_sequence: data.event_sequence,
            snapshot_occurred_at: data.occurred_at,
            snapshot: data.payload as FactorySnapshot,
            sim_time_ms: typeof data.sim_time_ms === 'number' ? data.sim_time_ms : prev.sim_time_ms,
          }));
        } else if (data.event_type) {
          // Skip factory.state — handled above
          if (data.event_type === 'factory.state') return;
          // Insert into the events list at the correct position by event_sequence,
          // so the list stays stably sorted and doesn't jump on heartbeat replace.
          setEvents((prev) => {
            if (prev.some((e) => e.event_id === data.event_id)) return prev;
            const next = [
              ...prev,
              {
                event_id: data.event_id,
                event_type: data.event_type,
                occurred_at: data.occurred_at,
                sim_time_ms: data.sim_time_ms,
                run_generation: data.run_generation,
                event_sequence: data.event_sequence,
                summary: data.event_type,
                payload: data.payload,
              },
            ]
              .sort((a, b) => b.event_sequence - a.event_sequence)
              .slice(0, 1000);
            return next;
          });
        }
      } catch (e) {
        console.error('SSE parse error:', e);
      }
    };

    eventSource.onerror = () => {
      setObservedState((prev) => ({
        ...prev,
        stream_health: 'stale',
      }));
    };

    return () => {
      eventSource.close();
    };
  }, []);

  const handleSendCommand = async (command: string, extra?: any) => {
    // csrfToken may be set after mount; read from state
    setIsCommandPending(true);
    try {
      const res = await fetch('/api/controls', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
        },
        body: JSON.stringify({
          command,
          expected_generation: observedState.run_generation || 1,
          ...extra,
        }),
      });

      if (!res.ok) {
        let msg = 'Error';
        try {
          const err = await res.json();
          const detail = err?.detail;
          if (typeof detail === 'object' && detail !== null) {
            msg = detail.message || detail.error_code || JSON.stringify(detail);
          } else if (typeof detail === 'string') {
            msg = detail;
          } else {
            msg = err?.message || JSON.stringify(err);
          }
        } catch {
          msg = (await res.text()) || `HTTP ${res.status}`;
        }
        alert(`Command rejected (${res.status}): ${msg}`);
      }
    } catch (e: any) {
      alert(`Command network failure: ${e.message}`);
    } finally {
      setIsCommandPending(false);
    }
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ background: '#F4F7FC' }}>
      <Header />

      {connectError && (
        <div className="mx-6 mt-3 p-3 bg-red-50 border border-red-200 text-red-700 rounded text-xs shrink-0">
          {connectError}
        </div>
      )}

      <div className="flex-1 min-h-0 flex overflow-hidden">
        <Sidebar
          streamHealth={observedState.stream_health}
          level={level}
          onLevelChange={setLevel}
          snapshot={observedState.snapshot}
          simTimeMs={observedState.sim_time_ms}
          commandReceipt={observedState.latest_command_receipt}
          onSendCommand={handleSendCommand}
          isCommandPending={isCommandPending}
        />

        <main className="flex-1 min-h-0 flex flex-col min-w-0 overflow-hidden">
          <ManufacturingFloor
            snapshot={observedState.snapshot}
            isRunning={observedState.snapshot?.running ?? false}
            stationRecipes={observedState.station_recipes}
            events={events}
            level={level}
          />
        </main>
      </div>
    </div>
  );
};

export default App;

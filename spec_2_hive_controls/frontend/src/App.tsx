import React, { useEffect, useState } from 'react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { ManufacturingFloor } from './components/ManufacturingFloor';
import { EventLog } from './components/EventLog';
import { ConnectionModal } from './components/ConnectionModal';
import { ObservedState, ActivityEvent, FactorySnapshot, StationRecipes } from './types';

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
    latest_command_receipt: null,
  });

  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [stationRecipes, setStationRecipes] = useState<StationRecipes>({});
  const [csrfToken, setCsrfToken] = useState<string>('');
  const [isConnectOpen, setIsConnectOpen] = useState(false);
  const [isCommandPending, setIsCommandPending] = useState(false);
  const [serverUrl, setServerUrl] = useState('http://localhost:8080');

  // Fetch initial CSRF & Status
  useEffect(() => {
    const initApp = async () => {
      try {
        const csrfRes = await fetch('/api/csrf');
        if (csrfRes.ok) {
          const data = await csrfRes.json();
          setCsrfToken(data.csrf_token);
        }

        const statusRes = await fetch('/api/status');
        if (statusRes.ok) {
          const sData = await statusRes.json();
          if (sData.observed_state) {
            setObservedState(sData.observed_state);
          }
          if (sData.simulation_server_url) {
            setServerUrl(sData.simulation_server_url);
          }
          if (!sData.active_factory_id) {
            setIsConnectOpen(true);
          }
        }
      } catch (err) {
        console.error('Initial status load failed:', err);
      }
    };

    initApp();
  }, []);

  // Helper: absorb recipe inputs from a job.started payload
  const absorbRecipe = (payload: Record<string, any>) => {
    const stId: string = payload?.station_id;
    const inputs: Record<string, number> = payload?.inputs;
    if (stId && inputs && Object.keys(inputs).length > 0) {
      setStationRecipes((prev) => {
        if (JSON.stringify(prev[stId]) === JSON.stringify(inputs)) return prev;
        return { ...prev, [stId]: inputs };
      });
    }
  };

  // SSE Stream Listener
  useEffect(() => {
    const eventSource = new EventSource('/api/stream');

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'init') {
          if (data.observed_state) setObservedState(data.observed_state);
          if (data.events) {
            // Sort newest-first by event_sequence on init so order is stable
            const sorted = [...(data.events as ActivityEvent[])]
              .sort((a, b) => b.event_sequence - a.event_sequence);
            setEvents(sorted);
            sorted.forEach((ev) => {
              if (ev.event_type === 'job.started') absorbRecipe(ev.payload);
            });
          }
        } else if (data.type === 'heartbeat') {
          if (data.observed_state) setObservedState((prev) => ({
            ...prev,
            ...data.observed_state,
            sim_time_ms: data.observed_state?.snapshot?.sim_time_ms ?? prev.sim_time_ms,
          }));
          // Heartbeat carries the authoritative store log (newest-first, up to 200).
          // Use it as the source of truth — sort by event_sequence descending so the
          // list is stable and never flashes or loses events due to merge races.
          if (data.events?.length) {
            (data.events as any[]).forEach((e) => {
              if (e.event_type === 'job.started') absorbRecipe(e.payload);
            });
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
          // Absorb recipe from job.started
          if (data.event_type === 'job.started') absorbRecipe(data.payload);
          // Skip factory.state — it only updates observedState above, not the event list
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
              .slice(0, 200);
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

  const handleConnect = async (formData: any) => {
    const res = await fetch('/api/connect', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrfToken,
      },
      body: JSON.stringify(formData),
    });

    if (!res.ok) {
      let message = 'Failed to connect';
      try {
        const err = await res.json();
        const detail = err?.detail;
        if (typeof detail === 'object' && detail !== null) {
          message = detail.message || detail.error_code || JSON.stringify(detail);
        } else if (typeof detail === 'string') {
          message = detail;
        } else {
          message = err?.message || JSON.stringify(err);
        }
      } catch {
        message = (await res.text()) || `Server error (${res.status})`;
      }
      throw new Error(message);
    }

    const data = await res.json();
    setObservedState((prev) => ({
      ...prev,
      active_factory_id: data.factory_id,
      server_epoch: data.server_epoch,
    }));
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#F4F7FC' }}>
      <Header
        streamHealth={observedState.stream_health}
        factoryId={observedState.active_factory_id}
        onOpenConnect={() => setIsConnectOpen(true)}
      />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          snapshot={observedState.snapshot}
          simTimeMs={observedState.sim_time_ms}
          commandReceipt={observedState.latest_command_receipt}
          onSendCommand={handleSendCommand}
          isCommandPending={isCommandPending}
        />

        <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
          <ManufacturingFloor
            snapshot={observedState.snapshot}
            isRunning={observedState.snapshot?.running ?? false}
            stationRecipes={stationRecipes}
          />
          <div className="px-6 pb-6">
            <EventLog events={events} />
          </div>
        </main>
      </div>

      <ConnectionModal
        isOpen={isConnectOpen}
        onClose={() => setIsConnectOpen(false)}
        onConnect={handleConnect}
        initialServerUrl={serverUrl}
        initialProfileId="workshop-cluster"
      />
    </div>
  );
};

export default App;

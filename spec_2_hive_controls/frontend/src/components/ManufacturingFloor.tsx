import React from 'react';
import { FactorySnapshot, StationState, StationRecipes } from '../types';
import { FlowDots } from './FlowDots';

// ── Delivery spinner ──────────────────────────────────────────────────────────
// SVG circular progress ring that sweeps from full (just delivered) to empty
// (next delivery imminent), matching the comp design.
const DeliverySpinner: React.FC<{ fraction: number }> = ({ fraction }) => {
  const size = 28;
  const stroke = 3.5;
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  // fraction=1 → full ring (just delivered), fraction=0 → empty (due now)
  const dashoffset = circ * (1 - fraction);

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0" style={{ transform: 'rotate(-90deg)' }}>
      {/* Track */}
      <circle
        cx={size / 2} cy={size / 2} r={r}
        fill="none"
        stroke="#DDEEFF"
        strokeWidth={stroke}
      />
      {/* Progress arc */}
      <circle
        cx={size / 2} cy={size / 2} r={r}
        fill="none"
        stroke="#2850B8"
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={dashoffset}
        style={{ transition: 'stroke-dashoffset 0.5s linear' }}
      />
    </svg>
  );
};


const RESOURCE_ICONS: Record<string, { src: string; w: number; h: number }> = {
  resin:   { src: '/icons/resources__resin__droplet.png',    w: 32, h: 36 },
  silicon: { src: '/icons/resources__silicon__chip.png',     w: 35, h: 33 },
  metals:  { src: '/icons/resources__metals__ingots.png',    w: 33, h: 32 },
  copper:  { src: '/icons/resources__copper__stack.png',     w: 33, h: 37 },
  energy:  { src: '/icons/resources__energy__lightning.png', w: 34, h: 36 },
};

// Static fallback recipes (mirrors simulation_rules.json) used before any job.started event arrives
const DEFAULT_RECIPES: StationRecipes = {
  structural_molding:   { resin: 1, metals: 1 },
  electronics_assembly: { silicon: 1, copper: 1 },
  actuator_fabrication: { metals: 1, copper: 1 },
  battery_assembly:     { energy: 1, copper: 1, metals: 1 },
};

const STATION_IMGS: Record<string, string> = {
  structural_molding:   '/icons/parts-manufacturing__structural-molding__chassis.png',
  electronics_assembly: '/icons/parts-manufacturing__electronics-assembly__board.png',
  actuator_fabrication: '/icons/parts-manufacturing__actuator-fabrication__servo.png',
  battery_assembly:     '/icons/parts-manufacturing__battery-assembly__battery.png',
};

const STATION_LABELS: Record<string, string> = {
  structural_molding:   'Structural molding',
  electronics_assembly: 'Electronics assembly',
  actuator_fabrication: 'Actuator fabrication',
  battery_assembly:     'Battery assembly',
};

const STATION_ORDER = [
  'structural_molding',
  'electronics_assembly',
  'actuator_fabrication',
  'battery_assembly',
];

const PART_INVENTORY: Array<{ key: keyof FactorySnapshot['parts']; label: string; src: string }> = [
  { key: 'chassis',     label: 'Chassis',     src: '/icons/parts-inventory__chassis__head-shell.png' },
  { key: 'electronics', label: 'Electronics', src: '/icons/parts-inventory__electronics__board.png' },
  { key: 'battery',     label: 'Batteries',   src: '/icons/parts-inventory__batteries__battery.png' },
  { key: 'actuator',    label: 'Actuators',   src: '/icons/parts-inventory__actuators__servo.png' },
];

interface StationRowProps {
  stationId: string;
  station: StationState | undefined;
  inputs: Record<string, number>;
}

const StationRow: React.FC<StationRowProps> = ({ stationId, station, inputs }) => {
  const progress = station?.job?.progress_percent ?? 0;
  const isWaiting = station?.status === 'waiting_for_resources' || station?.status === 'waiting_for_parts';
  const isBlocked = station?.status === 'waiting_for_resources';

  return (
    <div className="flex items-center gap-3 py-3 border-b border-[#E6EEFF] last:border-b-0">
      <div className="w-16 h-12 shrink-0 rounded bg-white flex items-center justify-center overflow-hidden">
        <img
          src={STATION_IMGS[stationId]}
          alt={STATION_LABELS[stationId]}
          className="max-w-full max-h-full object-contain"
          style={{ maxWidth: '56px', maxHeight: '44px' }}
        />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-sm text-[#031040]">{STATION_LABELS[stationId]}</span>
            {isBlocked && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-semibold shrink-0"
                style={{ background: '#FFF3E0', border: '1px solid #F59E0B', color: '#B45309' }}>
                <img src="/icons/parts-manufacturing__shortage__warning.png" alt="warning" width={12} height={12} style={{ display: 'inline' }} />
                Shortage
              </span>
            )}
          </div>
          <span className="text-sm font-bold text-[#031040] tabular-nums ml-2">{Math.round(progress)}%</span>
        </div>
        <div className="w-full h-3 bg-[#E6EEFF] rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-300"
            style={{ width: `${progress}%`, background: isWaiting ? '#D36B00' : '#2850B8' }}
          />
        </div>
        {/* Resource inputs row */}
        <div className="resource-input flex items-center gap-2 mt-1.5 flex-wrap">
          {Object.entries(inputs).map(([res, qty], i) => {
            const ico = RESOURCE_ICONS[res];
            return (
              <React.Fragment key={res}>
                {i > 0 && <span style={{ color: '#9aa3b0' }}>+</span>}
                {ico ? (
                  <img src={ico.src} alt={res} style={{ width: 20, height: 20, objectFit: 'contain', filter: 'grayscale(100%)' }} />
                ) : (
                  <span className="capitalize">{res}</span>
                )}
                <span>×{qty}</span>
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );
};

interface ManufacturingFloorProps {
  snapshot: FactorySnapshot | null;
  isRunning: boolean;
  stationRecipes: StationRecipes;
}

export const ManufacturingFloor: React.FC<ManufacturingFloorProps> = ({ snapshot, isRunning, stationRecipes }) => {
  const resources = snapshot?.resources ?? { resin: 0, silicon: 0, metals: 0, copper: 0, energy: 0 };
  const parts = snapshot?.parts ?? { chassis: 0, electronics: 0, actuator: 0, battery: 0 };
  const stations = snapshot?.stations ?? [];
  const completedWorkers = snapshot?.completed_workers?.count ?? 0;

  const nextDeliveryMs = snapshot?.next_delivery_in_ms ?? 0;
  const nextDeliverySec = Math.max(0, Math.ceil(nextDeliveryMs / 1000));
  const ndMM = String(Math.floor(nextDeliverySec / 60)).padStart(2, '0');
  const ndSS = String(nextDeliverySec % 60).padStart(2, '0');

  // Spinner fraction: how much of the delivery cycle is remaining (1 = just delivered, 0 = due now).
  // The delivery interval is fixed at 20 sim-seconds = 20,000 ms.
  const DELIVERY_INTERVAL_MS = 20_000;
  const spinnerFraction = Math.min(1, Math.max(0, nextDeliveryMs / DELIVERY_INTERVAL_MS));

  const getStation = (id: string): StationState | undefined =>
    stations.find((s) => s.station_id === id);

  const workerStation = getStation('worker_assembly');
  const workerProgress = workerStation?.job?.progress_percent ?? 0;
  const workerIsWorking = workerStation?.status === 'working';
  const inProgressLabel = `Worker W-${String(completedWorkers + 1).padStart(3, '0')}`;

  return (
    <div className="flex-1 p-6">
      {/* 3 columns with FlowDots connectors between them */}
      <div className="flex items-stretch gap-0">

        {/* ── Column 1: Resources ── */}
        <div className="bg-white rounded-lg border border-[#CCDDFF] p-5 flex flex-col" style={{ flex: '1 1 0' }}>
          <h3 className="font-bold text-[#2850B8] text-base mb-1">Resources</h3>
          <div className="flex-1 divide-y divide-[#F0F4FF]">
            {(['resin', 'silicon', 'metals', 'copper', 'energy'] as const).map((res) => {
              const ico = RESOURCE_ICONS[res];
              return (
                <div key={res} className="flex items-center gap-3 py-3">
                  <div className="w-10 flex items-center justify-center shrink-0">
                    <img src={ico.src} width={ico.w} height={ico.h} alt={res} />
                  </div>
                  <span className="flex-1 text-sm text-[#031040] capitalize">{res}</span>
                  <span className="text-lg font-bold text-[#031040] tabular-nums">{resources[res]}</span>
                </div>
              );
            })}
          </div>

          {/* Next delivery footer */}
          <div className="mt-3 pt-3 border-t border-[#E6EEFF] flex items-center gap-2">
            <DeliverySpinner fraction={spinnerFraction} />
            <span className="text-sm text-[#57606a]">Next delivery</span>
            <span className="ml-auto font-bold font-mono text-[#031040] text-base tabular-nums">
              {snapshot ? `${ndMM}:${ndSS}` : '--:--'}
            </span>
          </div>
        </div>

        {/* ── FlowDots: Resources → Parts ── */}
        <div className="flex items-center justify-center px-1 shrink-0">
          <FlowDots running={isRunning} color="#2850B8" />
        </div>

        {/* ── Column 2: Parts manufacturing + Parts inventory ── */}
        <div className="bg-white rounded-lg border border-[#CCDDFF] p-5 flex flex-col gap-5" style={{ flex: '1 1 0' }}>
          <div>
            <h3 className="font-bold text-[#2850B8] text-base mb-1">Parts manufacturing</h3>
            <div>
              {STATION_ORDER.map((stId) => {
                const inputs = stationRecipes[stId] ?? DEFAULT_RECIPES[stId] ?? {};
                return (
                  <StationRow key={stId} stationId={stId} station={getStation(stId)} inputs={inputs} />
                );
              })}
            </div>
          </div>

          <div>
            <h4 className="font-bold text-[#031040] text-sm mb-3">Parts inventory</h4>
            <div className="grid grid-cols-4 gap-2">
              {PART_INVENTORY.map(({ key, label, src }) => (
                <div key={key} className="flex flex-col items-center gap-1 p-2 rounded-lg border border-[#E6EEFF] bg-[#F7FAFF]">
                  <div className="h-12 flex items-center justify-center">
                    <img src={src} alt={label} className="max-h-10 max-w-full object-contain" />
                  </div>
                  <span className="text-[11px] text-[#57606a] text-center leading-tight">{label}</span>
                  <span className="text-lg font-bold text-[#031040] tabular-nums">{parts[key] ?? 0}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── FlowDots: Parts → Robot assembly ── */}
        <div className="flex items-center justify-center px-1 shrink-0">
          <FlowDots running={isRunning} color="#2850B8" />
        </div>

        {/* ── Column 3: Robot assembly ── */}
        <div className="bg-white rounded-lg border border-[#CCDDFF] p-5 flex flex-col gap-5" style={{ flex: '1 1 0' }}>
          <h3 className="font-bold text-[#031040] text-base">Robot assembly</h3>

          <div className="rounded-lg border border-[#CCDDFF] p-4">
            <div className="flex items-start gap-3 mb-3">
              <div className="shrink-0 w-20 flex items-center justify-center">
                <img src="/icons/robot-assembly__worker__bee.png" alt="worker bee" className="w-20 object-contain" />
              </div>
              <div className="flex-1 min-w-0 pt-1">
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <span className="font-bold text-[#031040] text-sm">
                    {workerIsWorking ? inProgressLabel : 'Worker Assembly'}
                  </span>
                  {workerStation?.status === 'waiting_for_parts' && (
                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-semibold shrink-0"
                      style={{ background: '#FFF3E0', border: '1px solid #F59E0B', color: '#B45309' }}>
                      <img src="/icons/parts-manufacturing__shortage__warning.png" alt="warning" width={12} height={12} style={{ display: 'inline' }} />
                      Shortage
                    </span>
                  )}
                </div>
                <div className="w-full h-3 bg-[#E6EEFF] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#2850B8] rounded-full transition-all duration-300"
                    style={{ width: `${workerProgress}%` }}
                  />
                </div>
                <div className="flex justify-end mt-1">
                  <span className="text-sm font-bold text-[#031040] tabular-nums">{Math.round(workerProgress)}%</span>
                </div>
                {workerIsWorking && (
                  <div className="text-xs text-[#57606a] mt-1">Assembly in progress</div>
                )}
              </div>
            </div>
            {!workerIsWorking && workerStation?.status !== 'waiting_for_parts' && (
              <div className="text-xs text-[#57606a]">
                Idle — awaiting parts
              </div>
            )}
            {workerStation?.status === 'waiting_for_parts' && (
              <div className="text-xs text-[#57606a]">
                Next build starts when parts are available
              </div>
            )}
          </div>

          <div>
            <h4 className="font-bold text-[#031040] text-sm mb-3">Assembled bee inventory</h4>
            <div className="rounded-lg border border-[#CCDDFF] p-4 flex items-center gap-4">
              <img src="/icons/assembled-bee-inventory__worker__bee.png" alt="assembled worker" className="w-16 object-contain shrink-0" />
              <div>
                <div className="text-sm font-semibold text-[#031040]">Worker</div>
                <div className="text-4xl font-bold text-[#031040] tabular-nums leading-tight">{completedWorkers}</div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

import React from 'react';
import { FactorySnapshot, StationState, StationRecipes, ResourceDeliveryState } from '../types';
import { FlowDots } from './FlowDots';

// ── Segmented delivery donut ───────────────────────────────────────────────────
// 10-segment donut showing time until next delivery for a single resource.
// Segments fill from the top clockwise; filled = remaining fraction of interval.
const DONUT_SEGMENTS = 10;
const DONUT_SIZE = 44;
const DONUT_CX = DONUT_SIZE / 2;
const DONUT_CY = DONUT_SIZE / 2;
const DONUT_OUTER_R = 20;
const DONUT_INNER_R = 13;
const SEGMENT_GAP_DEG = 4;
const SEGMENT_ANGLE = (360 - DONUT_SEGMENTS * SEGMENT_GAP_DEG) / DONUT_SEGMENTS;

// Pre-compute arc paths once at module load — they never change
const SEGMENT_PATHS: string[] = Array.from({ length: DONUT_SEGMENTS }, (_, i) => {
  const startDeg = i * (SEGMENT_ANGLE + SEGMENT_GAP_DEG);
  const endDeg = startDeg + SEGMENT_ANGLE;
  const toXY = (deg: number, r: number) => {
    const rad = ((deg - 90) * Math.PI) / 180;
    return { x: DONUT_CX + r * Math.cos(rad), y: DONUT_CY + r * Math.sin(rad) };
  };
  const o1 = toXY(startDeg, DONUT_OUTER_R), o2 = toXY(endDeg, DONUT_OUTER_R);
  const i1 = toXY(endDeg, DONUT_INNER_R),  i2 = toXY(startDeg, DONUT_INNER_R);
  const large = endDeg - startDeg > 180 ? 1 : 0;
  return `M ${o1.x} ${o1.y} A ${DONUT_OUTER_R} ${DONUT_OUTER_R} 0 ${large} 1 ${o2.x} ${o2.y} L ${i1.x} ${i1.y} A ${DONUT_INNER_R} ${DONUT_INNER_R} 0 ${large} 0 ${i2.x} ${i2.y} Z`;
});

const DeliveryDonut: React.FC<{ delivery: ResourceDeliveryState; quantity: number }> = ({ delivery, quantity }) => {
  // fraction = how much of the interval remains (1 = just delivered, 0 = due now)
  const fraction = delivery.interval_sim_ms > 0
    ? Math.min(1, Math.max(0, delivery.next_delivery_in_ms / delivery.interval_sim_ms))
    : 1; // no snapshot yet → show full ring

  // Discrete segments — Math.round so tiny float noise doesn't toggle a segment
  const filledSegments = Math.round(fraction * DONUT_SEGMENTS);

  return (
    // Relative wrapper lets us overlay the HTML label without SVG <text> reflow
    <div className="relative shrink-0" style={{ width: DONUT_SIZE, height: DONUT_SIZE }}>
      <svg width={DONUT_SIZE} height={DONUT_SIZE} viewBox={`0 0 ${DONUT_SIZE} ${DONUT_SIZE}`}>
        {SEGMENT_PATHS.map((d, i) => (
          <path key={i} d={d} fill={i >= DONUT_SEGMENTS - filledSegments ? '#2850B8' : '#DDEEFF'} />
        ))}
      </svg>
      {/* HTML label: no font-layout reflow, no bounce */}
      <div
        className="absolute inset-0 flex items-center justify-center"
        style={{ fontSize: 10, fontWeight: 700, color: '#031040', pointerEvents: 'none' }}
      >
        +{quantity}
      </div>
    </div>
  );
};


const RESOURCE_ICONS: Record<string, { src: string; w: number; h: number }> = {
  resin:   { src: '/icons/resources__resin__droplet.png',    w: 32, h: 36 },
  silicon: { src: '/icons/resources__silicon__chip.png',     w: 35, h: 33 },
  metals:  { src: '/icons/resources__metals__ingots.png',    w: 33, h: 32 },
  copper:  { src: '/icons/resources__copper__stack.png',     w: 33, h: 37 },
  energy:  { src: '/icons/resources__energy__lightning.png', w: 34, h: 36 },
};

const PART_ICONS: Record<string, string> = {
  chassis:     '/icons/parts-inventory__chassis__head-shell.png',
  electronics: '/icons/parts-inventory__electronics__board.png',
  battery:     '/icons/parts-inventory__batteries__battery.png',
  actuator:    '/icons/parts-inventory__actuators__servo.png',
};

const STATION_IMGS: Record<string, string> = {
  structural_molding:   '/icons/parts-manufacturing__structural-molding__chassis.png',
  electronics_assembly: '/icons/parts-manufacturing__electronics-assembly__board.png',
  actuator_fabrication: '/icons/parts-manufacturing__actuator-fabrication__servo.png',
  battery_assembly:     '/icons/parts-manufacturing__battery-assembly__battery.png',
};

const PART_INVENTORY: Array<{ key: string; label: string; src: string }> = [
  { key: 'chassis',     label: 'Chassis',     src: '/icons/parts-inventory__chassis__head-shell.png' },
  { key: 'electronics', label: 'Electronics', src: '/icons/parts-inventory__electronics__board.png' },
  { key: 'battery',     label: 'Batteries',   src: '/icons/parts-inventory__batteries__battery.png' },
  { key: 'actuator',    label: 'Actuators',   src: '/icons/parts-inventory__actuators__servo.png' },
];

// ── Progress donut shared by parts manufacturing and robot assembly ────────────
// Same 10-segment geometry as DeliveryDonut but driven by job progress_percent.
const PROG_PATHS = SEGMENT_PATHS; // reuse precomputed arcs

const ProgressDonut: React.FC<{
  progress: number;       // 0–100
  isBlocked: boolean;
  label: string;          // centre label e.g. "64%"
}> = ({ progress, isBlocked, label }) => {
  const filled = Math.round((progress / 100) * DONUT_SEGMENTS);
  const activeColor = isBlocked ? '#D36B00' : '#2850B8';
  return (
    <div className="relative shrink-0" style={{ width: DONUT_SIZE, height: DONUT_SIZE }}>
      <svg width={DONUT_SIZE} height={DONUT_SIZE} viewBox={`0 0 ${DONUT_SIZE} ${DONUT_SIZE}`}>
        {PROG_PATHS.map((d, i) => (
          <path key={i} d={d} fill={i < filled ? activeColor : '#DDEEFF'} />
        ))}
      </svg>
      <div
        className="absolute inset-0 flex items-center justify-center"
        style={{ fontSize: 9, fontWeight: 700, color: isBlocked ? '#D36B00' : '#031040', pointerEvents: 'none' }}
      >
        {label}
      </div>
    </div>
  );
};

// ── Inputs chip row ────────────────────────────────────────────────────────────
const InputRow: React.FC<{
  inputs: Record<string, number>;
  missingInputs: Record<string, number>;
  iconMap: Record<string, { src: string; w: number; h: number } | string>;
  large?: boolean;  // larger icons for robot assembly bottom row
}> = ({ inputs, missingInputs, iconMap, large }) => (
  <div className="flex items-center gap-2 flex-wrap" style={{ marginTop: large ? 0 : 6 }}>
    {Object.entries(inputs).map(([key, qty], i) => {
      const isShort = key in missingInputs;
      const ico = iconMap[key];
      const src = typeof ico === 'string' ? ico : ico?.src;
      const iconSize = large ? 36 : 18;
      return (
        <React.Fragment key={key}>
          {i > 0 && <span style={{ color: '#9aa3b0', fontSize: large ? 14 : 11 }}>+</span>}
          {src
            ? <img src={src} alt={key} style={{ width: iconSize, height: iconSize, objectFit: 'contain', filter: 'grayscale(100%)' }} />
            : <span className="text-xs capitalize">{key}</span>
          }
          <span style={{ fontSize: large ? 13 : 11, color: isShort ? '#D36B00' : undefined, fontWeight: isShort ? 600 : undefined }}>×{qty}</span>
        </React.Fragment>
      );
    })}
  </div>
);

// ── Station row: donut + label + shortage + input chips ────────────────────────
interface StationRowProps {
  stationId: string;
  station: StationState | undefined;
  inputs: Record<string, number>;
}

const StationRow: React.FC<StationRowProps> = ({ stationId, station, inputs }) => {
  const progress = station?.job?.progress_percent ?? 0;
  const isBlocked = station?.status === 'waiting_for_resources';
  const missingInputs = station?.missing_inputs ?? {};
  const label = `${Math.round(progress)}%`;
  // Derive display name from station_id: replace _ with space, title case
  const displayName = stationId.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-[#E6EEFF] last:border-b-0">
      {/* Station image */}
      <div className="w-12 h-10 shrink-0 rounded bg-white flex items-center justify-center overflow-hidden">
        {STATION_IMGS[stationId] && (
          <img src={STATION_IMGS[stationId]} alt={displayName}
            className="max-w-full max-h-full object-contain" style={{ maxWidth: '44px', maxHeight: '36px' }} />
        )}
      </div>
      {/* Progress donut */}
      <ProgressDonut progress={progress} isBlocked={isBlocked} label={label} />
      {/* Right: name + shortage + input chips */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-sm text-[#031040]">{displayName}</span>
          {isBlocked && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-semibold shrink-0"
              style={{ background: '#FFF3E0', border: '1px solid #F59E0B', color: '#B45309' }}>
              <img src="/icons/parts-manufacturing__shortage__warning.png" alt="warning" width={12} height={12} style={{ display: 'inline' }} />
              Shortage
            </span>
          )}
        </div>
        <InputRow inputs={inputs} missingInputs={missingInputs} iconMap={RESOURCE_ICONS} />
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
  const resources = snapshot?.resources ?? {};
  const parts: Record<string, number> = snapshot?.parts ?? {};
  const stations = snapshot?.stations ?? [];
  const completedWorkers = snapshot?.completed_robots?.count ?? 0;
  const resourceDeliveries = snapshot?.resource_deliveries ?? [];

  // Separate manufacturing stations from worker_assembly
  const mfgStations = stations.filter((s) => s.station_id !== 'worker_assembly');
  const workerStation = stations.find((s) => s.station_id === 'worker_assembly');
  const workerProgress = workerStation?.job?.progress_percent ?? 0;
  const workerIsBlocked = workerStation?.status === 'waiting_for_parts';

  return (
    <div className="flex-1 p-6">
      {/* 3 columns with FlowDots connectors between them */}
      <div className="flex items-stretch gap-0">

        {/* ── Column 1: Resources ── */}
        <div className="bg-white rounded-lg border border-[#CCDDFF] p-5 flex flex-col" style={{ flex: '1 1 0' }}>
          <div className="flex items-baseline justify-between mb-1">
            <h3 className="font-bold text-[#2850B8] text-base">Resources</h3>
            <span className="text-xs text-[#57606a]">Available</span>
          </div>
          <div className="flex-1 divide-y divide-[#F0F4FF]">
            {resourceDeliveries.length > 0
              ? resourceDeliveries.map((rd) => {
                  const ico = RESOURCE_ICONS[rd.name];
                  return (
                    <div key={rd.name} className="flex items-center gap-3 py-2.5">
                      {/* Resource icon */}
                      <div className="w-8 flex items-center justify-center shrink-0">
                        {ico
                          ? <img src={ico.src} width={ico.w * 0.7} height={ico.h * 0.7} alt={rd.name} />
                          : <span className="text-xs capitalize">{rd.name[0]}</span>
                        }
                      </div>
                      {/* Name */}
                      <span className="flex-1 text-sm text-[#031040] capitalize">{rd.name}</span>
                      {/* Segmented donut */}
                      <DeliveryDonut delivery={rd} quantity={rd.quantity} />
                      {/* Available quantity */}
                      <span className="text-lg font-bold text-[#031040] tabular-nums w-10 text-right">
                        {resources[rd.name] ?? 0}
                      </span>
                    </div>
                  );
                })
              : /* Fallback when no snapshot yet — plain list */
                (['resin', 'silicon', 'metals', 'copper', 'energy'] as const).map((res) => {
                  const ico = RESOURCE_ICONS[res];
                  return (
                    <div key={res} className="flex items-center gap-3 py-3">
                      <div className="w-8 flex items-center justify-center shrink-0">
                        {ico && <img src={ico.src} width={ico.w * 0.7} height={ico.h * 0.7} alt={res} />}
                      </div>
                      <span className="flex-1 text-sm text-[#031040] capitalize">{res}</span>
                      <span className="text-lg font-bold text-[#031040] tabular-nums">{resources[res] ?? 0}</span>
                    </div>
                  );
                })
            }
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
              {mfgStations.map((st) => {
                const inputs = stationRecipes[st.station_id] ?? {};
                return (
                  <StationRow key={st.station_id} stationId={st.station_id} station={st} inputs={inputs} />
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

          <div className="rounded-lg border border-[#CCDDFF] p-4 flex flex-col gap-3">
            {/* Top row: bee image + name/progress */}
            <div className="flex items-center gap-4">
              <div className="shrink-0 flex items-center justify-center" style={{ width: 72 }}>
                <img src="/icons/robot-assembly__worker__bee.png" alt="worker bee" style={{ width: 72, objectFit: 'contain' }} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-2">
                  <span className="font-bold text-[#031040] text-sm">Engineer</span>
                  {workerIsBlocked && (
                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-semibold shrink-0"
                      style={{ background: '#FFF3E0', border: '1px solid #F59E0B', color: '#B45309' }}>
                      <img src="/icons/parts-manufacturing__shortage__warning.png" alt="warning" width={12} height={12} style={{ display: 'inline' }} />
                      Shortage
                    </span>
                  )}
                </div>
                {/* Progress bar */}
                <div className="flex items-center gap-2">
                  <div className="flex-1 rounded-full overflow-hidden" style={{ height: 8, background: '#DDEEFF' }}>
                    <div
                      className="h-full rounded-full transition-all duration-300"
                      style={{
                        width: `${Math.round(workerProgress)}%`,
                        background: workerIsBlocked ? '#D36B00' : '#2850B8',
                      }}
                    />
                  </div>
                  <span className="text-sm font-bold tabular-nums shrink-0"
                    style={{ color: workerIsBlocked ? '#D36B00' : '#031040' }}>
                    {Math.round(workerProgress)}%
                  </span>
                </div>
              </div>
            </div>
            {/* Divider */}
            <div style={{ borderTop: '1px solid #E6EEFF' }} />
            {/* Bottom row: part input icons */}
            <InputRow
              inputs={stationRecipes['worker_assembly'] ?? {}}
              missingInputs={workerStation?.missing_inputs ?? {}}
              iconMap={PART_ICONS}
              large
            />
          </div>

          <div>
            <h4 className="font-bold text-[#031040] text-sm mb-3">Robot inventory</h4>
            <div className="rounded-lg border border-[#CCDDFF] p-4 flex items-center gap-4">
              <img src="/icons/assembled-bee-inventory__worker__bee.png" alt="assembled worker" className="w-16 object-contain shrink-0" />
              <div>
                <div className="text-sm font-semibold text-[#031040]">Engineer</div>
                <div className="text-4xl font-bold text-[#031040] tabular-nums leading-tight">{completedWorkers}</div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

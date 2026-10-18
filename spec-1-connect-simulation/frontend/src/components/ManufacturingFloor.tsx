import React from 'react';
import { DashboardState } from '../types';
import { ProgressRing } from './ProgressRing';
import { FlowDots } from './FlowDots';

// ── Resource gathering ────────────────────────────────────────────────────────
const RESOURCES: { id: string; label: string; icon: string }[] = [
  { id: 'copper',  label: 'Copper',  icon: '/icons/resource_copper.png' },
  { id: 'energy',  label: 'Energy',  icon: '/icons/resources_energy.png' },
  { id: 'metals',  label: 'Metals',  icon: '/icons/resources_metals.png' },
  { id: 'resin',   label: 'Resin',   icon: '/icons/resources_resin.png' },
  { id: 'silicon', label: 'Silicon', icon: '/icons/resources_silicon.png' },
];

// ── Parts manufacturing ───────────────────────────────────────────────────────
const STATIONS: { id: string; label: string; icon: string }[] = [
  { id: 'actuator_fabrication',  label: 'Actuator Fabrication', icon: '/icons/parts_actuator.png' },
  { id: 'battery_assembly',      label: 'Battery Assembly',     icon: '/icons/parts_battery.png' },
  { id: 'structural_molding',    label: 'Structural Molding',   icon: '/icons/parts_chassis.png' },
  { id: 'electronics_assembly',  label: 'Electronics Assembly', icon: '/icons/parts_electronics.png' },
];

// ── Robot assembly ────────────────────────────────────────────────────────────
const ROBOTS: { id: string; label: string; icon: string }[] = [
  { id: 'engineer', label: 'Engineer', icon: '/icons/robot-engineer.png' },
  { id: 'forager',  label: 'Forager',  icon: '/icons/harvester.png' },
];

// Ring fill: shows progress based on whether the job is currently active.
// While active: 60% (mid-arc, "in progress"). Idle with completions: 100%.
// No activity yet: 0%.
function ringPercent(completed: number, active: boolean): number {
  if (active) return 60;
  if (completed > 0) return 100;
  return 0;
}

interface Props {
  state: DashboardState;
}

export const ManufacturingFloor: React.FC<Props> = ({ state }) => {
  const {
    gathering_completed,
    manufacturing_completed,
    assembly_completed,
    gathering_active,
    manufacturing_active,
    assembly_active,
  } = state;

  return (
    <div className="flex-1 overflow-auto p-6">
      <div className="flex items-start gap-0 min-w-0">

        {/* ── Lane 1: Resource gathering ─────────────────────────────── */}
        <section className="flex-none" style={{ minWidth: 300 }}>
          <div
            className="rounded-xl border border-[#E0E8F8] bg-white p-5"
            style={{ minHeight: 480 }}
          >
            <h2 className="text-[#2850B8] font-bold text-base mb-4">Resource gathering</h2>
            <div className="grid grid-cols-2 gap-3">
              {RESOURCES.map(({ id, label, icon }) => {
                const count = gathering_completed[id] ?? 0;
                const active = gathering_active[id] ?? false;
                return (
                  <div
                    key={id}
                    className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-3 flex flex-col items-start gap-2"
                  >
                    <div className="flex items-center gap-2">
                      <img src={icon} width={20} height={20} alt={label} />
                      <span className="text-sm font-semibold text-[#031040]">{label}</span>
                    </div>
                    <ProgressRing
                      percent={ringPercent(count, active)}
                      label={`+${count}`}
                    />
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <FlowDots />

        {/* ── Lane 2: Parts manufacturing ────────────────────────────── */}
        <section className="flex-none" style={{ minWidth: 280 }}>
          <div
            className="rounded-xl border border-[#E0E8F8] bg-white p-5"
            style={{ minHeight: 480 }}
          >
            <h2 className="text-[#2850B8] font-bold text-base mb-4">Parts manufacturing</h2>
            <div className="flex flex-col gap-3">
              {STATIONS.map(({ id, label, icon }) => {
                const count = manufacturing_completed[id] ?? 0;
                const active = manufacturing_active[id] ?? false;
                return (
                  <div
                    key={id}
                    className="flex items-center gap-4 rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] px-4 py-3"
                  >
                    <div className="flex-1">
                      <span className="text-sm font-semibold text-[#031040]">{label}</span>
                    </div>
                    <img src={icon} width={40} height={40} alt={label} style={{ objectFit: 'contain' }} />
                    <ProgressRing
                      percent={ringPercent(count, active)}
                      label={`+${count}`}
                    />
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <FlowDots />

        {/* ── Lane 3: Robot assembly ─────────────────────────────────── */}
        <section className="flex-none" style={{ minWidth: 220 }}>
          <div
            className="rounded-xl border border-[#E0E8F8] bg-white p-5"
            style={{ minHeight: 480 }}
          >
            <h2 className="font-bold text-base text-[#031040] mb-4">Robot assembly</h2>
            <div className="flex flex-col gap-3">
              {ROBOTS.map(({ id, label, icon }) => {
                const count = assembly_completed[id] ?? 0;
                // Check either assembly station that produces this robot type
                const activeWorker = assembly_active['worker_assembly'] ?? false;
                const activeForager = assembly_active['forager_assembly'] ?? false;
                const active = id === 'engineer' ? activeWorker : activeForager;
                return (
                  <div
                    key={id}
                    className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-4"
                  >
                    <div className="text-sm font-semibold text-[#031040] mb-3">{label}</div>
                    <div className="flex items-center gap-4">
                      <img src={icon} width={48} height={48} alt={label} style={{ objectFit: 'contain' }} />
                      <ProgressRing
                        percent={ringPercent(count, active)}
                        label={`+${count}`}
                        size={88}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

      </div>
    </div>
  );
};

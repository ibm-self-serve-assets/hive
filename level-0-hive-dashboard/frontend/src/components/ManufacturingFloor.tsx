import React from 'react';
import { DashboardState } from '../types';
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

interface Props {
  state: DashboardState;
}

export const ManufacturingFloor: React.FC<Props> = ({ state }) => {
  const {
    running,
    gathering_completed,
    manufacturing_completed,
    assembly_completed,
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
                return (
                  <div
                    key={id}
                    className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-3 flex flex-col justify-between"
                  >
                    <div className="flex items-center gap-2">
                      <img src={icon} width={20} height={20} alt={label} />
                      <span className="text-sm font-semibold text-[#031040]">{label}</span>
                    </div>
                    <div className="text-2xl font-bold font-mono text-[#031040] tabular-nums mt-3">
                      {count}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <FlowDots running={running} />

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
                return (
                  <div
                    key={id}
                    className="flex items-center justify-between gap-4 rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] px-4 py-3.5"
                  >
                    <div className="flex items-center gap-3">
                      <img src={icon} width={36} height={36} alt={label} style={{ objectFit: 'contain' }} />
                      <span className="text-sm font-semibold text-[#031040]">{label}</span>
                    </div>
                    <div className="text-2xl font-bold font-mono text-[#031040] tabular-nums text-right">
                      {count}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <FlowDots running={running} />

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
                return (
                  <div
                    key={id}
                    className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-4"
                  >
                    <div className="text-sm font-semibold text-[#031040] mb-3">{label}</div>
                    <div className="flex items-center justify-between gap-4">
                      <img src={icon} width={48} height={48} alt={label} style={{ objectFit: 'contain' }} />
                      <div className="text-3xl font-bold font-mono text-[#031040] tabular-nums">
                        {count}
                      </div>
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

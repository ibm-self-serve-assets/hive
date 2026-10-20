import React from 'react';
import { EventPanel } from '../../components/EventPanel';
import { FlowDots } from '../../components/FlowDots';
import { ProgressRing } from '../../components/ProgressRing';
import type { LevelScreenProps } from '../types';

// ── Static metadata ───────────────────────────────────────────────────────────

const RESOURCES: { id: string; label: string; icon: string }[] = [
  { id: 'copper',  label: 'Copper',  icon: '/icons/svg/resource_copper.svg' },
  { id: 'energy',  label: 'Energy',  icon: '/icons/svg/resources_energy.svg' },
  { id: 'metals',  label: 'Metals',  icon: '/icons/svg/resources_metals.svg' },
  { id: 'resin',   label: 'Resin',   icon: '/icons/svg/resources_resin.svg' },
  { id: 'silicon', label: 'Silicon', icon: '/icons/svg/resources_silicon.svg' },
];

const RESOURCE_ICON: Record<string, string> = {
  copper:    '/icons/svg/resource_copper.svg',
  energy:    '/icons/svg/resources_energy.svg',
  metals:    '/icons/svg/resources_metals.svg',
  resin:     '/icons/svg/resources_resin.svg',
  silicon:   '/icons/svg/resources_silicon.svg',
};

const PART_ICON: Record<string, string> = {
  chassis:     '/icons/svg/parts_chassis.svg',
  electronics: '/icons/svg/parts_electronics.svg',
  actuator:    '/icons/svg/parts_actuator.svg',
  battery:     '/icons/svg/parts_battery.svg',
};

const STATIONS: { id: string; label: string; icon: string; output_id: string }[] = [
  { id: 'structural_molding',   label: 'Structural Molding',   icon: '/icons/svg/parts_chassis.svg',      output_id: 'chassis' },
  { id: 'electronics_assembly', label: 'Electronics Assembly', icon: '/icons/svg/parts_electronics.svg',  output_id: 'electronics' },
  { id: 'actuator_fabrication', label: 'Actuator Fabrication', icon: '/icons/svg/parts_actuator.svg',     output_id: 'actuator' },
  { id: 'battery_assembly',     label: 'Battery Assembly',     icon: '/icons/svg/parts_battery.svg',      output_id: 'battery' },
];

const ROBOTS: { id: string; station_id: string; label: string; icon: string }[] = [
  { id: 'engineer', station_id: 'worker_assembly',  label: 'Engineer', icon: '/icons/svg/robot-engineer.svg' },
  { id: 'forager',  station_id: 'forager_assembly', label: 'Forager',  icon: '/icons/svg/harvester.svg' },
];

// ── Shared sub-components ─────────────────────────────────────────────────────

/**
 * A single input chip: small greyscale icon + "+qty" label.
 * Turns orange when `blocked` is true (input is missing).
 */
const InputChip: React.FC<{
  icon: string;
  qty: number;
  blocked?: boolean;
}> = ({ icon, qty, blocked }) => (
  <span
    className="inline-flex items-center gap-0.5"
    style={{ color: blocked ? '#C75000' : '#57606A' }}
  >
    <img
      src={icon}
      width={14}
      height={14}
      alt=""
      style={{
        objectFit: 'contain',
        filter: blocked ? 'none' : 'grayscale(1)',
        opacity: blocked ? 1 : 0.7,
      }}
    />
    <span className="text-xs font-semibold tabular-nums" style={{ fontSize: 11 }}>
      +{qty}
    </span>
  </span>
);

/**
 * Row of input chips derived from the `inputs` dict of a *.started event.
 * Uses RESOURCE_ICON for manufacturing stations; PART_ICON for assembly stations.
 */
const InputChips: React.FC<{
  inputs: Record<string, number>;
  iconMap: Record<string, string>;
  blockedKeys?: Set<string>;
}> = ({ inputs, iconMap, blockedKeys }) => (
  <span className="flex items-center flex-wrap gap-1.5">
    {Object.entries(inputs).map(([inputId, qty]) => {
      const icon = iconMap[inputId];
      if (!icon) return null;
      const isBlocked = blockedKeys?.has(inputId) ?? false;
      return (
        <InputChip key={inputId} icon={icon} qty={qty} blocked={isBlocked} />
      );
    })}
  </span>
);

/**
 * The station spinner area: either the ProgressRing (when active or idle)
 * or the warning icon (when blocked).
 */
const StationSpinner: React.FC<{
  active: boolean;
  blocked: boolean;
  durationMins?: number;
  count: number;
  size?: number;
}> = ({ active, blocked, durationMins, count, size = 68 }) => {
  if (blocked) {
    return (
      <div
        className="flex items-center justify-center rounded-full border border-[#E8EFF8] bg-[#FFF8F4]"
        style={{ width: size, height: size }}
      >
        <img src="/icons/svg/warning.svg" width={32} height={32} alt="blocked" style={{ objectFit: 'contain' }} />
      </div>
    );
  }

  // Label: "n mins" if we have a Flink-derived duration, otherwise "+count"
  const label = durationMins != null
    ? `${durationMins} mins`
    : `+${count}`;

  return (
    <ProgressRing
      label={label}
      size={size}
      spinning={active}
      segments={durationMins}
    />
  );
};

// ── Main screen ───────────────────────────────────────────────────────────────

export const Level2Screen: React.FC<LevelScreenProps> = ({ state }) => {
  const {
    gathering_completed,
    manufacturing_completed,
    assembly_completed,
    gathering_active,
    manufacturing_active,
    assembly_active,
    gathering_blocked,
    manufacturing_blocked,
    assembly_blocked,
    manufacturing_inputs,
    assembly_inputs,
    job_durations,
    events,
  } = state;

  return (
    <div className="flex-1 overflow-auto p-6">
      <div className="flex items-start gap-8 min-w-0">

        {/* ── Lane 1: Resource gathering ──────────────────────────────────── */}
        <section className="flex-none" style={{ minWidth: 300 }}>
          <div
            className="rounded-xl border border-[#E0E8F8] bg-white p-5"
            style={{ minHeight: 480 }}
          >
            <h2 className="text-[#2850B8] font-bold text-base mb-4">Resource gathering</h2>
            <div className="grid grid-cols-2 gap-3">
              {RESOURCES.map(({ id, label, icon }) => {
                const count   = gathering_completed[id] ?? 0;
                const active  = gathering_active[id] ?? false;
                const blocked = id in gathering_blocked;
                const dur     = job_durations[id];

                return (
                  <div
                    key={id}
                    className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-3 flex flex-col items-center gap-2"
                  >
                    <div className="flex items-center gap-2 self-start">
                      <img src={icon} width={16} height={16} alt={label} style={{ objectFit: 'contain', filter: 'grayscale(1)', opacity: 0.7 }} />
                      <span className="text-xs font-semibold text-[#57606A]">{label}</span>
                    </div>
                    <StationSpinner
                      active={active}
                      blocked={blocked}
                      durationMins={dur}
                      count={count}
                      size={72}
                    />
                  </div>
                );
              })}
            </div>
          </div>
          <EventPanel title="Resource events" events={events?.gathering ?? []} />
        </section>

        <FlowDots running={state.running} />

        {/* ── Lane 2: Parts manufacturing ─────────────────────────────────── */}
        <section className="flex-none" style={{ minWidth: 300 }}>
          <div
            className="rounded-xl border border-[#E0E8F8] bg-white p-5"
            style={{ minHeight: 480 }}
          >
            <h2 className="text-[#2850B8] font-bold text-base mb-4">Parts manufacturing</h2>
            <div className="flex flex-col gap-3">
              {STATIONS.map(({ id, label, icon, output_id }) => {
                const count   = manufacturing_completed[id] ?? 0;
                const active  = manufacturing_active[id] ?? false;
                const blocked = id in manufacturing_blocked;
                const dur     = job_durations[id] ?? job_durations[output_id];
                const inputs  = manufacturing_inputs[id] ?? {};
                // Which input keys are missing when blocked
                const missingSet = blocked
                  ? new Set(Object.keys(manufacturing_blocked[id] ?? {}))
                  : undefined;

                return (
                  <div
                    key={id}
                    className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] px-4 py-3"
                  >
                    {/* Station header: label + input chips */}
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <span className="text-sm font-semibold text-[#031040] mr-1">{label}</span>
                      <InputChips inputs={inputs} iconMap={RESOURCE_ICON} blockedKeys={missingSet} />
                    </div>
                    {/* Station body: part icon + spinner */}
                    <div className="flex items-center gap-4">
                      <img
                        src={icon}
                        width={44}
                        height={44}
                        alt={output_id}
                        style={{ objectFit: 'contain', filter: 'grayscale(1)', opacity: 0.75 }}
                      />
                      <StationSpinner
                        active={active}
                        blocked={blocked}
                        durationMins={dur}
                        count={count}
                        size={68}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          <EventPanel title="Manufacturing events" events={events?.manufacturing ?? []} />
        </section>

        <FlowDots running={state.running} />

        {/* ── Lane 3: Robot assembly ───────────────────────────────────────── */}
        <section className="flex-none" style={{ minWidth: 260 }}>
          <div
            className="rounded-xl border border-[#E0E8F8] bg-white p-5"
            style={{ minHeight: 480 }}
          >
            <h2 className="text-[#2850B8] font-bold text-base mb-4">Robot assembly</h2>
            <div className="flex flex-col gap-3">
              {ROBOTS.map(({ id, station_id, label, icon }) => {
                const count   = assembly_completed[id] ?? 0;
                const active  = assembly_active[station_id] ?? false;
                const blocked = station_id in assembly_blocked;
                const dur     = job_durations[station_id] ?? job_durations[id];
                const inputs  = assembly_inputs[station_id] ?? {};
                const missingSet = blocked
                  ? new Set(Object.keys(assembly_blocked[station_id] ?? {}))
                  : undefined;

                return (
                  <div
                    key={id}
                    className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] px-4 py-3"
                  >
                    {/* Robot header: label + input part chips */}
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <span className="text-sm font-semibold text-[#031040] mr-1">{label}</span>
                      <InputChips inputs={inputs} iconMap={PART_ICON} blockedKeys={missingSet} />
                    </div>
                    {/* Robot body: robot icon + spinner */}
                    <div className="flex items-center gap-4">
                      <img
                        src={icon}
                        width={48}
                        height={48}
                        alt={label}
                        style={{ objectFit: 'contain', filter: 'grayscale(1)', opacity: 0.75 }}
                      />
                      <StationSpinner
                        active={active}
                        blocked={blocked}
                        durationMins={dur}
                        count={count}
                        size={68}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          <EventPanel title="Assembly events" events={events?.assembly ?? []} />
        </section>

      </div>
    </div>
  );
};

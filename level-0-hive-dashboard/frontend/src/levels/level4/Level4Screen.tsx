import React, { useState } from 'react';
import { EventPanel } from '../../components/EventPanel';
import { FlowDots } from '../../components/FlowDots';
import { Chevrons } from '../../components/Chevrons';
import type { LevelScreenProps } from '../types';

// ── Static metadata from simulation_rules.json ──────────────────────────────

const STATION_METADATA: Record<number, { cost_purchase: number; cost_upgrade: number; interval_sim_minutes: number }> = {
  1: { cost_purchase: 100, cost_upgrade: 100, interval_sim_minutes: 10 },
  2: { cost_purchase: 500, cost_upgrade: 500, interval_sim_minutes: 5 },
  3: { cost_purchase: 1000, cost_upgrade: -1, interval_sim_minutes: 3 },
};

const ADD_STATION_COST = STATION_METADATA[1].cost_purchase;

const ROBOT_PRICES: Record<string, number> = {
  engineer: 250,
  forager: 250,
};

const RESOURCE_METADATA: Record<string, { level: number }> = {
  copper:  { level: 2 },
  energy:  { level: 3 },
  metals:  { level: 1 },
  resin:   { level: 2 },
  silicon: { level: 2 },
};

const MANUFACTURING_METADATA: Record<string, { level: number }> = {
  structural_molding:   { level: 1 },
  electronics_assembly: { level: 1 },
  actuator_fabrication: { level: 1 },
  battery_assembly:     { level: 1 },
};

const ASSEMBLY_METADATA: Record<string, { level: number }> = {
  worker_assembly:  { level: 1 },
  forager_assembly: { level: 1 },
};

// Initial stations configuration (1 station per item with level from simulation_rules.json)
interface StationSlot {
  id: number;
  level: number;
}

const INITIAL_STATIONS: Record<string, StationSlot[]> = {
  copper:               [{ id: 1, level: RESOURCE_METADATA.copper.level }],
  energy:               [{ id: 1, level: RESOURCE_METADATA.energy.level }],
  metals:               [{ id: 1, level: RESOURCE_METADATA.metals.level }],
  resin:                [{ id: 1, level: RESOURCE_METADATA.resin.level }],
  silicon:              [{ id: 1, level: RESOURCE_METADATA.silicon.level }],
  structural_molding:   [{ id: 1, level: MANUFACTURING_METADATA.structural_molding.level }],
  electronics_assembly: [{ id: 1, level: MANUFACTURING_METADATA.electronics_assembly.level }],
  actuator_fabrication: [{ id: 1, level: MANUFACTURING_METADATA.actuator_fabrication.level }],
  battery_assembly:     [{ id: 1, level: MANUFACTURING_METADATA.battery_assembly.level }],
  worker_assembly:      [{ id: 1, level: ASSEMBLY_METADATA.worker_assembly.level }],
  forager_assembly:     [{ id: 1, level: ASSEMBLY_METADATA.forager_assembly.level }],
};

const MAX_STATIONS = 3;

// Inventory order: copper energy metals / resin silicon
// Gathering grid: copper energy / metals resin / silicon
const RESOURCES: { id: string; label: string; icon: string }[] = [
  { id: 'copper',  label: 'Copper',  icon: '/icons/svg/resource_copper.svg' },
  { id: 'energy',  label: 'Energy',  icon: '/icons/svg/resources_energy.svg' },
  { id: 'metals',  label: 'Metals',  icon: '/icons/svg/resources_metals.svg' },
  { id: 'resin',   label: 'Resin',   icon: '/icons/svg/resources_resin.svg' },
  { id: 'silicon', label: 'Silicon', icon: '/icons/svg/resources_silicon.svg' },
];

const GATHERING_ORDER = ['copper', 'energy', 'metals', 'resin', 'silicon'];

const RESOURCE_ICON: Record<string, string> = {
  energy:    '/icons/svg/resources_energy.svg',
  resin:     '/icons/svg/resources_resin.svg',
  silicon:   '/icons/svg/resources_silicon.svg',
  metals:    '/icons/svg/resources_metals.svg',
  copper:    '/icons/svg/resource_copper.svg',
};

const PARTS: { id: string; label: string; icon: string }[] = [
  { id: 'actuator',    label: 'Actuators',   icon: '/icons/svg/parts_actuator.svg' },
  { id: 'battery',     label: 'Batteries',   icon: '/icons/svg/parts_battery.svg' },
  { id: 'chassis',     label: 'Chassis',     icon: '/icons/svg/parts_chassis.svg' },
  { id: 'electronics', label: 'Electronics', icon: '/icons/svg/parts_electronics.svg' },
];

const PART_ICON: Record<string, string> = {
  chassis:     '/icons/svg/parts_chassis.svg',
  electronics: '/icons/svg/parts_electronics.svg',
  actuator:    '/icons/svg/parts_actuator.svg',
  battery:     '/icons/svg/parts_battery.svg',
};

const STATIONS: { id: string; label: string; icon: string; output_type: string }[] = [
  { id: 'actuator_fabrication', label: 'Actuator Fabrication', icon: '/icons/svg/parts_actuator.svg',    output_type: 'actuator' },
  { id: 'battery_assembly',     label: 'Battery Assembly',     icon: '/icons/svg/parts_battery.svg',     output_type: 'battery' },
  { id: 'structural_molding',   label: 'Chassis Molding',      icon: '/icons/svg/parts_chassis.svg',     output_type: 'chassis' },
  { id: 'electronics_assembly', label: 'Electronics Assembly', icon: '/icons/svg/parts_electronics.svg', output_type: 'electronics' },
];

const ROBOTS: { id: string; station_id: string; label: string; icon: string }[] = [
  { id: 'engineer', station_id: 'worker_assembly',  label: 'Engineer', icon: '/icons/svg/robot-engineer.svg' },
  { id: 'forager',  station_id: 'forager_assembly', label: 'Forager',  icon: '/icons/svg/harvester.svg' },
];

// ── Hexagon Tier Badge Components ────────────────────────────────────────────

const HexagonTierBadge: React.FC<{
  level: number;
  blocked?: boolean;
  active?: boolean;
  tooltip?: string;
  size?: number;
}> = ({ level, blocked = false, active = false, tooltip, size = 50 }) => {
  const height = Math.round(size * 1.15);
  const tier = (Math.max(1, Math.min(3, level))) as 1 | 2 | 3;

  return (
    <div className="relative select-none flex-none" style={{ width: size, height }}>
      <svg
        viewBox="0 0 120 120"
        width={size}
        height={height}
        style={{ display: 'block', overflow: 'visible' }}
      >
        {/* Solid blue hexagon */}
        <polygon
          points="60,6 107,33 107,87 60,114 13,87 13,33"
          fill="#0059E8"
          stroke="#0059E8"
          strokeWidth="4"
          strokeLinejoin="round"
        />

        {/* Animated Chevrons */}
        <Chevrons
          tier={tier}
          active={active && !blocked}
          inactiveOpacity={blocked ? 0.4 : 1}
        />
      </svg>

      {/* Warning icon overlay on top right */}
      {blocked && (
        <img
          src="/icons/svg/warning.svg"
          width={22}
          height={22}
          alt="blocked"
          title={tooltip ?? 'Blocked'}
          className="absolute -top-1.5 -right-2 drop-shadow-sm pointer-events-auto"
          style={{ objectFit: 'contain' }}
        />
      )}
    </div>
  );
};

const AddStationHexagon: React.FC<{ onClick?: () => void; disabled?: boolean; size?: number }> = ({ onClick, disabled = false, size = 50 }) => {
  const height = Math.round(size * 1.15);
  return (
    <div
      onClick={disabled ? undefined : onClick}
      className={`relative select-none flex-none ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer group'}`}
      style={{ width: size, height }}
      title={disabled ? 'Not enough coins' : 'Add station (max 3)'}
    >
      <svg
        viewBox="0 0 100 115"
        width={size}
        height={height}
        style={{ display: 'block', overflow: 'visible' }}
      >
        <polygon
          points="50,5 94,30 94,85 50,110 6,85 6,30"
          fill="transparent"
          stroke="#94A3B8"
          strokeWidth="3.5"
          strokeDasharray="7,5"
          strokeLinejoin="round"
          className={disabled ? '' : 'group-hover:stroke-[#0059E8] transition-colors'}
        />
        <path
          d="M 50,38 L 50,72 M 33,55 L 67,55"
          fill="none"
          stroke="#64748B"
          strokeWidth="4.5"
          strokeLinecap="round"
          className={disabled ? '' : 'group-hover:stroke-[#0059E8] transition-colors'}
        />
      </svg>
    </div>
  );
};

// ── Inventory strip ───────────────────────────────────────────────────────────

const InventoryItem: React.FC<{ icon: string; label: string; qty: number }> = ({ icon, label, qty }) => (
  <div className="flex items-center gap-2">
    <img src={icon} width={22} height={22} alt={label} style={{ objectFit: 'contain' }} />
    <span className="text-sm text-[#57606A]">{label}</span>
    <span className="text-sm font-bold font-mono text-[#031040] tabular-nums ml-1">{qty}</span>
  </div>
);

// ── Floor sub-components ──────────────────────────────────────────────────────

const InputChip: React.FC<{ icon: string; qty: number; blocked?: boolean }> = ({ icon, qty, blocked }) => (
  <span className="inline-flex items-center gap-0.5" style={{ color: blocked ? '#C75000' : '#57606A' }}>
    <img
      src={icon} width={18} height={18} alt=""
      style={{ objectFit: 'contain', opacity: blocked ? 1 : 0.85 }}
    />
    <span className="text-xs font-semibold tabular-nums" style={{ fontSize: 11 }}>+{qty}</span>
  </span>
);

const InputChips: React.FC<{
  inputs: Record<string, number>;
  iconMap: Record<string, string>;
  blockedKeys?: Set<string>;
}> = ({ inputs, iconMap, blockedKeys }) => (
  <span className="flex items-center flex-wrap gap-1.5">
    {Object.entries(inputs).map(([inputId, qty]) => {
      const icon = iconMap[inputId];
      if (!icon) return null;
      return <InputChip key={inputId} icon={icon} qty={qty} blocked={blockedKeys?.has(inputId)} />;
    })}
  </span>
);

// ── Main screen ───────────────────────────────────────────────────────────────

export const Level4Screen: React.FC<LevelScreenProps> = ({ state }) => {
  const {
    running,
    gathering_blocked,
    manufacturing_blocked,
    assembly_blocked,
    manufacturing_inputs,
    assembly_inputs,
    job_durations,
    inventory,
    events,
  } = state;

  const [stationSlots, setStationSlots] = useState<Record<string, StationSlot[]>>(INITIAL_STATIONS);
  const [spentCoins, setSpentCoins] = useState<number>(0);

  // Coins earned from completed robots
  const earnedCoins =
    (inventory.robot?.engineer ?? 0) * (ROBOT_PRICES.engineer ?? 250) +
    (inventory.robot?.forager ?? 0) * (ROBOT_PRICES.forager ?? 250);

  const coins = Math.max(0, earnedCoins - spentCoins);

  const addStation = (key: string) => {
    if (coins < ADD_STATION_COST) return;
    setStationSlots(prev => {
      const current = prev[key] ?? [{ id: 1, level: 1 }];
      if (current.length >= MAX_STATIONS) return prev;
      setSpentCoins(s => s + ADD_STATION_COST);
      return {
        ...prev,
        [key]: [...current, { id: current.length + 1, level: 1 }],
      };
    });
  };

  const upgradeStation = (key: string, index: number) => {
    const current = stationSlots[key] ?? [{ id: 1, level: 1 }];
    const st = current[index];
    if (!st || st.level >= 3) return;
    const cost = STATION_METADATA[st.level]?.cost_upgrade ?? 100;
    if (cost === -1 || coins < cost) return;

    setSpentCoins(s => s + cost);
    setStationSlots(prev => ({
      ...prev,
      [key]: (prev[key] ?? current).map((sItem, i) =>
        i === index ? { ...sItem, level: Math.min(3, sItem.level + 1) } : sItem
      ),
    }));
  };

  const canAffordAdd = coins >= ADD_STATION_COST;

  return (
    <div className="flex-1 overflow-auto p-6">
      <div className="flex items-start gap-0 min-w-0">

        {/* ── Column 1: Resource gathering ──────────────────────────────── */}
        <div className="flex-[4] flex flex-col gap-4 min-w-0">
          {/* Inventory */}
          <div className="rounded-xl border border-[#E0E8F8] bg-white px-5 py-4">
            <h2 className="text-[#2850B8] font-bold text-sm mb-3">Resource inventory</h2>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              {RESOURCES.map(({ id, label, icon }) => (
                <InventoryItem key={id} icon={icon} label={label} qty={inventory.resource[id] ?? 0} />
              ))}
            </div>
          </div>
          {/* Floor */}
          <section>
            <div className="rounded-xl border border-[#E0E8F8] bg-white p-5" style={{ minHeight: 480 }}>
              <h2 className="text-[#2850B8] font-bold text-base mb-4">Resource gathering</h2>
              <div className="grid grid-cols-2 gap-3">
                {GATHERING_ORDER.map((gid) => {
                  const res = RESOURCES.find(r => r.id === gid)!;
                  const { id, label, icon } = res;
                  const blocked = id in (gathering_blocked ?? {});
                  const dur = job_durations[id];
                  const meta = RESOURCE_METADATA[id] ?? { level: 1 };
                  const slots = stationSlots[id] ?? [{ id: 1, level: meta.level }];

                  return (
                    <div key={id} className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-3 flex flex-col items-start gap-3">
                      {/* Header with Icon and Label */}
                      <div className="flex items-center gap-2">
                        <img src={icon} width={28} height={28} alt={label} style={{ objectFit: 'contain' }} />
                        <span className="text-sm font-semibold text-[#031040]">{label}</span>
                      </div>

                      {/* Stations row (up to 3) + Add button */}
                      <div className="flex items-start justify-start gap-3 flex-wrap">
                        {slots.map((st, idx) => {
                          const cost = STATION_METADATA[st.level]?.cost_upgrade ?? 100;
                          const isMax = st.level >= 3 || cost === -1;
                          const canAfford = !isMax && coins >= cost;
                          const durationText = dur != null ? `${dur} mins` : `${STATION_METADATA[st.level]?.interval_sim_minutes ?? 10} mins`;

                          return (
                            <div key={st.id} className="flex flex-col items-center gap-1.5" style={{ width: 80 }}>
                              <HexagonTierBadge
                                level={st.level}
                                blocked={blocked}
                                active={running}
                                tooltip="Waiting for resources"
                                size={50}
                              />
                              <span className="text-xs font-semibold text-[#57606A] leading-tight text-center whitespace-nowrap">
                                {blocked ? 'Parts unavailable' : durationText}
                              </span>
                              {isMax ? (
                                <div className="rounded-md bg-[#E2E8F4] text-[#57606A] font-bold text-xs flex items-center justify-center py-1 select-none w-full text-center">
                                  Max level
                                </div>
                              ) : (
                                <button
                                  onClick={() => upgradeStation(id, idx)}
                                  disabled={!canAfford}
                                  className={`rounded-md font-bold text-xs flex items-center justify-center gap-1 py-1 px-1.5 transition w-full shadow-sm select-none ${
                                    canAfford
                                      ? 'bg-[#0059E8] hover:bg-[#0048C4] text-white cursor-pointer'
                                      : 'bg-[#E2E8F4] text-[#8C9BAE] cursor-not-allowed'
                                  }`}
                                >
                                  <span>{cost}</span>
                                  <img
                                    src="/icons/svg/coin.svg"
                                    width={13}
                                    height={13}
                                    alt="coin"
                                    style={{ objectFit: 'contain', opacity: canAfford ? 1 : 0.6 }}
                                  />
                                </button>
                              )}
                            </div>
                          );
                        })}

                        {slots.length < MAX_STATIONS && (
                          <div className="flex flex-col items-center gap-1.5" style={{ width: 68 }}>
                            <AddStationHexagon
                              onClick={() => addStation(id)}
                              disabled={!canAffordAdd}
                              size={50}
                            />
                            <span className="text-xs font-semibold text-[#57606A] leading-tight text-center whitespace-nowrap">
                              Add station
                            </span>
                            <button
                              onClick={() => addStation(id)}
                              disabled={!canAffordAdd}
                              className={`rounded-md font-bold text-xs flex items-center justify-center gap-1 py-1 px-1.5 transition w-full shadow-sm select-none ${
                                canAffordAdd
                                  ? 'bg-[#0059E8] hover:bg-[#0048C4] text-white cursor-pointer'
                                  : 'bg-[#E2E8F4] text-[#8C9BAE] cursor-not-allowed'
                              }`}
                            >
                              <span>{ADD_STATION_COST}</span>
                              <img
                                src="/icons/svg/coin.svg"
                                width={13}
                                height={13}
                                alt="coin"
                                style={{ objectFit: 'contain', opacity: canAffordAdd ? 1 : 0.6 }}
                              />
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            <EventPanel title="Resource events" events={events?.gathering ?? []} />
          </section>
        </div>

        <FlowDots running={running} />

        {/* ── Column 2: Parts manufacturing ─────────────────────────────── */}
        <div className="flex-[3] flex flex-col gap-4 min-w-0">
          {/* Inventory */}
          <div className="rounded-xl border border-[#E0E8F8] bg-white px-5 py-4">
            <h2 className="text-[#2850B8] font-bold text-sm mb-3">Parts inventory</h2>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              {PARTS.map(({ id, label, icon }) => (
                <InventoryItem key={id} icon={icon} label={label} qty={inventory.part[id] ?? 0} />
              ))}
            </div>
          </div>
          {/* Floor */}
          <section>
            <div className="rounded-xl border border-[#E0E8F8] bg-white p-5" style={{ minHeight: 480 }}>
              <h2 className="text-[#2850B8] font-bold text-base mb-4">Parts manufacturing</h2>
              <div className="flex flex-col gap-3">
                {STATIONS.map(({ id, label, icon, output_type }) => {
                  const blocked    = id in (manufacturing_blocked ?? {});
                  const dur        = job_durations[id] ?? job_durations[output_type];
                  const inputs     = manufacturing_inputs[id] ?? {};
                  const missingSet = blocked ? new Set(Object.keys(manufacturing_blocked[id] ?? {})) : undefined;
                  const meta       = MANUFACTURING_METADATA[id] ?? { level: 1 };
                  const slots      = stationSlots[id] ?? [{ id: 1, level: meta.level }];

                  return (
                    <div key={id} className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-3 flex flex-col items-start gap-3">
                      {/* Header with Icon, Label, and Input chips */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <img src={icon} width={28} height={28} alt={output_type} style={{ objectFit: 'contain' }} />
                        <span className="text-sm font-semibold text-[#031040] mr-1">{label}</span>
                        <InputChips inputs={inputs} iconMap={RESOURCE_ICON} blockedKeys={missingSet} />
                      </div>

                      {/* Stations row (up to 3) + Add button */}
                      <div className="flex items-start justify-start gap-3 flex-wrap">
                        {slots.map((st, idx) => {
                          const cost = STATION_METADATA[st.level]?.cost_upgrade ?? 100;
                          const isMax = st.level >= 3 || cost === -1;
                          const canAfford = !isMax && coins >= cost;
                          const durationText = dur != null ? `${dur} mins` : `${STATION_METADATA[st.level]?.interval_sim_minutes ?? 10} mins`;

                          return (
                            <div key={st.id} className="flex flex-col items-center gap-1.5" style={{ width: 80 }}>
                              <HexagonTierBadge
                                level={st.level}
                                blocked={blocked}
                                active={running}
                                tooltip="Waiting for resources"
                                size={50}
                              />
                              <span className="text-xs font-semibold text-[#57606A] leading-tight text-center whitespace-nowrap">
                                {blocked ? 'Parts unavailable' : durationText}
                              </span>
                              {isMax ? (
                                <div className="rounded-md bg-[#E2E8F4] text-[#57606A] font-bold text-xs flex items-center justify-center py-1 select-none w-full text-center">
                                  Max level
                                </div>
                              ) : (
                                <button
                                  onClick={() => upgradeStation(id, idx)}
                                  disabled={!canAfford}
                                  className={`rounded-md font-bold text-xs flex items-center justify-center gap-1 py-1 px-1.5 transition w-full shadow-sm select-none ${
                                    canAfford
                                      ? 'bg-[#0059E8] hover:bg-[#0048C4] text-white cursor-pointer'
                                      : 'bg-[#E2E8F4] text-[#8C9BAE] cursor-not-allowed'
                                  }`}
                                >
                                  <span>{cost}</span>
                                  <img
                                    src="/icons/svg/coin.svg"
                                    width={13}
                                    height={13}
                                    alt="coin"
                                    style={{ objectFit: 'contain', opacity: canAfford ? 1 : 0.6 }}
                                  />
                                </button>
                              )}
                            </div>
                          );
                        })}

                        {slots.length < MAX_STATIONS && (
                          <div className="flex flex-col items-center gap-1.5" style={{ width: 68 }}>
                            <AddStationHexagon
                              onClick={() => addStation(id)}
                              disabled={!canAffordAdd}
                              size={50}
                            />
                            <span className="text-xs font-semibold text-[#57606A] leading-tight text-center whitespace-nowrap">
                              Add station
                            </span>
                            <button
                              onClick={() => addStation(id)}
                              disabled={!canAffordAdd}
                              className={`rounded-md font-bold text-xs flex items-center justify-center gap-1 py-1 px-1.5 transition w-full shadow-sm select-none ${
                                canAffordAdd
                                  ? 'bg-[#0059E8] hover:bg-[#0048C4] text-white cursor-pointer'
                                  : 'bg-[#E2E8F4] text-[#8C9BAE] cursor-not-allowed'
                              }`}
                            >
                              <span>{ADD_STATION_COST}</span>
                              <img
                                src="/icons/svg/coin.svg"
                                width={13}
                                height={13}
                                alt="coin"
                                style={{ objectFit: 'contain', opacity: canAffordAdd ? 1 : 0.6 }}
                              />
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            <EventPanel title="Manufacturing events" events={events?.manufacturing ?? []} />
          </section>
        </div>

        <FlowDots running={running} />

        {/* ── Column 3: Robot assembly & Treasury ────────────────────────── */}
        <div className="flex-[3] flex flex-col gap-4 min-w-0">
          {/* Inventory & Treasury Row */}
          <div className="flex gap-4">
            {/* Robot inventory */}
            <div className="flex-1 rounded-xl border border-[#E0E8F8] bg-white px-5 py-4">
              <h2 className="text-[#2850B8] font-bold text-sm mb-3">Robot inventory</h2>
              <div className="flex flex-col gap-2">
                {ROBOTS.map(({ id, label, icon }) => (
                  <InventoryItem key={id} icon={icon} label={label} qty={inventory.robot[id] ?? 0} />
                ))}
              </div>
            </div>

            {/* Treasury */}
            <div className="flex-1 rounded-xl border border-[#E0E8F8] bg-white px-5 py-4">
              <h2 className="text-[#2850B8] font-bold text-sm mb-3">Treasury</h2>
              <div className="flex items-center gap-2">
                <img src="/icons/svg/coin.svg" width={22} height={22} alt="Coins" style={{ objectFit: 'contain' }} />
                <span className="text-sm text-[#57606A]">Coins</span>
                <span className="text-sm font-bold font-mono text-[#031040] tabular-nums ml-1">{coins}</span>
              </div>
            </div>
          </div>

          {/* Floor */}
          <section>
            <div className="rounded-xl border border-[#E0E8F8] bg-white p-5" style={{ minHeight: 480 }}>
              <h2 className="text-[#2850B8] font-bold text-base mb-4">Robot assembly</h2>
              <div className="flex flex-col gap-3">
                {ROBOTS.map(({ id, station_id, label, icon }) => {
                  const blocked     = station_id in (assembly_blocked ?? {});
                  const dur         = job_durations[station_id] ?? job_durations[id];
                  const inputs      = assembly_inputs[station_id] ?? {};
                  const missingSet  = blocked ? new Set(Object.keys(assembly_blocked[station_id] ?? {})) : undefined;
                  const meta        = ASSEMBLY_METADATA[station_id] ?? { level: 1 };
                  const slots       = stationSlots[station_id] ?? [{ id: 1, level: meta.level }];

                  return (
                    <div key={id} className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-3 flex flex-col items-start gap-3">
                      {/* Header with Icon, Label, and Input chips */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <img src={icon} width={28} height={28} alt={label} style={{ objectFit: 'contain' }} />
                        <span className="text-sm font-semibold text-[#031040] mr-1">{label}</span>
                        <InputChips inputs={inputs} iconMap={PART_ICON} blockedKeys={missingSet} />
                      </div>

                      {/* Stations row (up to 3) + Add button */}
                      <div className="flex items-start justify-start gap-3 flex-wrap">
                        {slots.map((st, idx) => {
                          const cost = STATION_METADATA[st.level]?.cost_upgrade ?? 100;
                          const isMax = st.level >= 3 || cost === -1;
                          const canAfford = !isMax && coins >= cost;
                          const durationText = dur != null ? `${dur} mins` : `${STATION_METADATA[st.level]?.interval_sim_minutes ?? 10} mins`;

                          return (
                            <div key={st.id} className="flex flex-col items-center gap-1.5" style={{ width: 80 }}>
                              <HexagonTierBadge
                                level={st.level}
                                blocked={blocked}
                                active={running}
                                tooltip="Waiting for parts"
                                size={50}
                              />
                              <span className="text-xs font-semibold text-[#57606A] leading-tight text-center whitespace-nowrap">
                                {blocked ? 'Parts unavailable' : durationText}
                              </span>
                              {isMax ? (
                                <div className="rounded-md bg-[#E2E8F4] text-[#57606A] font-bold text-xs flex items-center justify-center py-1 select-none w-full text-center">
                                  Max level
                                </div>
                              ) : (
                                <button
                                  onClick={() => upgradeStation(station_id, idx)}
                                  disabled={!canAfford}
                                  className={`rounded-md font-bold text-xs flex items-center justify-center gap-1 py-1 px-1.5 transition w-full shadow-sm select-none ${
                                    canAfford
                                      ? 'bg-[#0059E8] hover:bg-[#0048C4] text-white cursor-pointer'
                                      : 'bg-[#E2E8F4] text-[#8C9BAE] cursor-not-allowed'
                                  }`}
                                >
                                  <span>{cost}</span>
                                  <img
                                    src="/icons/svg/coin.svg"
                                    width={13}
                                    height={13}
                                    alt="coin"
                                    style={{ objectFit: 'contain', opacity: canAfford ? 1 : 0.6 }}
                                  />
                                </button>
                              )}
                            </div>
                          );
                        })}

                        {slots.length < MAX_STATIONS && (
                          <div className="flex flex-col items-center gap-1.5" style={{ width: 68 }}>
                            <AddStationHexagon
                              onClick={() => addStation(station_id)}
                              disabled={!canAffordAdd}
                              size={50}
                            />
                            <span className="text-xs font-semibold text-[#57606A] leading-tight text-center whitespace-nowrap">
                              Add station
                            </span>
                            <button
                              onClick={() => addStation(station_id)}
                              disabled={!canAffordAdd}
                              className={`rounded-md font-bold text-xs flex items-center justify-center gap-1 py-1 px-1.5 transition w-full shadow-sm select-none ${
                                canAffordAdd
                                  ? 'bg-[#0059E8] hover:bg-[#0048C4] text-white cursor-pointer'
                                  : 'bg-[#E2E8F4] text-[#8C9BAE] cursor-not-allowed'
                              }`}
                            >
                              <span>{ADD_STATION_COST}</span>
                              <img
                                src="/icons/svg/coin.svg"
                                width={13}
                                height={13}
                                alt="coin"
                                style={{ objectFit: 'contain', opacity: canAffordAdd ? 1 : 0.6 }}
                              />
                            </button>
                          </div>
                        )}
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
    </div>
  );
};

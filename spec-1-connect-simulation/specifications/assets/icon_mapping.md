# HIVE dashboard icon mapping

Updated: 2026-10-18

## Package contents

- `icons/`: 20 supplied assets (19 PNG files and 1 SVG file).
- `icons_contact_sheet.png`: previews of all 20 assets, labeled with their exact filenames.
- `icon_mapping.md`: this mapping. All icon paths below are relative to `icons/`.
- Original icon filenames and bytes are preserved. PNG dimensions vary; see the table.

## Mapping

| Filename | Dimensions | UI component / usage |
| --- | --- | --- |
| `resource_copper.png` | 256 × 256 | Resource Inventory and gathering: Copper; recipe inputs |
| `resources_energy.png` | 256 × 256 | Resource Inventory and gathering: Energy; recipe inputs |
| `resources_metals.png` | 256 × 256 | Resource Inventory and gathering: Metals; recipe inputs (previous mapping used Steel) |
| `resources_resin.png` | 256 × 256 | Resource Inventory and gathering: Resin; recipe inputs |
| `resources_silicon.png` | 256 × 256 | Resource Inventory and gathering: Silicon; recipe inputs |
| `parts_actuator.png` | 256 × 256 | Parts Inventory: Actuator; Manufacturing: Actuator Fabrication; robot recipe inputs |
| `parts_battery.png` | 256 × 256 | Parts Inventory: Battery; Manufacturing: Battery Assembly; robot recipe inputs |
| `parts_chassis.png` | 256 × 256 | Parts Inventory: Chassis; Manufacturing: Structural Molding; robot recipe inputs |
| `parts_electronics.png` | 256 × 256 | Parts Inventory: Electronics; Manufacturing: Electronics Assembly; robot recipe inputs |
| `engineer.png` | 1254 × 1254 | Robot inventory and assembly: Engineer |
| `harvester.png` | 1254 × 1254 | Robot inventory and assembly: Harvester |
| `coin.png` | 256 × 256 | Treasury balance: bee coin (raster) |
| `coin.svg` | Vector | Treasury balance: bee coin (vector) |
| `simulation_controls_run.png` | 256 × 256 | Simulation controls: Run / Start |
| `simulation_controls_pause.png` | 256 × 256 | Simulation controls: Pause |
| `simulation_status_connected.png` | 256 × 256 | Simulation connection status: Connected |
| `clock.png` | 178 × 177 | Simulation time and delivery countdown |
| `warning.png` | 256 × 256 | Manufacturing and robot assembly: input shortage badge |
| `robot-engineer.png` | 256 × 256 | Additional supplied engineer variant; use engineer.png for the updated character |
| `resource-coin.png` | 256 × 256 | Additional supplied coin variant; use coin.png or coin.svg for the updated Treasury icon |

## Rendering rules

- Use colored icons in resource balances, inventories, manufacturing stations, and robot assembly.
- For manufacturing and robot recipe inputs, reuse the corresponding resource or `parts_*.png` assets with CSS `filter: grayscale(100%)`. Use small regular-weight gray quantities (`13px`, `400`, `#6b6b6b`).
- Display `warning.png` in the amber **Shortage** badge when a station is blocked by insufficient inputs. Recipe quantities are defined in application code, not in this asset mapping.
- Display coins under **Treasury**. Coins come from robot sales and are not gathered resources.
- Use `engineer.png` and `harvester.png` for the updated robot characters. The older engineer and coin variants remain included and are identified above.
- White Run and Pause icons require a dark or colored background.
- Reuse `clock.png` for simulation time or delivery timing. Format simulation time as days, hours, and minutes.
- Render progress rings/bars and moving production indicators in SVG/CSS; they are not separate assets in this package.
- Event panels have no decorative status dots. `simulation_status_connected.png` is for connection status only.

## Removed references

The previous mapping listed assets that are absent from this archive. They are no longer mapped:

- `event-log__part-produced__status-dot.png`
- `event-log__resource-received__status-dot.png`
- `event-log__robot-assembled__status-dot.png`
- `header__information__info.png`
- `manufacturing__automated__gear.png`
- `resource-supply__scheduled-deliveries__truck.png`

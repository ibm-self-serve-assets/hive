# HIVE dashboard icon mapping

## Package contents

- `icons/`: 26 original supplied 256 × 256 PNG files, including `warning.png`.
- `icons_256_contact_sheet.png`: regenerated contact sheet of every supplied icon.
- This mapping describes the latest dashboard. Original filenames and icon bytes are preserved.

## Rendering rules

Use colored icons in resource balances, manufacturing stations and inventories. For recipe inputs in both manufacturing and robot assembly, reuse these assets with CSS `filter: grayscale(100%)`. Use small regular-weight gray quantities (`13px`, `400`, `#6b6b6b`). Do not create separate gray asset copies.

`warning.png` appears inside the amber **Shortage** badge when required inputs are unavailable. Example: resin available 3, structural molding requires 4 resin and 1 steel, station at 0%. Show the badge only when blocked by insufficient inputs.

The three event panels contain no decorative status dots. Preserve legacy dot files for compatibility, but do not render them. Blue moving dots between production columns are SVG/CSS animation, not these event icons.

The existing clock asset may be reused for system time and delivery timing. Use an SVG progress ring alongside the delivery countdown. White control icons need a dark background.

## Mapping

| Filename | UI component | Current usage |
| --- | --- | --- |
| `assembled-bee-inventory__worker__bee.png` | assembled-bee-inventory → worker → bee | Active |
| `event-log__part-produced__status-dot.png` | event-log → part-produced → status-dot | Legacy — unused; event log dots removed |
| `event-log__resource-received__status-dot.png` | event-log → resource-received → status-dot | Legacy — unused; event log dots removed |
| `event-log__robot-assembled__status-dot.png` | event-log → robot-assembled → status-dot | Legacy — unused; event log dots removed |
| `factory-connection__connected__status-dot.png` | factory-connection → connected → status-dot | Active |
| `header__information__info.png` | header → information → info | Optional — not shown in current dashboard |
| `manufacturing__automated__gear.png` | manufacturing → automated → gear | Optional — not shown in current dashboard |
| `parts-inventory__actuators__servo.png` | parts-inventory → actuators → servo | Active |
| `parts-inventory__batteries__battery.png` | parts-inventory → batteries → battery | Active |
| `parts-inventory__chassis__head-shell.png` | parts-inventory → chassis → head-shell | Active |
| `parts-inventory__electronics__board.png` | parts-inventory → electronics → board | Active |
| `parts-manufacturing__actuator-fabrication__servo.png` | parts-manufacturing → actuator-fabrication → servo | Active |
| `parts-manufacturing__battery-assembly__battery.png` | parts-manufacturing → battery-assembly → battery | Active |
| `parts-manufacturing__electronics-assembly__board.png` | parts-manufacturing → electronics-assembly → board | Active |
| `parts-manufacturing__structural-molding__chassis.png` | parts-manufacturing → structural-molding → chassis | Active |
| `resource-supply__next-delivery__clock.png` | resource-supply → next-delivery → clock | Active |
| `resource-supply__scheduled-deliveries__truck.png` | resource-supply → scheduled-deliveries → truck | Optional — not shown in current dashboard |
| `resources__copper__stack.png` | resources → copper → stack | Active |
| `resources__energy__lightning.png` | resources → energy → lightning | Active |
| `resources__metals__ingots.png` | Resources → Steel (filename retained for compatibility) | Active |
| `resources__resin__droplet.png` | resources → resin → droplet | Active |
| `resources__silicon__chip.png` | resources → silicon → chip | Active |
| `robot-assembly__worker__bee.png` | robot-assembly → worker → bee | Active |
| `simulation-controls__pause__pause.png` | simulation-controls → pause → pause | Active |
| `simulation-controls__run__play.png` | simulation-controls → run → play | Active |
| `warning.png` | Manufacturing / Assembly → Input shortage warning | Active |

## Recipe values

| Output | Required inputs |
| --- | --- |
| Chassis / Structural molding | Resin ×4 + Steel ×1 |
| Electronics | Silicon ×2 + Copper ×1 |
| Actuator | Steel ×2 + Copper ×1 |
| Battery | Energy ×2 + Copper ×1 + Steel ×1 |
| Worker robot | Chassis ×1 + Electronics ×3 + Batteries ×2 + Actuators ×8 |

Robot input icons reuse the corresponding `parts-inventory__*` assets. Steel uses `resources__metals__ingots.png`.

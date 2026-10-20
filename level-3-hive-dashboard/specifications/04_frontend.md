# Build the manufacturing dashboard

## Design reference

Open the supplied comp before implementation:

![Spec 1 manufacturing dashboard](assets/spec_1_screen_comp.png)

Use `assets/color_palette.png` for colors and the supplied IBM Plex Sans fonts in `assets/fonts/`. Build working components; do not display the comp as the application. Its numbers and dates are examples.

## Layout

Keep the navy HIVE header and left sidebar. Manufacturing is active; Colony Operations is disabled until a later specification. The sidebar contains Start/Pause, Stop, Restart at zero, 1x/5x, Kafka connection status, next delivery and “Manufacturing: Automated”.

The main area has three columns:

| Column | Content |
| --- | --- |
| Resources | Available resin, silicon, metals, copper and energy |
| Parts manufacturing | Four station rows with progress/status; parts inventory directly below |
| Robot assembly | Engineer (`worker_assembly`) and forager (`forager_assembly`) assembly rows; completed robot inventory by type below |

Put the event log across the bottom with time, event and details. Keep icons compact and mechanical. Do not duplicate the parts counts under robot assembly. Omit the comp's unused empty strip above the log.

No aggregate KPI cards, production-order form, editable resources, large mascot or Queen controls. Keep the base layout stable so later specs can extend it.

## Type and color

Load local IBM Plex Sans regular, medium, semibold and bold with @font-face; keep its license. Use these palette colors consistently:

| Use | Color |
| --- | --- |
| Navy shell and dark text | `#031040` |
| Primary controls | `#2850B8` |
| Blue accent | `#6FA1FE` |
| Border / pale surface | `#CCDDFF` / `#E6EEFF` |
| Success / exception | `#1E7A40` / `#D36B00` |

Use white content panels. Check text contrast, especially on light accents, and show status words alongside colors. The supplied palette takes precedence over approximate screenshot hues.

## Live behavior

Display the local consumer's snapshot, never server inventory read directly over HTTP. Use the control workflow in 05_controls.md. Label a server command receipt separately until its snapshot is consumed. Restart at zero requires confirmation and an explicit start-immediately choice; it is not merely restarting the UI.

Show observed lifecycle (running/paused/stopped/expired), server command status, stream freshness and any operational error as distinct states. During Kafka outages the cloud factory may continue while observations become stale. Disable progress interpolation and show the observation age. Do not claim the factory is paused merely because the laptop lost connectivity.

Add a compact registration/connection screen and a reconnect action. Keep consumer/producer secrets in the local backend only. Display factory ID and workshop connection status without revealing credentials. Explain that closing the app does not stop the hosted factory.
- **SSE Stream Invalidation on Server Restart**: If an incoming snapshot reveals a new `server_epoch` or mismatched `factory_id`, the frontend must immediately clear its local snapshot state to `awaiting_events` and prompt the user to re-register rather than displaying stale cloud data.

## Acceptance

Inspect the dashboard at 1672×941 and 1366×768. All sections and controls remain usable without clipped text. Narrow screens may stack columns. Check keyboard focus, accessible button labels, semantic progress indicators and error messages. Capture working, paused and disconnected screenshots and compare them with the comp.

# 10Micron Mount Monitor for Home Assistant

Community-maintained **experimental** local TCP integration for 10Micron mounts. Based on a GM3000HPS / Control Box V3 installation; **other models and firmwares are not yet verified**. Not affiliated with 10Micron.

## Features

- Tracking state, Gstat/GTRK watchdog, Alt/Az, mount refraction state, meridian and tracking-limit telemetry.
- Read-only PARK state and optional comparison with user-provided reference Alt/Az. **No mount movement or PARK commands** in this standalone edition.
- Optional mount UTC checks and UTC synchronization using user-configured NTP server(s).
- Optional refraction temperature/pressure preview, enable/disable, and verified updates from Home Assistant sensors.
- Optional automatic time sync after a qualified mount TCP offline → online transition (120 seconds offline, then 60 seconds stable online).
- Optional automatic refraction refresh upon connection and significant sensor changes.
- All native writes and all automatic operations are **OFF by default**.

## Integration icon

An original astronomy mount icon is included at `custom_components/tenmicron_mount/brand/icon.png`. Home Assistant 2026.3+ reads the icon directly from this location, including manual installations. The image does not use the 10Micron manufacturer's logo and does not imply an official integration.

After updating, restart HA Core and refresh the browser. Some HACS versions may still display a placeholder in the HACS catalog even though the icon works on the Home Assistant integrations/device pages.

## Manual installation (without HACS)

1. Download this project's ZIP and extract it.
2. Copy the **entire folder** `custom_components/tenmicron_mount/` into HA: `/config/custom_components/tenmicron_mount/`.
3. Restart **Home Assistant Core** (not the mount).
4. Go to **Settings → Devices & services → Add integration → 10Micron Mount Monitor**.
5. Enter the **mount IP/host and TCP port** (default: **3492**). Other configuration is under **Configure**.
6. Leave time/refraction automatic writes disabled until all sources and safety gates have been configured.

Back up an existing integration directory before any manual update. This standalone edition intentionally **does not implement PARK commands**. Do **not** install over a private observatory build that needs those commands.

## PARK reference and entity translations

Reference PARK altitude (Alt), azimuth (Az), and tolerance are optional and now shown immediately below the TCP connection settings. They are used **only** to validate the reported parked position; no movement commands are sent.

Entity names for sensors, binary sensors and buttons are translated into Czech and English. Stable entity unique IDs and all raw telemetry values are preserved; names of existing entities may be cached or customized in Home Assistant.

## Optional functions and their prerequisites

| Parameter | Required for | If missing |
| --- | --- | --- |
| Mount IP/host and port | All | Setup rejected |
| NTP servers (1–8, comma separated) | Time feature | Time feature cannot be enabled |
| `sensor.…` temperature entity | Refraction | Refraction cannot be enabled |
| `sensor.…` pressure entity | Refraction | Refraction cannot be enabled |
| Enable time feature | Manual clock check and UTC sync | Off by default |
| Enable refraction feature | Preview, enable, disable, update | Off by default |
| Native write commands | Manual/automatic writes | Off by default |
| Confirm legacy writers disabled | Manual/automatic writes | Required before writes |
| Auto time sync / auto refraction | Automatic writes | Off by default |

Configured refraction sensors must exist in HA when the feature is enabled. Readings must be fresh and valid at the moment of each update; acceptable units are °C/°F and hPa/mbar/Pa. No external weather service is queried. NTP servers are queried using UDP 123 from the HA host, and failure blocks clock actions.

Time synchronization checks are offered only when valid NTP servers have been configured. Native controls and automatic update require separate explicit opt-in.

## Safety

- **No movement, slew/GoTo, roof/shutter or PARK command** is provided by this public edition.
- Monitoring alarms and park geometry **are not independent safety interlocks** for roof motion.
- Restrict the mount's TCP service to trusted LAN devices; do not expose it to the Internet.
- Never run independent mount UTC/refraction writers at the same time.
- Mount offline, invalid TCP responses, stale weather sensors or NTP failures must not be interpreted as safe telemetry.

## HACS / Marketplace

The standalone directory layout `custom_components/tenmicron_mount/` is suitable for manual copying and HACS-compatible repository packaging. After the code is moved into a **new public repository with clean history**, add that repository as a custom integration repository. The present staging branch is private; it is not a public release.

## Compatibility

Development baseline: **10Micron GM3000HPS, Control Box V3, firmware 3.4.0**. Other models and firmware variants are not yet field-verified.

License: MIT. Integration domain: `tenmicron_mount`.

## Manual clock check results (v0.6.3)

When you press **Check mount clock (no changes)**, the integration immediately publishes a Home Assistant **persistent notification** (bell / Notifications) showing the measured mount offset in ms, NTP-to-HA host offset, NTP servers, timestamp and any error. A newer manual check replaces the prior notification instead of creating a flood. This operation **never adjusts the mount clock**.

The mount device also exposes a dedicated **Last clock check result** (translated CS/EN) and separate sensors for measurement time, mount offset, and HA/NTP offset. Open the result sensor to inspect its attributes. These live sensors retain the last check in memory until Home Assistant reload/restart; HA persistent notification remains available after restart until dismissed. The original overall Last action/result entities remain unchanged. The result state is independent of unrelated mount operations.

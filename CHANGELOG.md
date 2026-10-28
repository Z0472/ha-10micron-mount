# Changelog

## 0.7.2 – first public preview preparation

- Clarify experimental release status and the distinction between tested telemetry and unverified optional write/audio features.
- Remove outdated statement that the repository is private.
- No changes to mount control, telemetry, configurations, or entity identifiers.


## 0.7.1 – full bilingual user documentation

- Add prominent documentation links at the top of README.
- Add complete Czech and English user guides for setup, manual/automatic UTC, refraction, PARK, monitoring and alarms.
- Describe current startup/reconnect conditions and the refraction initial-write limitation without overstating functionality.
- Include the entire docs directory in GitHub Release ZIP.
- No mount protocol, automation, or entity behavior changed.


## 0.7.0 – optional alerting
- Add opt-in 10Micron Alarm Lovelace card with local browser siren, test, arm and silence, in Czech/English.
- Add tracking-stop automation blueprint with configurable sensor and siren/notification actions.
- Add separate opt-in sustained TCP availability alarm blueprint.
- Add bilingual manual-install documentation and standalone JS/blueprint tests.
- No changes to 10Micron TCP commands, clock, refraction, PARK or existing entity IDs.


## 0.6.4 – integration brand icon

- Include an original transparent 256×256 PNG icon in `custom_components/tenmicron_mount/brand/icon.png`.
- Home Assistant 2026.3+ displays local brand assets without a separate Home Assistant Brands PR.
- No changes to mount commands, polling, config or entity identifiers.


## 0.6.3 – visible clock check feedback

- Show native HA persistent notification after manual read-only mount clock check (success or failure), including offset, NTP sources, and timestamp.
- Expose independent, localized clock-check status/time/mount-offset/host-NTP-offset sensors.
- Do not change time-sync commands, write opt-ins, automatic behavior, or existing entity unique IDs.
- Avoid notification floods; replace only the previous manual clock-check notice.


## 0.6.2 – localized entities and PARK reference

- Czech and English names for all sensors, binary sensors and buttons using Home Assistant translation keys.
- Preserve stable unique IDs and existing command and monitoring behavior.
- Move reference PARK Alt, Az and tolerance to the top of the connection form for visibility; reference only, no movement commands.


## 0.6.1 – UI localization fix

- Ship translations/en.json and translations/cs.json so manual custom-component installations show human-readable fields.
- Keep original feature guards and read-only initial setup behavior unchanged.
- Regression test translation completeness.

## 0.6.0 – standalone publication candidate

- Standalone repository layout for HACS-compatible distribution and manual `custom_components` copying.
- IP, TCP port, NTP host list, temperature and pressure entities selectable through config/option flows.
- Independent explicit time/refraction feature toggles, missing-input validation and runtime enforcement.
- Manual and automatic native writes require explicit user acknowledgement that legacy writers are disabled.
- Removed custom observatory-dependent motion/PARK command from public edition; retained read-only mount status and park geometry.
- Retains 0.5.10 meridian correction and watchdog behavior.
- Not yet field-tested as a distributable package; consider this a candidate, not a production-certified safety solution.

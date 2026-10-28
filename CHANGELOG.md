# Changelog

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

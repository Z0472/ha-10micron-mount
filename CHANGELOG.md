# Changelog

## 0.6.0 – standalone publication candidate

- Standalone repository layout for HACS-compatible distribution and manual `custom_components` copying.
- IP, TCP port, NTP host list, temperature and pressure entities selectable through config/option flows.
- Independent explicit time/refraction feature toggles, missing-input validation and runtime enforcement.
- Manual and automatic native writes require explicit user acknowledgement that legacy writers are disabled.
- Removed custom observatory-dependent motion/PARK command from public edition; retained read-only mount status and park geometry.
- Retains 0.5.10 meridian correction and watchdog behavior.
- Not yet field-tested as a distributable package; consider this a candidate, not a production-certified safety solution.

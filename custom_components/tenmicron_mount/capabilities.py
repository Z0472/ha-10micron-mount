"""Pure configuration gates. Commands must pass these checks at runtime too."""
from __future__ import annotations
import re

_NTP_HOST = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,252}\Z")

def ntp_hosts(config):
    return [part.strip() for part in str(config.get("ntp_servers") or "").split(",") if part.strip()]

def has_ntp(config):
    hosts = ntp_hosts(config)
    return bool(hosts) and len(hosts) <= 8 and all(_NTP_HOST.fullmatch(h) for h in hosts)

def has_refraction_sources(config):
    return all(
        isinstance(config.get(k), str) and config[k].strip().startswith("sensor.")
        and len(config[k].strip()) > 7
        for k in ("temperature_entity", "pressure_entity")
    )

def feature_enabled(config, feature):
    if feature == "time_sync":
        return bool(config.get("time_sync_enabled", False) and has_ntp(config))
    if feature == "refraction":
        return bool(config.get("refraction_enabled", False) and has_refraction_sources(config))
    return False

def write_armed(config):
    return bool(config.get("native_controls_enabled", False)
                and config.get("legacy_writers_disabled_confirmed", False))

def auto_allowed(config, feature):
    return bool(feature_enabled(config, feature) and write_armed(config)
                and config.get(f"auto_{feature}_enabled", False))

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from .entity import MountEntity
from .const import DOMAIN
FIELDS = {
    "native_auto_time_result": ("Automatic UTC result", "mdi:clock-check-outline", None),
    "native_auto_time_at": ("Last automatic UTC attempt", "mdi:clock-outline", None),
    "native_auto_time_after_ms": ("Automatic UTC final offset", "mdi:clock-alert-outline", "ms"),
    "native_auto_refraction_result": ("Automatic refraction result", "mdi:weather-windy", None),
    "native_auto_refraction_at": ("Last automatic refraction attempt", "mdi:clock-outline", None),
    "watchdog_state": ("Tracking watchdog", "mdi:shield-eye-outline", None),
    "native_time_check_result": ("Last clock check result", "mdi:clock-check-outline", None),
    "native_time_check_at": ("Last clock check time", "mdi:clock-outline", None),
    "native_time_check_offset_ms": ("Last checked mount offset", "mdi:clock-alert-outline", "ms"),
    "native_time_check_ntp_offset_ms": ("Last checked NTP host offset", "mdi:clock-alert-outline", "ms"),
    "native_clock_offset_ms": ("Mount clock offset", "mdi:clock-alert-outline", "ms"),
    "native_temperature_delta_c": ("Temperature change since update", "mdi:thermometer-chevron-up", "°C"),
    "native_pressure_delta_hpa": ("Pressure change since update", "mdi:gauge", "hPa"),
    "native_last_temperature_written": ("Last written refraction temperature", "mdi:thermometer-check", "°C"),
    "native_last_pressure_written": ("Last written refraction pressure", "mdi:gauge", "hPa"),
    "native_last_refraction_write": ("Last native refraction update", "mdi:clock-check-outline", None),
    "native_auto_status": ("Native automation state", "mdi:robot-outline", None),
    "native_last_action": ("Last native action", "mdi:script-text-outline", None),
    "native_last_result": ("Last native result", "mdi:check-circle-outline", None),
    "tracking": ("Tracking active", "mdi:motion-sensor", None),
    "fault_reason": ("Tracking fault reason", "mdi:alert-circle-outline", None),
    "slew_seconds": ("Slew duration", "mdi:timer-outline", "s"),
    "status": ("Mount state", "mdi:telescope", None),
    "status_code": ("Mount state code", "mdi:counter", None),
    "altitude": ("Altitude", "mdi:angle-acute", "°"),
    "azimuth": ("Azimuth", "mdi:compass-outline", "°"),
    "pressure": ("Refraction pressure", "mdi:gauge", "hPa"),
    "temperature": ("Refraction temperature", "mdi:thermometer", "°C"),
    "last_seen": ("Last successful poll", "mdi:clock-check-outline", None),
    "park_separation": ("Park position deviation", "mdi:angle-acute", "°"),
    "meridian_track_limit_deg": ("Meridian tracking limit", "mdi:angle-acute", "°"),
    "meridian_slew_limit_deg": ("Meridian GoTo/slew limit", "mdi:angle-acute", "°"),
    "horizon_limit_deg": ("Minimum GoTo altitude", "mdi:angle-acute", "°"),
    "meridian_allowed_side": ("Allowed meridian side", "mdi:axis-arrow", None),
    "pier_side": ("Current pier side", "mdi:telescope", None),
    "tracking_end_minutes": ("Estimated time to tracking end", "mdi:timer-sand", "min"),
    "tracking_end_estimated_utc": ("Estimated tracking end UTC", "mdi:clock-alert-outline", None),
    "hour_angle_minutes": ("Signed hour angle", "mdi:clock-outline", "min"),
    "meridian_transit_minutes": ("Estimated time to meridian transit", "mdi:timer-outline", "min"),
}
async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MountSensor(coordinator, entry, k, *details) for k, details in FIELDS.items()])

class MountSensor(MountEntity, SensorEntity):
    def __init__(self, coordinator, entry, key, name, icon, unit):
        super().__init__(coordinator, entry)
        self.key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_icon = icon
        if key == "native_time_check_result":
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = ["ok", "error"]
        if unit:
            self._attr_native_unit_of_measurement = unit
    @property
    def available(self):
        # Persistent audit records remain available even while the mount is OFF.
        if self.key.startswith('native_park_') or self.key.startswith('native_time_check_'):
            return True
        if self.key.startswith('native_auto_time_') or self.key.startswith('native_auto_refraction_'):
            return self.coordinator.auto_controller is not None
        return super().available

    @property
    def native_value(self):
        audit = self.coordinator.auto_controller
        if audit and self.key.startswith('native_auto_time_'):
            last = audit.last_auto_time
            if not last: return None
            return {
                'native_auto_time_result': last['status'],
                'native_auto_time_at': last['at_utc'],
                'native_auto_time_after_ms': last.get('after_ms'),
            }.get(self.key)
        if audit and self.key.startswith('native_auto_refraction_'):
            last = audit.last_auto_refraction
            if not last: return None
            return {
                'native_auto_refraction_result': last['status'],
                'native_auto_refraction_at': last['at_utc'],
            }.get(self.key)
        if self.key.startswith("native_time_check_"):
            last = self.coordinator.last_clock_check
            if last is None:
                return None
            key_map = {
                "native_time_check_result": "status",
                "native_time_check_at": "at_utc",
                "native_time_check_offset_ms": "mount_offset_ms",
                "native_time_check_ntp_offset_ms": "ntp_system_offset_ms",
            }
            return last.get(key_map[self.key])
        if self.key == "native_clock_offset_ms":
            return self.coordinator.native_clock_offset_ms
        if self.key == "native_temperature_delta_c":
            return (self.coordinator.native_refraction_deltas or {}).get("temperature_delta_c")
        if self.key == "native_pressure_delta_hpa":
            return (self.coordinator.native_refraction_deltas or {}).get("pressure_delta_hpa")
        if self.key in ("native_last_temperature_written", "native_last_pressure_written", "native_last_refraction_write"):
            values = self.coordinator.auto_controller.last_verified if self.coordinator.auto_controller else None
            if not values: return None
            return values.get({"native_last_temperature_written":"temperature_c", "native_last_pressure_written":"pressure_hpa", "native_last_refraction_write":"at_utc"}[self.key])
        if self.key == "native_auto_status":
            return self.coordinator.auto_controller.status if self.coordinator.auto_controller else "Not initialized"
        if self.key == "native_last_action":
            return self.coordinator.last_action
        if self.key == "native_last_result":
            if self.coordinator.last_action_ok is None: return None
            return "OK" if self.coordinator.last_action_ok else "ERROR"
        return self.coordinator.data.get(self.key)
    @property
    def extra_state_attributes(self):
        audit = self.coordinator.auto_controller
        if self.key == "native_time_check_result":
            check = self.coordinator.last_clock_check
            return ({
                "checked_at_utc": check["at_utc"],
                "mount_offset_ms": check["mount_offset_ms"],
                "ntp_system_offset_ms": check["ntp_system_offset_ms"],
                "ntp_servers_used": check["ntp_servers_used"],
                "ntp_errors": check["ntp_errors"],
                "proposed_corrections_not_applied": check["proposed_corrections"],
                "error": check["error"],
                "read_only": True,
            } if check else None)
        if audit and self.key == 'native_auto_time_result':
            return {'last': audit.last_auto_time, 'history': audit.auto_time_history[-8:]}
        if audit and self.key == 'native_auto_refraction_result':
            return {'last': audit.last_auto_refraction, 'history': audit.auto_refraction_history[-8:]}
        if self.key in ("native_last_action", "native_last_result"):
            return {"at_utc":self.coordinator.last_action_at,
                    "source":getattr(self.coordinator,"last_action_source", "manual"),
                    "details":self.coordinator.last_action_result}
        if self.key in ("altitude", "azimuth"):
            return {"raw_response": self.coordinator.data.get(self.key + "_raw")}
        if self.key == "status":
            return {"raw_code": self.coordinator.data.get("status_code")}
        if self.key in ("meridian_track_limit_deg", "meridian_slew_limit_deg",
                        "horizon_limit_deg",
                        "meridian_allowed_side", "pier_side", "hour_angle_minutes",
                        "meridian_transit_minutes", "tracking_end_minutes",
                        "tracking_end_estimated_utc"):
            raw = self.coordinator.data.get("meridian_raw") or {}
            commands = {
                "meridian_track_limit_deg": "meridian_track_limit_deg",
                "meridian_slew_limit_deg": "meridian_slew_limit_deg",
                "horizon_limit_deg": "horizon_limit_deg",
                "meridian_allowed_side": "meridian_allowed_side",
                "pier_side": "pier_side",
                "hour_angle_minutes": "sidereal_time",
                "meridian_transit_minutes": "sidereal_time",
                "tracking_end_minutes": "tracking_end_minutes",
                "tracking_end_estimated_utc": "tracking_end_minutes",
            }
            attributes = {"raw_response": raw.get(commands[self.key])}
            if self.key in ("hour_angle_minutes", "meridian_transit_minutes"):
                attributes["raw_right_ascension"] = raw.get("right_ascension")
            if self.key in ("tracking_end_minutes", "tracking_end_estimated_utc"):
                attributes["meaning"] = "Time until tracking end; may be horizon OR meridian limit, not scheduled flip"
                attributes["auto_flip_enabled"] = self.coordinator.data.get("unattended_flip")
            if self.key == "hour_angle_minutes":
                attributes["meaning"] = "Negative before meridian transit; positive after transit"
            return attributes
        return None

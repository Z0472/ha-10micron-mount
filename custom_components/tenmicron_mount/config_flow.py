"""Config flow: connection settings and strict opt-in for time/refraction writes."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from .const import DOMAIN, DEFAULT_PORT
from .capabilities import has_ntp, has_refraction_sources, feature_enabled, write_armed

def schema(defaults):
    return vol.Schema({
        vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
        vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)):
            vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        vol.Required("interval", default=defaults.get("interval", 10)):
            vol.All(vol.Coerce(int), vol.Range(min=2, max=3600)),
        vol.Required("timeout", default=defaults.get("timeout", 2)):
            vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
        vol.Optional("park_alt", default=defaults.get("park_alt", "")): str,
        vol.Optional("park_az", default=defaults.get("park_az", "")): str,
        vol.Required("park_tolerance", default=defaults.get("park_tolerance", 0.5)):
            vol.All(vol.Coerce(float), vol.Range(min=0.01, max=30)),
        vol.Optional("ntp_servers", default=defaults.get("ntp_servers", "")): str,
        vol.Optional("temperature_entity", default=defaults.get("temperature_entity", "")): str,
        vol.Optional("pressure_entity", default=defaults.get("pressure_entity", "")): str,
        vol.Required("time_sync_enabled", default=defaults.get("time_sync_enabled", False)): bool,
        vol.Required("refraction_enabled", default=defaults.get("refraction_enabled", False)): bool,
        vol.Required("native_controls_enabled", default=defaults.get("native_controls_enabled", False)): bool,
        vol.Required("legacy_writers_disabled_confirmed",
                     default=defaults.get("legacy_writers_disabled_confirmed", False)): bool,
        vol.Required("auto_time_sync_enabled",
                     default=defaults.get("auto_time_sync_enabled", False)): bool,
        vol.Required("auto_refraction_enabled",
                     default=defaults.get("auto_refraction_enabled", False)): bool,
        vol.Required("slew_grace_seconds", default=defaults.get("slew_grace_seconds", 60)):
            vol.All(vol.Coerce(int), vol.Range(min=10, max=600)),
    })

def validate(values, hass=None):
    if not str(values.get(CONF_HOST, "")).strip():
        raise vol.Invalid("Mount IP address/host is required")
    if values.get("ntp_servers", "").strip() and not has_ntp(values):
        raise vol.Invalid("Invalid NTP server list (1–8 hosts, separated by commas)")
    if values.get("time_sync_enabled") and not has_ntp(values):
        raise vol.Invalid("Time function requires at least one valid NTP server")
    if values.get("refraction_enabled") and not has_refraction_sources(values):
        raise vol.Invalid("Refraction requires BOTH temperature and pressure sensor entities")
    if values.get("auto_time_sync_enabled") and not feature_enabled(values, "time_sync"):
        raise vol.Invalid("Automatic clock sync requires configured and enabled NTP")
    if values.get("auto_refraction_enabled") and not feature_enabled(values, "refraction"):
        raise vol.Invalid("Automatic refraction requires both configured and enabled sensors")
    if (values.get("auto_time_sync_enabled") or values.get("auto_refraction_enabled")) and not write_armed(values):
        raise vol.Invalid("Automatic writes require native controls AND legacy writer shutdown confirmation")
    if values.get("refraction_enabled") and hass is not None:
        for key in ("temperature_entity", "pressure_entity"):
            if hass.states.get(values[key].strip()) is None:
                raise vol.Invalid(f"Configured {key} does not exist in Home Assistant")
    alt, az = str(values.get("park_alt", "")).strip(), str(values.get("park_az", "")).strip()
    if bool(alt) != bool(az):
        raise vol.Invalid("Park Alt/Az reference must be provided together")
    try:
        if alt and not -90 <= float(alt) <= 90:
            raise vol.Invalid("Park altitude outside -90..90")
        if az and not 0 <= float(az) < 360:
            raise vol.Invalid("Park azimuth outside 0..360")
    except ValueError as exc:
        raise vol.Invalid("Park reference must be numeric") from exc
    return values

class TenMicronFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            try:
                validate(user_input, self.hass)
            except (vol.Invalid, ValueError):
                return self.async_show_form(step_id="user", data_schema=schema(user_input),
                                            errors={"base": "invalid_config"})
            await self.async_set_unique_id(f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=f"10Micron {user_input[CONF_HOST]}", data=user_input)
        return self.async_show_form(step_id="user", data_schema=schema({}))

    @staticmethod
    def async_get_options_flow(config_entry):
        return TenMicronOptionsFlow(config_entry)

class TenMicronOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            try:
                validate(user_input, self.hass)
            except (vol.Invalid, ValueError):
                return self.async_show_form(step_id="init", data_schema=schema(user_input),
                                            errors={"base": "invalid_config"})
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=schema({**self._entry.data, **self._entry.options}),
        )

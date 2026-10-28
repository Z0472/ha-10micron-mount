"""10Micron monitoring and opt-in time/refraction actions.

Native writes are disabled by default and never scheduled automatically.
Existing external HA scripts remain unchanged during the migration phase.
"""
import asyncio
import time
import logging
from datetime import timedelta, datetime, timezone
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, STATUS
from .angles import parse_angle, angular_distance
from .automatic import NativeAutomation, delta_decision
from .refraction_control import valid_reading
from .watchdog import evaluate as evaluate_tracking_watchdog
from .capabilities import feature_enabled, write_armed
from .meridian import build_meridian_data

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "binary_sensor", "button"]

async def query(host, port, timeout, command, *, single_character=False):
    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
    try:
        writer.write(command.encode("ascii"))
        await asyncio.wait_for(writer.drain(), timeout)
        if single_character:
            # WatchMount QueryMountFixed/RecvFixedOptionalHash: some 10Micron
            # status flags (e.g. :GREF#) reply with b"1" or b"0" without '#'.
            # Read exactly one character, then optionally consume a split '#'
            # for up to 250 ms, on THIS socket only.
            first = await asyncio.wait_for(reader.readexactly(1), timeout)
            if first not in (b"0", b"1"):
                raise ValueError(f"Invalid flag reply {first!r} for {command}")
            try:
                tail = await asyncio.wait_for(reader.read(1), min(timeout, 0.25))
            except asyncio.TimeoutError:
                tail = b""
            if tail not in (b"", b"#"):
                raise ValueError(f"Unexpected flag suffix {tail!r} for {command}")
            return first.decode("ascii")

        response = await asyncio.wait_for(reader.readuntil(b"#"), timeout)
        if len(response) > 128:
            raise ValueError("Unexpectedly large response")
        return response.decode("ascii").rstrip("#").strip()
    finally:
        writer.close()
        try:
            await asyncio.wait_for(writer.wait_closed(), 1)
        except (OSError, asyncio.TimeoutError):
            pass

class MountCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        self.entry = entry
        self._slew_started = None
        self.io_lock = asyncio.Lock()
        self.last_action = None
        self.last_action_at = None
        self.last_action_ok = None
        self.last_action_result = None
        self.native_clock_offset_ms = None
        self.native_refraction_deltas = None
        self.auto_controller = None
        # Keep added meridian polling independent of the 10-second tracking watchdog.
        # Both optional telemetry groups are polled at most once per 60 seconds.
        self._meridian_raw = {}
        self._meridian_fast_at = None
        self._meridian_slow_at = None
        options = {**entry.data, **entry.options}
        super().__init__(hass, _LOGGER, name=f"10Micron {entry.entry_id}", update_interval=timedelta(seconds=options.get("interval", 10)))

    async def mount_query(self, command):
        cfg={**self.entry.data, **self.entry.options}
        return await query(cfg[CONF_HOST], cfg[CONF_PORT], cfg.get("timeout",2), command)

    async def mount_flag(self, command):
        cfg={**self.entry.data, **self.entry.options}
        return await query(cfg[CONF_HOST], cfg[CONF_PORT], cfg.get("timeout",2), command, single_character=True)

    async def mount_no_reply(self, command):
        # 10Micron :U2# changes response precision but has no ACK by design.
        cfg={**self.entry.data, **self.entry.options}
        reader,writer=await asyncio.wait_for(asyncio.open_connection(cfg[CONF_HOST],cfg[CONF_PORT]),cfg.get("timeout",2))
        try:
            writer.write(command.encode("ascii"))
            await asyncio.wait_for(writer.drain(),cfg.get("timeout",2))
            await asyncio.sleep(0.05)
        finally:
            writer.close()
            try: await asyncio.wait_for(writer.wait_closed(),1)
            except (OSError,asyncio.TimeoutError): pass

    async def execute(self, operation, *, source="manual"):
        from . import time_sync, refraction_control
        config = {**self.entry.data, **self.entry.options}
        if operation in ("time_check", "time_sync"):
            feature = "time_sync"
        elif operation in ("refraction_preview", "enable", "disable", "update"):
            feature = "refraction"
        else:
            raise ValueError("Unsupported or unsafe mount command")
        if not feature_enabled(config, feature):
            raise ValueError(f"{feature} is disabled or lacks required NTP/sensor configuration")
        if operation not in ("time_check", "refraction_preview") and not write_armed(config):
            raise ValueError("Native writes require explicit opt-in and legacy-writer shutdown")
        self.last_action = operation
        self.last_action_source = source
        self.last_action_at = datetime.now(timezone.utc).isoformat()
        try:
            async with self.io_lock:
                if operation=="time_check":
                    result=await time_sync.run(self.hass,self,dry_run=True)
                elif operation=="time_sync":
                    result=await time_sync.run(self.hass,self,dry_run=False)
                elif operation=="refraction_preview":
                    result=await refraction_control.run(self.hass,self,mode="update",dry_run=True)
                elif operation in ("enable", "disable", "update"):
                    result=await refraction_control.run(self.hass,self,mode=operation,dry_run=False)
                else: raise ValueError(f"Unknown operation {operation}")
            self.last_action_ok=True
            self.last_action_result=result
            if operation in ("time_check", "time_sync"):
                self.native_clock_offset_ms = result.get("after_ms")
                if self.native_clock_offset_ms is None:
                    self.native_clock_offset_ms = result.get("before_ms")
            if operation in ("enable", "update") and result.get("ok") and self.auto_controller:
                await self.auto_controller.record_refraction_verified(result)
            await self.async_request_refresh()
            return result
        except Exception as exc:
            self.last_action_ok=False
            self.last_action_result={"error": str(exc),"operation":operation}
            _LOGGER.error("10Micron action %s failed: %s",operation,exc)
            self.async_update_listeners()
            raise

    async def _async_update_data(self):
        async with self.io_lock:
            try:
                data = await self._read_mount()
            except Exception as exc:
                # Discard stale optional readbacks after a lost connection.
                self._meridian_raw = {}
                self._meridian_fast_at = None
                self._meridian_slow_at = None
                raise
            return data

    async def _read_mount(self):
        cfg = {**self.entry.data, **self.entry.options}
        host, port, timeout = cfg[CONF_HOST], cfg[CONF_PORT], cfg.get("timeout", 2)
        try:
            code = int(await query(host, port, timeout, ":Gstat#"))
            if code not in STATUS:
                raise ValueError(f"Invalid Gstat value {code}")
            data = {"status": STATUS[code], "status_code": code}
            # 10Micron WatchMount critical GTRK one-character response.
            # Unlike Gstat, this reply may omit the '#' terminator.
            try:
                tracking_raw = await query(host, port, timeout, ":GTRK#", single_character=True)
                data["tracking"] = tracking_raw == "1"
            except (OSError, ValueError, UnicodeError, asyncio.TimeoutError,
                    asyncio.IncompleteReadError) as exc:
                _LOGGER.warning("Cannot read mount tracking flag: %s", exc)
                data["tracking"] = None

            if code == 6:
                if self._slew_started is None:
                    self._slew_started = time.monotonic()
                slew_duration = time.monotonic() - self._slew_started
            else:
                self._slew_started = None
                slew_duration = 0.0
            data["slew_seconds"] = round(slew_duration, 1)

            # Automatic read-only WatchMount v8 status evaluator. No APT state,
            # manual tracking_expected helper or HA input_boolean is required.
            alarm, reason, mode = evaluate_tracking_watchdog(
                code, data["tracking"], slew_duration, int(cfg.get("slew_grace_seconds", 60))
            )
            data["tracking_fault"] = alarm
            data["fault_reason"] = reason
            data["watchdog_state"] = mode
            for key, cmd in [("altitude", ":GA#"), ("azimuth", ":GZ#"), ("refraction", ":GREF#"), ("pressure", ":GRPRS#"), ("temperature", ":GRTMP#")]:
                try:
                    raw = await query(host, port, timeout, cmd, single_character=(key == "refraction"))
                    data[key + "_raw"] = raw
                    if key in ("altitude", "azimuth"):
                        data[key] = parse_angle(raw, azimuth=(key == "azimuth"))
                    elif key == "refraction":
                        data[key] = bool(int(raw)) if raw in ("0", "1") else None
                    else:
                        data[key] = float(raw)
                except (OSError, ValueError, UnicodeError, asyncio.TimeoutError, asyncio.IncompleteReadError) as exc:
                    _LOGGER.debug("Cannot read %s: %s", key, exc)
                    data[key] = None
                    data[key + "_raw"] = None
            # Read-only meridian telemetry, split into two cadences like WatchMount v8.
            # Critical Gstat/GTRK and legacy refraction readings above are untouched.
            # Optional commands never block a future 10-second cycle unnecessarily.
            now_mono = time.monotonic()
            fast_due = (
                self._meridian_fast_at is None
                or now_mono - self._meridian_fast_at >= 60
            )
            slow_due = (
                self._meridian_slow_at is None
                or now_mono - self._meridian_slow_at >= 60
            )
            meridian_raw = self._meridian_raw.copy()
            fast_commands = (
                ("tracking_end_minutes", ":Gmte#", False),
                ("pier_side", ":pS#", False),
                ("sidereal_time", ":GS#", False),
                ("right_ascension", ":GR#", False),
            )
            slow_commands = (
                ("meridian_track_limit_deg", ":Glmt#", False),
                ("meridian_slew_limit_deg", ":Glms#", False),
                ("horizon_limit_deg", ":Go#", False),
                ("meridian_allowed_side", ":GMF#", False),
                ("unattended_flip", ":Guaf#", True),
            )
            for due, commands in ((fast_due, fast_commands), (slow_due, slow_commands)):
                if not due:
                    continue
                for key, command, is_flag in commands:
                    try:
                        meridian_raw[key] = await query(
                            host, port, timeout, command, single_character=is_flag
                        )
                    except (OSError, ValueError, UnicodeError, asyncio.TimeoutError,
                            asyncio.IncompleteReadError) as exc:
                        # Never reuse an old value after a failed individual query.
                        meridian_raw[key] = None
                        _LOGGER.debug("Meridian telemetry %s unavailable: %s", command, exc)
            if fast_due:
                self._meridian_fast_at = time.monotonic()
            if slow_due:
                self._meridian_slow_at = time.monotonic()
            self._meridian_raw = meridian_raw
            data.update(build_meridian_data(
                meridian_raw, status_code=code, tracking=data["tracking"]
            ))
            data["meridian_raw"] = meridian_raw

            data["last_seen"] = datetime.now(timezone.utc).isoformat()
            if self.auto_controller and self.auto_controller.last_verified:
                last = self.auto_controller.last_verified
                try:
                    current_temp = valid_reading(self.hass, cfg.get("temperature_entity", ""), "temperature")
                    current_pressure = valid_reading(self.hass, cfg.get("pressure_entity", ""), "pressure")
                    self.native_refraction_deltas = delta_decision(current_temp, current_pressure, last)
                except (OSError, ValueError, TypeError):
                    self.native_refraction_deltas = {"reason": "invalid_source", "needed": False,
                                                      "temperature_delta_c": None, "pressure_delta_hpa": None}
            reference_ready = str(cfg.get("park_alt", "")).strip() and str(cfg.get("park_az", "")).strip()
            data["park_geometry"] = None
            if reference_ready and data["altitude"] is not None and data["azimuth"] is not None:
                delta_alt = abs(data["altitude"] - float(cfg["park_alt"]))
                delta_az = angular_distance(data["azimuth"], float(cfg["park_az"]))
                # Compare great-circle separation to avoid misleading azimuth differences near zenith.
                import math
                alt1, alt2 = math.radians(data["altitude"]), math.radians(float(cfg["park_alt"]))
                az_diff = math.radians(delta_az)
                cosine = math.sin(alt1)*math.sin(alt2) + math.cos(alt1)*math.cos(alt2)*math.cos(az_diff)
                separation = math.degrees(math.acos(min(1, max(-1, cosine))))
                data["park_separation"] = round(separation, 4)
                data["park_geometry"] = (separation <= float(cfg.get("park_tolerance", 0.5))) if code == 5 else False
            else:
                data["park_separation"] = None
            return data
        except (OSError, ValueError, UnicodeError, asyncio.TimeoutError, asyncio.IncompleteReadError) as exc:
            raise UpdateFailed(f"Invalid mount response: {exc}") from exc

async def async_setup_entry(hass, entry):
    coordinator = MountCoordinator(hass, entry)
    # Never block integration setup when the mount is powered off.
    # A failed refresh marks CoordinatorEntity sensors unavailable; the
    # periodic coordinator will recover automatically after power-on.
    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        _LOGGER.info("10Micron mount unavailable at startup; continuing in offline mode")
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.auto_controller = NativeAutomation(hass, entry, coordinator)
    await coordinator.auto_controller.async_start()
    entry.async_on_unload(entry.add_update_listener(async_options_updated))
    return True

async def async_options_updated(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass, entry):
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator and coordinator.auto_controller:
        await coordinator.auto_controller.async_stop()
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return ok

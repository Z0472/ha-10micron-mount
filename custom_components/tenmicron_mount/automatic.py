"""Optional native scheduling for 10Micron mount.

Never enabled by default. Automatic UTC sync reacts to an observed mount
TCP telemetry OFFLINE -> ONLINE transition, but only after at least 120
continuous seconds OFFLINE, followed by 60 continuous seconds ONLINE.
Brief TCP interruptions must not retrigger UTC synchronization.
An HA restart while the mount is already online is not a transition.
The initial OFFLINE duration is counted only after this integration starts.
Refraction reconnect and threshold logic remains unchanged.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from homeassistant.helpers.storage import Store
from .refraction_control import valid_reading
from .capabilities import auto_allowed

_LOGGER = logging.getLogger(__name__)
TEMP_THRESHOLD_C = 1.0
PRESS_THRESHOLD_HPA = 2.0
STABILIZE_SECONDS = 60
UTC_MIN_OFFLINE_SECONDS = 120


def config_of(entry):
    return {**entry.data, **entry.options}


def is_enabled(config, mode):
    return auto_allowed(config, mode)


def delta_decision(temp, pressure, last):
    """All units in C/hPa, baseline comes ONLY from verified native write."""
    if last is None:
        return {'needed': False, 'reason': 'no_verified_baseline',
                'temperature_delta_c': None, 'pressure_delta_hpa': None}
    dt = abs(temp - float(last['temperature_c']))
    dp = abs(pressure - float(last['pressure_hpa']))
    return {'needed': dt >= TEMP_THRESHOLD_C or dp >= PRESS_THRESHOLD_HPA,
            'reason': 'threshold' if dt >= TEMP_THRESHOLD_C or dp >= PRESS_THRESHOLD_HPA else 'within_thresholds',
            'temperature_delta_c': round(dt, 2), 'pressure_delta_hpa': round(dp, 2)}


class NativeAutomation:
    def __init__(self, hass, entry, coordinator):
        self.hass, self.entry, self.coordinator = hass, entry, coordinator
        self.store = Store(hass, 1, f'tenmicron_mount.native_{entry.entry_id}')
        self.last_verified = None
        # Independent, persistent automatic-operation audit trails.
        # Manual time_check and manual update never overwrite these histories.
        self.auto_time_history = []
        self.auto_refraction_history = []
        self._store_lock = asyncio.Lock()
        self._was_online = bool(coordinator.last_update_success)
        self._offline_since = None  # monotonic clock; set when monitoring starts
        self._epoch = 0
        self._pending = set()
        self._unsub = None
        self._closing = False
        self._online_ready = bool(coordinator.last_update_success)
        self._last_check_at = 0.0
        self._refraction_inflight = False
        self.status = 'Standby'

    async def async_start(self):
        data = await self.store.async_load()
        cfg = config_of(self.entry)
        if (isinstance(data, dict) and data.get('host') == cfg.get('host')
                and data.get('port') == cfg.get('port')
                and isinstance(data.get('last_verified'), dict)):
            self.last_verified = data['last_verified']
        if isinstance(data, dict) and data.get('host') == cfg.get('host') and data.get('port') == cfg.get('port'):
            for key in ('auto_time_history', 'auto_refraction_history'):
                records = data.get(key, [])
                if isinstance(records, list):
                    setattr(self, key, [item for item in records[-12:] if isinstance(item, dict)])
        # Starting offline counts from monitoring start, not from an unknown
        # historical disconnect; an already-online mount never triggers sync.
        self._offline_since = (asyncio.get_running_loop().time()
                               if not self._was_online else None)
        self._unsub = self.coordinator.async_add_listener(self._on_poll)
        self.status = 'Monitoring' if self._was_online else 'Mount offline'
        self.coordinator.async_update_listeners()

    async def async_stop(self):
        self._closing = True
        if self._unsub:
            self._unsub()
            self._unsub = None
        for task in tuple(self._pending):
            task.cancel()
        if self._pending:
            await asyncio.gather(*self._pending, return_exceptions=True)
        self._pending.clear()

    def _spawn(self, coro):
        if self._closing:
            coro.close()
            return
        task = self.hass.async_create_task(coro)
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    def _on_poll(self):
        if self._closing:
            return
        online = bool(self.coordinator.last_update_success)
        if online != self._was_online:
            now = asyncio.get_running_loop().time()
            offline_seconds = (now - self._offline_since
                               if online and self._offline_since is not None else None)
            utc_eligible = (offline_seconds is not None
                            and offline_seconds >= UTC_MIN_OFFLINE_SECONDS)
            self._offline_since = None if online else now
            self._was_online = online
            self._epoch += 1
            epoch = self._epoch
            self._online_ready = False
            self.status = 'Waiting for mount stabilization' if online else 'Mount offline'
            if online:
                if not utc_eligible:
                    _LOGGER.debug(
                        '10Micron UTC auto-sync skipped: TCP offline %.1f s (< %d s)',
                        offline_seconds if offline_seconds is not None else 0.0,
                        UTC_MIN_OFFLINE_SECONDS,
                    )
                self._spawn(self._after_mount_online(epoch, utc_eligible=utc_eligible))
        elif online and self._online_ready and self._should_check_again():
            self._spawn(self._compare_and_update(force=False, epoch=self._epoch))

    def _should_check_again(self):
        cfg = config_of(self.entry)
        if not is_enabled(cfg, 'refraction'):
            return False
        # Avoid duplicate tasks on repeated coordinator refresh/commands.
        now = asyncio.get_running_loop().time()
        if now - self._last_check_at < max(10, cfg.get('interval', 10)):
            return False
        self._last_check_at = now
        return True

    async def _after_mount_online(self, epoch, *, utc_eligible):
        try:
            await asyncio.sleep(STABILIZE_SECONDS)
            if self._closing or epoch != self._epoch or not self.coordinator.last_update_success:
                return
            cfg = config_of(self.entry)
            # Synchronize UTC only after >=120s observed OFFLINE and >=60s
            # stable ONLINE. Short TCP dropouts still restore refraction checks.
            if utc_eligible and is_enabled(cfg, 'time_sync'):
                try:
                    self.status = 'Synchronizing mount UTC'
                    result = await self.coordinator.execute('time_sync', source='auto_mount_online')
                    await self.record_auto_time(result=result, cause='mount_online')
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    # Record failures too; never infer success from a later manual time check.
                    await self.record_auto_time(error=str(exc), cause='mount_online')
                    _LOGGER.warning('10Micron UTC sync on mount online failed: %s', exc)
            if self._closing or epoch != self._epoch or not self.coordinator.last_update_success:
                return
            if is_enabled(config_of(self.entry), 'refraction'):
                await self._compare_and_update(force=True, epoch=epoch)
            if self._closing or epoch != self._epoch or not self.coordinator.last_update_success:
                return
            self._online_ready = True
            self._last_check_at = asyncio.get_running_loop().time()
            self.status = 'Monitoring'
        except asyncio.CancelledError:
            raise

    async def _compare_and_update(self, *, force, epoch):
        if (self._closing or epoch != self._epoch or not self.coordinator.last_update_success
                or self._refraction_inflight):
            return
        cfg = config_of(self.entry)
        if not is_enabled(cfg, 'refraction'):
            return
        self._refraction_inflight = True
        try:
            temp = valid_reading(self.hass, cfg.get('temperature_entity', ''), 'temperature')
            pressure = valid_reading(self.hass, cfg.get('pressure_entity', ''), 'pressure')
            decision = delta_decision(temp, pressure, self.last_verified)
            self.coordinator.native_refraction_deltas = decision
            self.coordinator.async_update_listeners()
            if force or decision['needed']:
                self.status = 'Updating refraction'
                cause = 'mount_online' if force else 'threshold'
                try:
                    result = await self.coordinator.execute('update', source='auto_' + cause)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    await self.record_auto_refraction(error=str(exc), cause=cause)
                    raise
                else:
                    await self.record_auto_refraction(result=result, cause=cause)
            self._last_check_at = asyncio.get_running_loop().time()
            self.status = 'Monitoring'
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.status = 'Refraction auto error'
            _LOGGER.warning('10Micron refraction auto-check failed: %s', exc)
            # Sensor or network failure must not change the verified baseline.
        finally:
            self._refraction_inflight = False

    async def record_refraction_verified(self, result):
        if 'pressure_hpa' not in result or 'temperature_c' not in result:
            return
        cfg = config_of(self.entry)
        self.last_verified = {'pressure_hpa': result['pressure_hpa'],
                              'temperature_c': result['temperature_c'],
                              'at_utc': datetime.now(timezone.utc).isoformat()}
        await self._save_state()
        self.coordinator.native_refraction_deltas = delta_decision(
            result['temperature_c'], result['pressure_hpa'], self.last_verified)
        self.coordinator.async_update_listeners()

    async def _save_state(self):
        """Serialize all persistent fields atomically; preserve the refraction baseline."""
        async with self._store_lock:
            cfg = config_of(self.entry)
            await self.store.async_save({
                'host': cfg.get('host'), 'port': cfg.get('port'),
                'last_verified': self.last_verified,
                'auto_time_history': self.auto_time_history[-12:],
                'auto_refraction_history': self.auto_refraction_history[-12:],
            })

    @property
    def last_auto_time(self):
        return self.auto_time_history[-1] if self.auto_time_history else None

    @property
    def last_auto_refraction(self):
        return self.auto_refraction_history[-1] if self.auto_refraction_history else None

    async def record_auto_time(self, *, result=None, error=None, cause='mount_online'):
        """Persist proof of a native AUTO UTC attempt, not a manual time check."""
        result = result if isinstance(result, dict) else {}
        status = ('Error' if error or not result.get('ok') else
                  'Corrected' if result.get('corrections') else 'Checked – no correction')
        entry = {
            'at_utc': datetime.now(timezone.utc).isoformat(),
            'status': status, 'cause': cause,
            'before_ms': result.get('before_ms'),
            'after_ms': result.get('after_ms'),
            'corrections': result.get('corrections', []),
            'ntp_system_offset_ms': result.get('ntp_system_offset_ms'),
            'error': error or (None if result.get('ok') else 'UTC operation not verified'),
        }
        self.auto_time_history = (self.auto_time_history + [entry])[-12:]
        await self._save_state()
        self.coordinator.async_update_listeners()

    async def record_auto_refraction(self, *, result=None, error=None, cause='mount_online'):
        """Persist native AUTO write attempt outcome independently of manual updates."""
        result = result if isinstance(result, dict) else {}
        entry = {
            'at_utc': datetime.now(timezone.utc).isoformat(),
            'status': 'Error' if error or not result.get('ok') else 'Written and verified',
            'cause': cause,
            'pressure_hpa': result.get('pressure_hpa'),
            'temperature_c': result.get('temperature_c'),
            'error': error or (None if result.get('ok') else 'Refraction write not verified'),
        }
        self.auto_refraction_history = (self.auto_refraction_history + [entry])[-12:]
        await self._save_state()
        self.coordinator.async_update_listeners()

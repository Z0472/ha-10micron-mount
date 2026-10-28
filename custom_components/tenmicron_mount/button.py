"""Explicit user actions. No automatic writes and disabled by default."""
import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from .entity import MountEntity
from .const import DOMAIN
from .capabilities import feature_enabled, write_armed

_LOGGER=logging.getLogger(__name__)
BUTTONS={
 "time_check":("Check mount clock (no changes)","mdi:clock-check-outline"),
 "time_sync":("Synchronize mount UTC (NTP)","mdi:clock-sync-outline"),
 "refraction_preview":("Preview refraction update (no changes)","mdi:eye-outline"),
 "enable":("Enable refraction","mdi:weather-windy"),
 "disable":("Disable refraction","mdi:weather-windy-off"),
 "update":("Update refraction pressure/temperature","mdi:thermometer-lines"),
}
async def async_setup_entry(hass,entry,async_add_entities):
    c=hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MountAction(c,entry,key,*metadata) for key,metadata in BUTTONS.items()])

class MountAction(MountEntity,ButtonEntity):
    def __init__(self,coordinator,entry,key,name,icon):
        super().__init__(coordinator,entry)
        self.operation=key
        self._attr_translation_key = self.operation
        self._attr_icon=icon
        self._attr_unique_id=f"{entry.entry_id}_action_{key}"
    @property
    def available(self):
        opts={**self.coordinator.entry.data, **self.coordinator.entry.options}
        feature = "time_sync" if self.operation in ("time_check", "time_sync") else "refraction"
        if not feature_enabled(opts, feature):
            return False
        if self.operation not in ("time_check", "refraction_preview") and not write_armed(opts):
            return False
        return super().available
    async def async_press(self):
        try: await self.coordinator.execute(self.operation)
        except Exception as exc: raise HomeAssistantError(f"10Micron {self.operation}: {exc}") from exc

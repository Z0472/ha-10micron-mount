from homeassistant.components.binary_sensor import BinarySensorEntity
from .entity import MountEntity
from .const import DOMAIN
async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MountBinary(c, entry, "parked", "Parked", "mdi:parking"), MountBinary(c, entry, "park_geometry", "Park position verified", "mdi:shield-check"), MountBinary(c, entry, "refraction", "Refraction enabled", "mdi:weather-windy"), MountBinary(c, entry, "tracking_fault", "Unexpected tracking stop", "mdi:alert-octagon"), MountBinary(c, entry, "unattended_flip", "Unattended meridian flip enabled", "mdi:swap-horizontal"), MountBinary(c, entry, "tracking_limit_soon", "Tracking end approaching (30 min)", "mdi:clock-alert-outline"), MountBinary(c, entry, "tracking_limit_critical", "Tracking end imminent (5 min)", "mdi:alert-circle"), MountBinary(c, entry, "meridian_transit_soon", "Meridian transit approaching (30 min)", "mdi:clock-fast")])

class MountBinary(MountEntity, BinarySensorEntity):
    def __init__(self, coordinator, entry, key, name, icon):
        super().__init__(coordinator, entry)
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key if key != 'parked' else 'parked'}"
        self._attr_icon = icon
    @property
    def is_on(self):
        if self.key == "parked":
            return self.coordinator.data["status_code"] == 5
        return self.coordinator.data.get(self.key)
    @property
    def available(self):
        return super().available and (self.key == "parked" or self.coordinator.data.get(self.key) is not None)

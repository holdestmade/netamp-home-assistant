from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class NetAmpEntity(CoordinatorEntity):
    """Base entity: shared device info and safe access to coordinator data."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="NetAmp",
            manufacturer="Armour Home Electronics",
            model="NetAmp",
        )

    def _data(self) -> dict[str, Any]:
        # coordinator.data is None until the first successful refresh
        # (e.g. when the device is offline at startup).
        return self.coordinator.data or {}


class NetAmpZoneEntity(NetAmpEntity):
    """Base entity for a single amplifier zone."""

    def __init__(self, coordinator, entry: ConfigEntry, zone: int) -> None:
        super().__init__(coordinator, entry)
        self._zone = zone

    def _zone_data(self) -> dict[str, Any]:
        return self._data().get("zones", {}).get(self._zone, {})

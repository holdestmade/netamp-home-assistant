from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ZONES, LIM_VALUES
from .netamp import NetAmpClient


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    client: NetAmpClient = data["client"]
    coordinator = data["coordinator"]

    async_add_entities([NetAmpLimSelect(coordinator, client, entry, zone=z) for z in ZONES])


class NetAmpLimSelect(CoordinatorEntity, SelectEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator, client: NetAmpClient, entry: ConfigEntry, zone: int) -> None:
        super().__init__(coordinator)
        self._client = client
        self._entry = entry
        self._zone = zone

        self._attr_unique_id = f"{entry.entry_id}_zone_{zone}_lim"
        self._attr_name = f"Zone {zone} LIM Input"
        self._attr_options = list(LIM_VALUES.values())

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "NetAmp",
            "manufacturer": "Armour Home Electronics",
            "model": "NetAmp",
        }

    def _zone_data(self) -> dict[str, Any]:
        return self.coordinator.data["zones"][self._zone]

    @property
    def current_option(self) -> str | None:
        raw = self._zone_data().get("lim")
        if raw is None:
            return None
        return LIM_VALUES.get(raw)

    async def async_select_option(self, option: str) -> None:
        # Convert label back to device value
        inv = {v: k for k, v in LIM_VALUES.items()}
        raw = inv.get(option)
        if not raw:
            return
        await self._client.async_set_lim(self._zone, raw)
        await self.coordinator.async_request_refresh()

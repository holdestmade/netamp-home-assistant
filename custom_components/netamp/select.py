from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ZONES, LIM_VALUES
from .entity import NetAmpZoneEntity
from .netamp import NetAmpClient

# Reverse map: display label -> device value
LIM_LABEL_TO_VALUE = {label: value for value, label in LIM_VALUES.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    client: NetAmpClient = data["client"]
    coordinator = data["coordinator"]

    async_add_entities([NetAmpLimSelect(coordinator, client, entry, zone=z) for z in ZONES])


class NetAmpLimSelect(NetAmpZoneEntity, SelectEntity):
    _attr_options = list(LIM_VALUES.values())

    def __init__(self, coordinator, client: NetAmpClient, entry: ConfigEntry, zone: int) -> None:
        super().__init__(coordinator, entry, zone)
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone}_lim"
        self._attr_name = f"Zone {zone} LIM Input"

    @property
    def current_option(self) -> str | None:
        raw = self._zone_data().get("lim")
        if raw is None:
            return None
        return LIM_VALUES.get(raw)

    async def async_select_option(self, option: str) -> None:
        raw = LIM_LABEL_TO_VALUE.get(option)
        if not raw:
            return
        await self._client.async_set_lim(self._zone, raw)
        await self.coordinator.async_request_refresh()

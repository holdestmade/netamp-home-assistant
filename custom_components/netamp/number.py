from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ZONES
from .netamp import NetAmpClient


@dataclass(frozen=True)
class NetAmpNumberDescription:
    key: str
    name: str
    min_value: int
    max_value: int
    step: int
    mode: NumberMode
    setter: Callable[[NetAmpClient, int, int], Any]  # (client, zone, value)
    getter: Callable[[dict[str, Any]], int | None]    # (zone_data) -> value


DESCRIPTIONS: list[NetAmpNumberDescription] = [
    NetAmpNumberDescription(
        key="max_volume",
        name="Max Volume",
        min_value=0,
        max_value=30,
        step=1,
        mode=NumberMode.SLIDER,
        setter=lambda c, z, v: c.async_set_max_volume(z, v),
        getter=lambda d: d.get("max_volume"),
    ),
    NetAmpNumberDescription(
        key="bass",
        name="Bass",
        min_value=-7,
        max_value=7,
        step=1,
        mode=NumberMode.SLIDER,
        setter=lambda c, z, v: c.async_set_bass(z, v),
        getter=lambda d: d.get("bass"),
    ),
    NetAmpNumberDescription(
        key="treble",
        name="Treble",
        min_value=-7,
        max_value=7,
        step=1,
        mode=NumberMode.SLIDER,
        setter=lambda c, z, v: c.async_set_treble(z, v),
        getter=lambda d: d.get("treble"),
    ),
    NetAmpNumberDescription(
        key="balance",
        name="Balance",
        min_value=-15,
        max_value=15,
        step=1,
        mode=NumberMode.SLIDER,
        setter=lambda c, z, v: c.async_set_balance(z, v),
        getter=lambda d: d.get("balance"),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    client: NetAmpClient = data["client"]
    coordinator = data["coordinator"]

    entities: list[NumberEntity] = []
    for zone in ZONES:
        for desc in DESCRIPTIONS:
            entities.append(NetAmpZoneNumber(coordinator, client, entry, zone, desc))

    async_add_entities(entities)


class NetAmpZoneNumber(CoordinatorEntity, NumberEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        client: NetAmpClient,
        entry: ConfigEntry,
        zone: int,
        description: NetAmpNumberDescription,
    ) -> None:
        super().__init__(coordinator)
        self._client = client
        self._entry = entry
        self._zone = zone
        self.entity_description = description

        self._attr_unique_id = f"{entry.entry_id}_zone_{zone}_{description.key}"
        self._attr_name = f"Zone {zone} {description.name}"

        self._attr_native_min_value = description.min_value
        self._attr_native_max_value = description.max_value
        self._attr_native_step = description.step
        self._attr_mode = description.mode

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
    def native_value(self) -> float | None:
        return self.entity_description.getter(self._zone_data())

    async def async_set_native_value(self, value: float) -> None:
        await self.entity_description.setter(self._client, self._zone, int(value))
        await self.coordinator.async_request_refresh()

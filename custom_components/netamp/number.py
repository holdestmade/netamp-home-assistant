from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, VOLUME_MAX, ZONES
from .entity import NetAmpZoneEntity
from .netamp import NetAmpClient

@dataclass(frozen=True)
class NetAmpNumberDescription:
    key: str
    name: str
    min_value: int
    max_value: int
    step: int
    mode: NumberMode
    setter: Callable[[NetAmpClient, int, int], Any]
    getter: Callable[[dict[str, Any]], int | None]

DESCRIPTIONS: list[NetAmpNumberDescription] = [
    NetAmpNumberDescription(
        key="max_volume",
        name="Max Volume",
        min_value=0,
        max_value=VOLUME_MAX,
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

    async_add_entities(
        NetAmpZoneNumber(coordinator, client, entry, zone, desc)
        for zone in ZONES
        for desc in DESCRIPTIONS
    )

class NetAmpZoneNumber(NetAmpZoneEntity, NumberEntity):
    def __init__(
        self,
        coordinator,
        client: NetAmpClient,
        entry: ConfigEntry,
        zone: int,
        description: NetAmpNumberDescription,
    ) -> None:
        super().__init__(coordinator, entry, zone)
        self._client = client
        self.entity_description = description

        self._attr_unique_id = f"{entry.entry_id}_zone_{zone}_{description.key}"
        self._attr_name = f"Zone {zone} {description.name}"

        self._attr_native_min_value = description.min_value
        self._attr_native_max_value = description.max_value
        self._attr_native_step = 1.0  # Force float step for UI sliders
        self._attr_mode = description.mode

    @property
    def native_value(self) -> float | None:
        return self.entity_description.getter(self._zone_data())

    async def async_set_native_value(self, value: float) -> None:
        await self.entity_description.setter(self._client, self._zone, int(value))
        await self.coordinator.async_request_refresh()

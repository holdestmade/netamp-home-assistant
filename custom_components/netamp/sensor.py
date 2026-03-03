from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ZONES
from .netamp import NetAmpClient


@dataclass(frozen=True)
class _Desc:
    key: str
    name: str
    getter: Callable[[dict[str, Any], int], str | None]  # (data, zone) -> value


DESCS: list[_Desc] = [
    _Desc("zone_name", "Zone Name", lambda data, z: data["zones"][z].get("zone_name")),
]

GLOBAL_SOURCE_DESCS: list[_Desc] = [
    _Desc("sn1", "Source 1 Name", lambda data, z: data["zones"][1].get("sn1")),
    _Desc("sn2", "Source 2 Name", lambda data, z: data["zones"][1].get("sn2")),
    _Desc("sn3", "Source 3 Name", lambda data, z: data["zones"][1].get("sn3")),
    _Desc("sn4", "Source 3a Name", lambda data, z: data["zones"][1].get("sn4")),
    _Desc("snl", "Local Source Name", lambda data, z: data["zones"][1].get("snl")),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    client: NetAmpClient = data["client"]
    coordinator = data["coordinator"]

    entities: list[SensorEntity] = []

    # Per-zone sensors
    for zone in ZONES:
        for d in DESCS:
            entities.append(NetAmpTextSensor(coordinator, entry, zone, d))

    # Global source name sensors (create once, zone=1)
    for d in GLOBAL_SOURCE_DESCS:
        entities.append(NetAmpGlobalTextSensor(coordinator, entry, d))

    async_add_entities(entities)


class NetAmpTextSensor(CoordinatorEntity, SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry, zone: int, desc: _Desc) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._zone = zone
        self._desc = desc
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone}_{desc.key}"
        self._attr_name = f"Zone {zone} {desc.name}"

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "NetAmp",
            "manufacturer": "Armour Home Electronics",
            "model": "NetAmp",
        }

    @property
    def native_value(self) -> str | None:
        return self._desc.getter(self.coordinator.data, self._zone)


class NetAmpGlobalTextSensor(CoordinatorEntity, SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry, desc: _Desc) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._desc = desc
        self._attr_unique_id = f"{entry.entry_id}_global_{desc.key}"
        self._attr_name = desc.name

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "NetAmp",
            "manufacturer": "Armour Home Electronics",
            "model": "NetAmp",
        }

    @property
    def native_value(self) -> str | None:
        return self._desc.getter(self.coordinator.data, 1)

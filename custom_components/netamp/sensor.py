from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ZONES
from .entity import NetAmpEntity, NetAmpZoneEntity

# Global source-name sensors: (state field, display name).
# Source names are global (zone is don't-care per spec), so read from zone 1.
GLOBAL_SOURCE_SENSORS = (
    ("sn1", "Source 1 Name"),
    ("sn2", "Source 2 Name"),
    ("sn3", "Source 3 Name"),
    ("sn4", "Source 3a Name"),
    ("snl", "Local Source Name"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[SensorEntity] = [
        NetAmpZoneNameSensor(coordinator, entry, zone) for zone in ZONES
    ]
    entities.extend(
        NetAmpGlobalTextSensor(coordinator, entry, key, name)
        for key, name in GLOBAL_SOURCE_SENSORS
    )

    async_add_entities(entities)


class NetAmpZoneNameSensor(NetAmpZoneEntity, SensorEntity):
    def __init__(self, coordinator, entry: ConfigEntry, zone: int) -> None:
        super().__init__(coordinator, entry, zone)
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone}_zone_name"
        self._attr_name = f"Zone {zone} Zone Name"

    @property
    def native_value(self) -> str | None:
        return self._zone_data().get("zone_name")


class NetAmpGlobalTextSensor(NetAmpEntity, SensorEntity):
    def __init__(self, coordinator, entry: ConfigEntry, key: str, name: str) -> None:
        super().__init__(coordinator, entry)
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_global_{key}"
        self._attr_name = name

    @property
    def native_value(self) -> str | None:
        return self._data().get("zones", {}).get(1, {}).get(self._key)

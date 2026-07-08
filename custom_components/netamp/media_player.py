from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, VOLUME_MAX, ZONES
from .entity import NetAmpZoneEntity
from .netamp import NetAmpClient

# (state-field, device source value, fallback label)
SOURCE_SLOTS = (
    ("sn1", "1", "Source 1"),
    ("sn2", "2", "Source 2"),
    ("sn3", "3", "Source 3"),
    ("snl", "loc", "Local"),
)

# Bare names/numbers accepted as a fallback when a label doesn't match
SOURCE_ALIASES = {
    "source 1": "1",
    "1": "1",
    "source 2": "2",
    "2": "2",
    "source 3": "3",
    "3": "3",
    "local": "loc",
    "loc": "loc",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    client: NetAmpClient = data["client"]
    coordinator = data["coordinator"]

    async_add_entities([NetAmpZoneMediaPlayer(coordinator, client, entry, zone=z) for z in ZONES])


class NetAmpZoneMediaPlayer(NetAmpZoneEntity, MediaPlayerEntity):
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, coordinator, client: NetAmpClient, entry: ConfigEntry, zone: int) -> None:
        super().__init__(coordinator, entry, zone)
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone}"
        self._attr_name = f"Zone {zone}"

    def _source_labels(self) -> dict[str, str]:
        """Map device source value -> current display label."""
        zd = self._zone_data()
        return {src: zd.get(field) or fallback for field, src, fallback in SOURCE_SLOTS}

    @property
    def state(self) -> MediaPlayerState | None:
        zd = self._zone_data()
        standby = zd.get("standby")
        if standby is True:
            return MediaPlayerState.OFF
        if standby is False:
            return MediaPlayerState.ON
        # Fallback to source heuristic
        src = zd.get("source")
        if src == "off":
            return MediaPlayerState.OFF
        if src is None:
            return None
        return MediaPlayerState.ON

    @property
    def is_volume_muted(self) -> bool | None:
        return self._zone_data().get("muted")

    @property
    def volume_level(self) -> float | None:
        vol = self._zone_data().get("volume")
        if vol is None:
            return None
        return max(0.0, min(1.0, vol / VOLUME_MAX))

    @property
    def source(self) -> str | None:
        zd = self._zone_data()
        if zd.get("standby") is True:
            return None
        return self._source_labels().get(zd.get("source"))

    @property
    def source_list(self) -> list[str] | None:
        return list(self._source_labels().values())

    async def async_turn_on(self) -> None:
        await self._client.async_turn_on(self._zone)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        await self._client.async_turn_off(self._zone)
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        # HA is 0..1; NetAmp is 0..30
        vol = int(round(max(0.0, min(1.0, volume)) * VOLUME_MAX))
        await self._client.async_set_volume(self._zone, vol)
        await self.coordinator.async_request_refresh()

    async def async_volume_up(self) -> None:
        await self._client.async_volume_step(self._zone, "+")
        await self.coordinator.async_request_refresh()

    async def async_volume_down(self) -> None:
        await self._client.async_volume_step(self._zone, "-")
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        await self._client.async_set_mute(self._zone, mute)
        await self.coordinator.async_request_refresh()

    async def async_select_source(self, source: str) -> None:
        # Match against current labels, then fall back to bare names/numbers
        label_to_src = {label: src for src, label in self._source_labels().items()}
        src = label_to_src.get(source) or SOURCE_ALIASES.get(source.lower().strip())
        if not src:
            return
        await self._client.async_set_source(self._zone, src)
        await self.coordinator.async_request_refresh()

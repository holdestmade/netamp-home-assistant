from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import MediaPlayerState
from homeassistant.components.media_player.const import (
    MediaPlayerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ZONES
from .netamp import NetAmpClient


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    client: NetAmpClient = data["client"]
    coordinator = data["coordinator"]

    async_add_entities([NetAmpZoneMediaPlayer(coordinator, client, entry, zone=z) for z in ZONES])


class NetAmpZoneMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    _attr_should_poll = False

    def __init__(self, coordinator, client: NetAmpClient, entry: ConfigEntry, zone: int) -> None:
        super().__init__(coordinator)
        self._client = client
        self._entry = entry
        self._zone = zone

        self._attr_unique_id = f"{entry.entry_id}_zone_{zone}"
        self._attr_name = f"NetAmp Zone {zone}"

        self._attr_supported_features = (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.SELECT_SOURCE
        )

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "NetAmp",
            "manufacturer": "Armour Home Electronics",
            "model": "NetAmp",
            "configuration_url": f"tcp://{self._entry.data['host']}:{self._entry.data['port']}",
        }

    @property
    def available(self) -> bool:
        return super().available

    def _zone_data(self) -> dict[str, Any]:
        return self.coordinator.data["zones"][self._zone]

    @property
    def state(self) -> str | None:
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
        return max(0.0, min(1.0, vol / 30.0))

    @property
    def source(self) -> str | None:
    zd = self._zone_data()
    if zd.get("standby") is True:
        return None
    src = zd.get("source")
    if src in ("1", "2", "3", "loc"):
        return self._source_label(src)
    return None

    def _source_label(self, src: str) -> str:
        zd = self._zone_data()
        if src == "1":
            return zd.get("sn1") or "Source 1"
        if src == "2":
            return zd.get("sn2") or "Source 2"
        if src == "3":
            return zd.get("sn3") or "Source 3"
        if src == "loc":
            return zd.get("snl") or "Local"
        return src

    @property
    def source_list(self) -> list[str] | None:
        zd = self._zone_data()
        return [
            zd.get("sn1") or "Source 1",
            zd.get("sn2") or "Source 2",
            zd.get("sn3") or "Source 3",
            zd.get("snl") or "Local",
        ]

    async def async_turn_on(self) -> None:
        await self._client.async_turn_on(self._zone)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        await self._client.async_turn_off(self._zone)
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        # HA is 0..1; NetAmp is 0..30
        vol = int(round(max(0.0, min(1.0, volume)) * 30))
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
        # Match against current labels
        zd = self._zone_data()
        mapping = {
            (zd.get("sn1") or "Source 1"): "1",
            (zd.get("sn2") or "Source 2"): "2",
            (zd.get("sn3") or "Source 3"): "3",
            (zd.get("snl") or "Local"): "loc",
        }
        src = mapping.get(source)
        if not src:
            # Fallback: accept "Source 1" etc.
            if source.lower().strip() in ("source 1", "1"):
                src = "1"
            elif source.lower().strip() in ("source 2", "2"):
                src = "2"
            elif source.lower().strip() in ("source 3", "3"):
                src = "3"
            elif source.lower().strip() in ("local", "loc"):
                src = "loc"
        if not src:
            return
        await self._client.async_set_source(self._zone, src)
        await self.coordinator.async_request_refresh()

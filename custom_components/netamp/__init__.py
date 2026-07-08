from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, CONF_SCAN_INTERVAL
from .netamp import NetAmpClient
from .service import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["media_player", "number", "select", "sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    host = entry.data["host"]
    port = entry.data["port"]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    client = NetAmpClient(host=host, port=port)

    coordinator = DataUpdateCoordinator(
        hass,
        logger=_LOGGER,
        name=f"NetAmp {host}",
        update_method=client.async_update,
        update_interval=timedelta(seconds=scan_interval),
    )

    # Perform initial refresh so entities have data; tolerate device being offline at startup
    try:
        await coordinator.async_config_entry_first_refresh()
    except (ConfigEntryNotReady, OSError):
        _LOGGER.warning("NetAmp %s unreachable at startup; will retry on next poll", host)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    # Reload the entry when options (e.g. scan interval) change
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async_setup_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if data and "client" in data:
        await data["client"].async_close()
    if not hass.data.get(DOMAIN):
        async_unload_services(hass)
    return unload_ok

from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN

SERVICE_SET_RAW_COMMAND = "set_raw_command"
SERVICE_SET_BASS = "set_bass"
SERVICE_SET_TREBLE = "set_treble"
SERVICE_SET_BALANCE = "set_balance"

_SOUND_SERVICES = {
    SERVICE_SET_BASS: ("async_set_bass", 7),
    SERVICE_SET_TREBLE: ("async_set_treble", 7),
    SERVICE_SET_BALANCE: ("async_set_balance", 15),
}

RAW_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): str,
        vol.Required("command"): str,
    }
)


def _sound_schema(limit: int) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("entry_id"): str,
            vol.Required("zone"): vol.In(["1", "2", "X"]),
            vol.Required("level"): vol.All(vol.Coerce(int), vol.Range(min=-limit, max=limit)),
        }
    )


def _get_entry_data(hass: HomeAssistant, entry_id: str) -> dict:
    data = hass.data.get(DOMAIN, {}).get(entry_id)
    if data is None:
        raise ServiceValidationError(
            f"No NetAmp config entry with id '{entry_id}' is loaded"
        )
    return data


def async_setup_services(hass: HomeAssistant) -> None:
    # Guard against re-registration when multiple config entries are loaded.
    if hass.services.has_service(DOMAIN, SERVICE_SET_RAW_COMMAND):
        return

    async def _handle_raw_command(call: ServiceCall) -> None:
        data = _get_entry_data(hass, call.data["entry_id"])
        await data["client"].async_send_raw(call.data["command"])
        await data["coordinator"].async_request_refresh()

    async def _handle_sound_setting(call: ServiceCall) -> None:
        data = _get_entry_data(hass, call.data["entry_id"])
        client = data["client"]
        zone = call.data["zone"]
        level = call.data["level"]

        method_name, _ = _SOUND_SERVICES[call.service]
        fn = getattr(client, method_name)
        zones = client.zones if zone == "X" else (int(zone),)
        for z in zones:
            await fn(z, level)

        await data["coordinator"].async_request_refresh()

    hass.services.async_register(
        DOMAIN, SERVICE_SET_RAW_COMMAND, _handle_raw_command, schema=RAW_COMMAND_SCHEMA
    )
    for service, (_, limit) in _SOUND_SERVICES.items():
        hass.services.async_register(
            DOMAIN, service, _handle_sound_setting, schema=_sound_schema(limit)
        )


def async_unload_services(hass: HomeAssistant) -> None:
    """Remove services when the last config entry is unloaded."""
    for service in (SERVICE_SET_RAW_COMMAND, *_SOUND_SERVICES):
        hass.services.async_remove(DOMAIN, service)

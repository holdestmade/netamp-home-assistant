from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall
from .const import DOMAIN

async def async_setup_services(hass: HomeAssistant) -> None:
    async def _handle_raw_command(call: ServiceCall) -> None:
        entry_id = call.data["entry_id"]
        cmd = call.data["command"]
        data = hass.data[DOMAIN][entry_id]
        client = data["client"]
        await client._send_and_collect(cmd)

    async def _apply_to_zones(client, method_name: str, zone: str, level: int) -> None:
        """Apply a sound-setting method to one or all zones."""
        fn = getattr(client, method_name)
        if zone == "X":
            for z in client.zones:
                await fn(z, level)
        else:
            await fn(int(zone), level)

    async def _handle_sound_setting(call: ServiceCall) -> None:
        entry_id = call.data["entry_id"]
        zone = call.data["zone"]
        level = int(call.data["level"])
        data = hass.data[DOMAIN][entry_id]
        client = data["client"]

        service_to_method = {
            "set_bass": "async_set_bass",
            "set_treble": "async_set_treble",
            "set_balance": "async_set_balance",
        }
        method_name = service_to_method[call.service]
        await _apply_to_zones(client, method_name, zone, level)

        await data["coordinator"].async_request_refresh()

    hass.services.async_register(DOMAIN, "set_raw_command", _handle_raw_command)
    hass.services.async_register(DOMAIN, "set_bass", _handle_sound_setting)
    hass.services.async_register(DOMAIN, "set_treble", _handle_sound_setting)
    hass.services.async_register(DOMAIN, "set_balance", _handle_sound_setting)

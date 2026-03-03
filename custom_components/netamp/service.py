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

    async def _handle_sound_setting(call: ServiceCall) -> None:
        entry_id = call.data["entry_id"]
        zone = call.data["zone"]
        level = int(call.data["level"])
        data = hass.data[DOMAIN][entry_id]
        client = data["client"]
        
        # Determine service type from call.service
        if call.service == "set_bass":
            if zone == "X":
                await client.async_set_bass(1, level)
                await client.async_set_bass(2, level)
            else:
                await client.async_set_bass(int(zone), level)
        elif call.service == "set_treble":
            if zone == "X":
                await client.async_set_treble(1, level)
                await client.async_set_treble(2, level)
            else:
                await client.async_set_treble(int(zone), level)
        elif call.service == "set_balance":
            if zone == "X":
                await client.async_set_balance(1, level)
                await client.async_set_balance(2, level)
            else:
                await client.async_set_balance(int(zone), level)
        
        await data["coordinator"].async_request_refresh()

    hass.services.async_register(DOMAIN, "set_raw_command", _handle_raw_command)
    hass.services.async_register(DOMAIN, "set_bass", _handle_sound_setting)
    hass.services.async_register(DOMAIN, "set_treble", _handle_sound_setting)
    hass.services.async_register(DOMAIN, "set_balance", _handle_sound_setting)

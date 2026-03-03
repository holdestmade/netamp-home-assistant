from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN

async def async_setup_services(hass: HomeAssistant) -> None:
    async def _handle(call: ServiceCall) -> None:
        entry_id = call.data["entry_id"]
        cmd = call.data["command"]
        data = hass.data[DOMAIN][entry_id]
        client = data["client"]
        await client._send_and_collect(cmd)  # noqa: SLF001 - debug-only service

    hass.services.async_register(DOMAIN, "set_raw_command", _handle)

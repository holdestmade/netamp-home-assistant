from __future__ import annotations

import re

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

RAW_COMMAND_RE = re.compile(r"^\$[A-Za-z0-9+\-]+$")
SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): str,
        vol.Required("command"): str,
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, "set_raw_command"):
        return

    async def _handle(call: ServiceCall) -> None:
        entry_id = call.data["entry_id"]
        cmd = call.data["command"].strip()

        if not cmd:
            raise HomeAssistantError("command must not be empty")
        if len(cmd) > 64:
            raise HomeAssistantError("command is too long")
        if not RAW_COMMAND_RE.match(cmd):
            raise HomeAssistantError("command must start with '$' and contain only NetAmp-safe characters")

        data = hass.data.get(DOMAIN, {}).get(entry_id)
        if not data:
            raise HomeAssistantError(f"unknown netamp entry_id: {entry_id}")

        client = data["client"]
        await client._send_and_collect(cmd)  # noqa: SLF001 - debug-only service

    hass.services.async_register(DOMAIN, "set_raw_command", _handle, schema=SERVICE_SCHEMA)

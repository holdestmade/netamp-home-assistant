from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, CONF_SCAN_INTERVAL
from .netamp import NetAmpClient
from .discovery import async_discover_netamps

class NetAmpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self) -> None:
        self._discovered: list[tuple[str, str]] = []

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}

        try:
            found = await async_discover_netamps(timeout=1.0)
        except Exception:
            found = []

        self._discovered = []
        for d in found:
            label = f"{d.ip} • {d.netbios or ''} • #{d.logical or ''}"
            self._discovered.append((label, d.ip))

        if user_input is not None:
            device_selection = user_input.get("device")
            host = user_input.get("host")

            if device_selection and device_selection != "manual":
                host = device_selection

            if not host:
                errors["base"] = "no_host"
            else:
                port = user_input.get("port", DEFAULT_PORT)
                client = NetAmpClient(host=host, port=port, hass=self.hass)
                try:
                    await client.async_ping()
                    
                    # Persistent Unique ID: Try MAC first, then host
                    uid_base = next((d.mac for d in found if d.ip == host and d.mac), host)
                    await self.async_set_unique_id(f"netamp_{uid_base}")
                    self._abort_if_unique_id_configured()
                    
                    return self.async_create_entry(
                        title=f"NetAmp ({host})",
                        data={"host": host, "port": port},
                    )
                except Exception:
                    errors["base"] = "cannot_connect"
                finally:
                    await client.async_close()

        device_options = {"manual": "Manual entry"}
        for label, host in self._discovered:
            device_options[host] = label

        schema = vol.Schema({
            vol.Optional("device", default="manual"): vol.In(device_options),
            vol.Optional("host"): str,
            vol.Optional("port", default=DEFAULT_PORT): vol.All(
                vol.Coerce(int),
                vol.Range(min=1, max=65535)
            ),
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry):
        return NetAmpOptionsFlowHandler(config_entry)

class NetAmpOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema({
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=2, max=300))
        })
        return self.async_show_form(step_id="init", data_schema=schema)

from __future__ import annotations

import sys
import types
import unittest


# Provide minimal Home Assistant modules used during import.
homeassistant_module = types.ModuleType("homeassistant")
config_entries_module = types.ModuleType("homeassistant.config_entries")
core_module = types.ModuleType("homeassistant.core")
exceptions_module = types.ModuleType("homeassistant.exceptions")
helpers_module = types.ModuleType("homeassistant.helpers")
device_registry_module = types.ModuleType("homeassistant.helpers.device_registry")
update_coordinator_module = types.ModuleType("homeassistant.helpers.update_coordinator")
voluptuous_module = types.ModuleType("voluptuous")
voluptuous_module.Schema = lambda value: value
voluptuous_module.Required = lambda key: key

config_entries_module.ConfigEntry = object
core_module.HomeAssistant = object
core_module.ServiceCall = object
exceptions_module.HomeAssistantError = Exception
exceptions_module.ConfigEntryNotReady = Exception
device_registry_module.DeviceEntryType = object
update_coordinator_module.DataUpdateCoordinator = object

homeassistant_module.config_entries = config_entries_module
homeassistant_module.core = core_module
homeassistant_module.exceptions = exceptions_module
homeassistant_module.helpers = helpers_module
helpers_module.device_registry = device_registry_module
helpers_module.update_coordinator = update_coordinator_module

sys.modules.setdefault("homeassistant", homeassistant_module)
sys.modules.setdefault("homeassistant.config_entries", config_entries_module)
sys.modules.setdefault("homeassistant.core", core_module)
sys.modules.setdefault("homeassistant.exceptions", exceptions_module)
sys.modules.setdefault("homeassistant.helpers", helpers_module)
sys.modules.setdefault("homeassistant.helpers.device_registry", device_registry_module)
sys.modules.setdefault("homeassistant.helpers.update_coordinator", update_coordinator_module)
sys.modules.setdefault("voluptuous", voluptuous_module)

from custom_components.netamp.const import PARAM_SRC
from custom_components.netamp.netamp import NetAmpClient


class NetAmpSourceParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = NetAmpClient(host="127.0.0.1", port=9760, hass=None)  # type: ignore[arg-type]
        self.state = self.client.zones[1]

    def test_explicit_source_sets_last_source_and_clears_standby(self) -> None:
        self.client._apply_param(1, PARAM_SRC, "2")

        self.assertEqual(self.state.source, "2")
        self.assertEqual(self.state.last_source, "2")
        self.assertFalse(self.state.standby)

    def test_off_preserves_last_source(self) -> None:
        self.client._apply_param(1, PARAM_SRC, "3")
        self.client._apply_param(1, PARAM_SRC, "off")

        self.assertEqual(self.state.source, "off")
        self.assertEqual(self.state.last_source, "3")
        self.assertTrue(self.state.standby)

    def test_on_restores_last_source_from_standby(self) -> None:
        self.state.last_source = "1"
        self.state.source = "off"
        self.state.standby = True

        self.client._apply_param(1, PARAM_SRC, "on")

        self.assertFalse(self.state.standby)
        self.assertEqual(self.state.source, "1")

    def test_source_4_is_tracked_as_last_source(self) -> None:
        self.client._apply_param(1, PARAM_SRC, "4")

        self.assertEqual(self.state.source, "4")
        self.assertEqual(self.state.last_source, "4")


if __name__ == "__main__":
    unittest.main()

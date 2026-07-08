from __future__ import annotations

import asyncio
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
voluptuous_module.Optional = lambda key, **kwargs: key
voluptuous_module.All = lambda *validators: validators
voluptuous_module.In = lambda container: container
voluptuous_module.Range = lambda **kwargs: kwargs
voluptuous_module.Coerce = lambda type_: type_

config_entries_module.ConfigEntry = object
core_module.HomeAssistant = object
core_module.ServiceCall = object
exceptions_module.HomeAssistantError = Exception
exceptions_module.ConfigEntryNotReady = Exception
exceptions_module.ServiceValidationError = Exception
device_registry_module.DeviceEntryType = object
device_registry_module.DeviceInfo = dict
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

from custom_components.netamp.const import PARAM_SRC, SRC_VALUES
from custom_components.netamp.netamp import NetAmpClient


class NetAmpSourceParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = NetAmpClient(host="127.0.0.1", port=9760)
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

    def test_src_values_does_not_include_source_4(self) -> None:
        # Source 4 ("3a") is a name/MAC entry but not a selectable source per spec.
        self.assertNotIn("4", SRC_VALUES)
        self.assertIn("1", SRC_VALUES)
        self.assertIn("2", SRC_VALUES)
        self.assertIn("3", SRC_VALUES)
        self.assertIn("loc", SRC_VALUES)


class NetAmpMuteParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = NetAmpClient(host="127.0.0.1", port=9760)
        self.state = self.client.zones[1]

    def test_mute_response_sets_muted(self) -> None:
        # Device responds "$r1mute" — body is "mute" with no "vol" prefix
        self.client._handle_response_line("$r1mute")
        self.assertTrue(self.state.muted)

    def test_moff_response_clears_muted(self) -> None:
        self.state.muted = True
        self.client._handle_response_line("$r1moff")
        self.assertFalse(self.state.muted)

    def test_volmute_response_also_sets_muted(self) -> None:
        # Some firmware may reply $r1volmute; parser handles both formats.
        self.client._handle_response_line("$r1volmute")
        self.assertTrue(self.state.muted)

    def test_volmoff_response_also_clears_muted(self) -> None:
        self.state.muted = True
        self.client._handle_response_line("$r1volmoff")
        self.assertFalse(self.state.muted)


class NetAmpGpvParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = NetAmpClient(host="127.0.0.1", port=9760)

    def test_gpv_response_updates_zone_state(self) -> None:
        # Simulate the multi-line gpv response described in the spec
        for line in ("$r1src3", "$r1vol20", "$r1volvar", "$r1bal0", "$r1bas3", "$r1tre7"):
            self.client._handle_response_line(line)

        st = self.client.zones[1]
        self.assertEqual(st.source, "3")
        self.assertEqual(st.volume, 20)
        self.assertEqual(st.balance, 0)
        self.assertEqual(st.bass, 3)
        self.assertEqual(st.treble, 7)

    def test_gpn_response_updates_zone_name_and_source_names(self) -> None:
        for line in (
            "$r1znnKitchen",
            "$r1sn1AirPlay",
            "$r1sn2DISABLED",
            "$r1sn3NetMusic",
            "$r1sn4NetMusic3a",
            "$r1snlTV",
        ):
            self.client._handle_response_line(line)

        st = self.client.zones[1]
        self.assertEqual(st.zone_name, "Kitchen")
        self.assertEqual(st.sn1, "AirPlay")
        self.assertEqual(st.sn2, "DISABLED")
        self.assertEqual(st.sn3, "NetMusic")
        self.assertEqual(st.sn4, "NetMusic3a")
        self.assertEqual(st.snl, "TV")

    def test_mxv_response_updates_max_volume(self) -> None:
        self.client._handle_response_line("$r1mxv20")
        self.assertEqual(self.client.zones[1].max_volume, 20)

    def test_lim_response_updates_lim(self) -> None:
        self.client._handle_response_line("$r1lima")
        self.assertEqual(self.client.zones[1].lim, "a")

    def test_zone_x_response_updates_all_zones(self) -> None:
        self.client._handle_response_line("$rXvol15")
        self.assertEqual(self.client.zones[1].volume, 15)
        self.assertEqual(self.client.zones[2].volume, 15)

    def test_error_response_raises(self) -> None:
        from custom_components.netamp.netamp import NetAmpProtocolError

        with self.assertRaises(NetAmpProtocolError):
            self.client._handle_response_line("$rxError")

    def test_snapshot_contains_all_zone_fields(self) -> None:
        self.client._handle_response_line("$r1vol12")
        snap = self.client.snapshot()
        self.assertEqual(snap["zones"][1]["volume"], 12)
        self.assertIn("zone_name", snap["zones"][1])
        self.assertIn(2, snap["zones"])


class NetAmpTieredPollingTests(unittest.TestCase):
    """async_update fetches names/mxv/lim only every STATIC_POLL_CYCLES polls."""

    def setUp(self) -> None:
        self.client = NetAmpClient(host="127.0.0.1", port=9760)
        self.sent: list[str] = []

        async def fake_send(cmd: str) -> list[str]:
            self.sent.append(cmd)
            return [cmd]

        self.client._send_and_collect = fake_send  # type: ignore[method-assign]

    def test_first_update_fetches_everything(self) -> None:
        asyncio.run(self.client.async_update())
        self.assertEqual(
            self.sent,
            [
                "$g1gpv", "$g2gpv",
                "$g1gpn", "$g2gpn",
                "$g1mxv", "$g2mxv",
                "$g1lim", "$g2lim",
            ],
        )

    def test_subsequent_updates_only_fetch_gpv(self) -> None:
        asyncio.run(self.client.async_update())
        self.sent.clear()
        asyncio.run(self.client.async_update())
        self.assertEqual(self.sent, ["$g1gpv", "$g2gpv"])

    def test_static_data_refetched_after_cycle(self) -> None:
        from custom_components.netamp.const import STATIC_POLL_CYCLES

        for _ in range(STATIC_POLL_CYCLES):
            asyncio.run(self.client.async_update())
        self.sent.clear()
        asyncio.run(self.client.async_update())
        self.assertIn("$g1gpn", self.sent)
        self.assertIn("$g1mxv", self.sent)
        self.assertIn("$g1lim", self.sent)


if __name__ == "__main__":
    unittest.main()

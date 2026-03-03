from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    ZONES,
    PARAM_SRC,
    PARAM_VOL,
    PARAM_MXV,
    PARAM_BAS,
    PARAM_TRE,
    PARAM_BAL,
    PARAM_ZNN,
    PARAM_SN1,
    PARAM_SN2,
    PARAM_SN3,
    PARAM_SN4,
    PARAM_SNL,
    PARAM_LIM,
    LIM_VALUES,
)

_LOGGER = logging.getLogger(__name__)

# Examples: $r1src3  | $r2vol12 | $r1bas-2 | $r1znnKitchen
# Some firmwares might reply with $r1mute or $r1moff (seen in spec examples).
RESP_RE = re.compile(r"^\$(?P<cmd>r)(?P<zone>[12X])(?P<body>.+)$")

@dataclass
class ZoneState:
    zone: int
    zone_name: str | None = None

    standby: bool | None = None
    source: str | None = None  # "1","2","3","loc"
    last_source: str | None = None
    volume: int | None = None  # 0..30
    muted: bool | None = None

    max_volume: int | None = None  # 0..30
    bass: int | None = None  # -7..7
    treble: int | None = None  # -7..7
    balance: int | None = None  # -15..15

    lim: str | None = None  # "1","a","d"

    # Source names (global + local)
    sn1: str | None = None
    sn2: str | None = None
    sn3: str | None = None
    sn4: str | None = None
    snl: str | None = None

class NetAmpProtocolError(Exception):
    pass

class NetAmpClient:
    def __init__(self, host: str, port: int, hass: HomeAssistant) -> None:
        self._host = host
        self._port = port
        self._hass = hass
        self._lock = asyncio.Lock()
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self.logger = _LOGGER

        self.zones: dict[int, ZoneState] = {z: ZoneState(zone=z) for z in ZONES}

    async def async_ping(self) -> None:
        # Connect and do a lightweight query (gpv zone1). Any response means OK.
        await self._ensure_connected()
        await self._send_and_collect(f"$g1gpv")

    async def async_close(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
        self._reader = None
        self._writer = None

    async def _ensure_connected(self) -> None:
        if self._reader and self._writer and not self._writer.is_closing():
            return
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)

    async def _write_line(self, line: str) -> None:
        if not self._writer:
            raise NetAmpProtocolError("Not connected")
        # NetAmp expects CRLF
        self._writer.write((line + "\r\n").encode("ascii", "ignore"))
        await self._writer.drain()

    async def _read_available_lines(self, idle_timeout: float = 0.25, max_lines: int = 64) -> list[str]:
        """Read lines until no new data arrives for idle_timeout."""
        if not self._reader:
            raise NetAmpProtocolError("Not connected")

        lines: list[str] = []
        while len(lines) < max_lines:
            try:
                raw = await asyncio.wait_for(self._reader.readline(), timeout=idle_timeout)
            except asyncio.TimeoutError:
                break
            if not raw:
                break
            s = raw.decode("ascii", "ignore").strip()
            if s:
                lines.append(s)
        return lines

    async def _send_and_collect(self, cmd: str) -> list[str]:
        async with self._lock:
            await self._ensure_connected()
            await self._write_line(cmd)
            lines = await self._read_available_lines()
            # If device returns nothing, treat as error (could be network drop)
            if not lines:
                raise NetAmpProtocolError("No response from NetAmp")
            # Parse / update state from all lines
            for line in lines:
                self._handle_response_line(line)
            return lines

    def _handle_response_line(self, line: str) -> None:
        # Error example: $rxError
        if line.startswith("$rxError"):
            raise NetAmpProtocolError("NetAmp error response")

        m = RESP_RE.match(line)
        if not m:
            # Ignore anything unexpected
            self.logger.debug("Unparsed NetAmp line: %s", line)
            return

        zone_s = m.group("zone")
        body = m.group("body")

        # Zone can be 'X' for global name commands; we apply those to both zones.
        zones = list(self.zones.keys()) if zone_s == "X" else [int(zone_s)]

        # Identify parameter by known prefixes, longest first
        for param in (PARAM_ZNN, PARAM_SN1, PARAM_SN2, PARAM_SN3, PARAM_SN4, PARAM_SNL,
                      PARAM_MXV, PARAM_SRC, PARAM_VOL, PARAM_BAS, PARAM_TRE, PARAM_BAL, PARAM_LIM):
            if body.startswith(param):
                value = body[len(param):]
                for z in zones:
                    self._apply_param(z, param, value)
                return

        # Handle legacy/typo-ish mute/moff responses ($r1mute, $r1moff)
        if body in ("mute", "moff"):
            for z in zones:
                self.zones[z].muted = (body == "mute")
            return

        self.logger.debug("Unknown NetAmp param in line: %s", line)

    def _apply_param(self, zone: int, param: str, value: str) -> None:
        st = self.zones[zone]
        if param == PARAM_SRC:
    # value like '1','2','3','loc','on','off'
    if value == "off":
        st.standby = True
        # Preserve last known non-off source
        if st.source in ("1", "2", "3", "loc"):
            st.last_source = st.source
        return

    if value == "on":
        # Exit standby and select last playing source (device-side). Keep our last_source if we have it.
        st.standby = False
        if st.last_source and st.source not in ("1", "2", "3", "loc"):
            st.source = st.last_source
        return

    # Any explicit source selection exits standby
    st.standby = False
    st.source = value
    if value in ("1", "2", "3", "loc"):
        st.last_source = value
    return
            if value in ("off",):
                st.source = "off"
                return
            st.source = value
            return

        if param == PARAM_VOL:
            # value might be 'mute'/'moff' or a number or 'var'/'fix'
            if value == "mute":
                st.muted = True
                return
            if value == "moff":
                st.muted = False
                return
            if value in ("var", "fix"):
                # volume mode, not currently surfaced
                return
            try:
                st.volume = int(value)
            except ValueError:
                return
            return

        if param == PARAM_MXV:
            try:
                st.max_volume = int(value)
            except ValueError:
                return
            return

        if param == PARAM_BAS:
            try:
                st.bass = int(value)
            except ValueError:
                return
            return

        if param == PARAM_TRE:
            try:
                st.treble = int(value)
            except ValueError:
                return
            return

        if param == PARAM_BAL:
            try:
                st.balance = int(value)
            except ValueError:
                return
            return

        if param == PARAM_LIM:
            if value in LIM_VALUES:
                st.lim = value
            return

        if param == PARAM_ZNN:
            st.zone_name = value
            return

        if param in (PARAM_SN1, PARAM_SN2, PARAM_SN3, PARAM_SN4, PARAM_SNL):
            setattr(st, param, value)
            return

    async def async_update(self) -> dict[str, Any]:
        """Poll the device."""
        # Pull names occasionally (they don't change often, but cheap enough).
        # We request gpv (values) for both zones, and gpn (names) for zone 1 only (gpn returns global + zone data).
        await self._send_and_collect("$g1gpv")
        await self._send_and_collect("$g2gpv")
        await self._send_and_collect("$g1gpn")
        # Return a serializable snapshot for coordinator consumers
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        return {
            "zones": {
                z: {
                    "zone": st.zone,
                    "zone_name": st.zone_name,
                    "standby": st.standby,
                    "source": st.source,
                    "last_source": st.last_source,
                    "volume": st.volume,
                    "muted": st.muted,
                    "max_volume": st.max_volume,
                    "bass": st.bass,
                    "treble": st.treble,
                    "balance": st.balance,
                    "lim": st.lim,
                    "sn1": st.sn1,
                    "sn2": st.sn2,
                    "sn3": st.sn3,
                    "sn4": st.sn4,
                    "snl": st.snl,
                }
                for z, st in self.zones.items()
            }
        }

    # ----- High level commands -----
    async def async_set_source(self, zone: int, source: str) -> None:
        # source: "1","2","3","loc"
        await self._send_and_collect(f"$s{zone}src{source}")

    async def async_turn_on(self, zone: int) -> None:
        # srcon selects last source
        await self._send_and_collect(f"$s{zone}srcon")

    async def async_turn_off(self, zone: int) -> None:
        await self._send_and_collect(f"$s{zone}srcoff")

    async def async_set_volume(self, zone: int, volume: int) -> None:
        vol = max(0, min(30, int(volume)))
        await self._send_and_collect(f"$s{zone}vol{vol}")

    async def async_volume_step(self, zone: int, direction: str) -> None:
        # direction: "+" or "-"
        if direction not in ("+", "-"):
            raise ValueError("direction must be + or -")
        await self._send_and_collect(f"$s{zone}vol{direction}")

    async def async_set_mute(self, zone: int, muted: bool) -> None:
        await self._send_and_collect(f"$s{zone}vol{'mute' if muted else 'moff'}")

    async def async_set_max_volume(self, zone: int, volume: int) -> None:
        vol = max(0, min(30, int(volume)))
        await self._send_and_collect(f"$s{zone}mxv{vol}")

    async def async_set_bass(self, zone: int, value: int) -> None:
        v = max(-7, min(7, int(value)))
        await self._send_and_collect(f"$s{zone}bas{v}")

    async def async_set_treble(self, zone: int, value: int) -> None:
        v = max(-7, min(7, int(value)))
        await self._send_and_collect(f"$s{zone}tre{v}")

    async def async_set_balance(self, zone: int, value: int) -> None:
        v = max(-15, min(15, int(value)))
        await self._send_and_collect(f"$s{zone}bal{v}")

    async def async_set_lim(self, zone: int, value: str) -> None:
        # value: "1","a","d"
        if value not in LIM_VALUES:
            raise ValueError("Invalid LIM value")
        await self._send_and_collect(f"$s{zone}lim{value}")

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, fields
from typing import Any

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
    SRC_VALUES,
    CONNECT_TIMEOUT,
    MAX_RESPONSE_LINES,
    RESPONSE_IDLE_TIMEOUT,
    STATIC_POLL_CYCLES,
    VOLUME_MAX,
)

_LOGGER = logging.getLogger(__name__)

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
    max_volume: int | None = None
    bass: int | None = None
    treble: int | None = None
    balance: int | None = None
    lim: str | None = None
    sn1: str | None = None
    sn2: str | None = None
    sn3: str | None = None
    sn4: str | None = None
    snl: str | None = None

_ZONE_STATE_FIELDS = tuple(f.name for f in fields(ZoneState))

class NetAmpProtocolError(Exception):
    pass

class NetAmpClient:
    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._lock = asyncio.Lock()
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        # Countdown until the next refresh of rarely-changing data (names, mxv, lim).
        # Starts at 0 so the first update always fetches everything.
        self._static_countdown = 0
        self.zones: dict[int, ZoneState] = {z: ZoneState(zone=z) for z in ZONES}

    async def async_ping(self) -> None:
        await self._send_and_collect("$g1gpv")

    async def async_close(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except (OSError, asyncio.CancelledError) as err:
                _LOGGER.debug("Error closing connection: %s", err)
            finally:
                self._reader = None
                self._writer = None

    async def _ensure_connected(self) -> None:
        if self._reader and self._writer and not self._writer.is_closing():
            return
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port), timeout=CONNECT_TIMEOUT
        )

    async def _write_line(self, line: str) -> None:
        if not self._writer:
            raise NetAmpProtocolError("Not connected")
        self._writer.write((line + "\r\n").encode("ascii", "ignore"))
        await self._writer.drain()

    async def _read_available_lines(self, idle_timeout: float = RESPONSE_IDLE_TIMEOUT, max_lines: int = MAX_RESPONSE_LINES) -> list[str]:
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
            try:
                await self._ensure_connected()
                await self._write_line(cmd)
                lines = await self._read_available_lines()
            except (OSError, asyncio.TimeoutError):
                # Drop the connection so the next command starts from a clean socket.
                await self.async_close()
                raise
            if not lines:
                await self.async_close()
                raise NetAmpProtocolError("No response from NetAmp")
            try:
                for line in lines:
                    self._handle_response_line(line)
            except NetAmpProtocolError:
                await self.async_close()
                raise
            return lines

    def _handle_response_line(self, line: str) -> None:
        if line.startswith("$rxError"):
            raise NetAmpProtocolError("NetAmp error response")
        m = RESP_RE.match(line)
        if not m:
            return
        zone_s = m.group("zone")
        body = m.group("body")
        zones = list(self.zones.keys()) if zone_s == "X" else [int(zone_s)]

        for param in (PARAM_ZNN, PARAM_SN1, PARAM_SN2, PARAM_SN3, PARAM_SN4, PARAM_SNL,
                      PARAM_MXV, PARAM_SRC, PARAM_VOL, PARAM_BAS, PARAM_TRE, PARAM_BAL, PARAM_LIM):
            if body.startswith(param):
                value = body[len(param):]
                for z in zones:
                    self._apply_param(z, param, value)
                return

        if body in ("mute", "moff"):
            for z in zones:
                self.zones[z].muted = (body == "mute")

    def _apply_param(self, zone: int, param: str, value: str) -> None:
        st = self.zones[zone]
        if param == PARAM_SRC:
            if value == "off":
                st.standby = True
                if st.source in SRC_VALUES:
                    st.last_source = st.source
                st.source = "off"
                return
            if value == "on":
                # Per spec the device responds with the actual source (e.g. $r1src1),
                # not $r1srcon, so this branch is not reached from real device responses.
                # Kept as a safe fallback in case of firmware variations.
                st.standby = False
                if st.last_source and st.source not in SRC_VALUES:
                    st.source = st.last_source
                return
            st.standby = False
            st.source = value
            if value in SRC_VALUES:
                st.last_source = value
            return

        if param == PARAM_VOL:
            if value == "mute":
                st.muted = True
            elif value == "moff":
                st.muted = False
            elif value not in ("var", "fix"):
                try:
                    st.volume = int(value)
                except ValueError:
                    pass
            return

        num_params = {
            PARAM_MXV: "max_volume",
            PARAM_BAS: "bass",
            PARAM_TRE: "treble",
            PARAM_BAL: "balance"
        }
        if param in num_params:
            try:
                setattr(st, num_params[param], int(value))
            except ValueError:
                pass
            return

        if param == PARAM_LIM and value in LIM_VALUES:
            st.lim = value
        elif param == PARAM_ZNN:
            st.zone_name = value
        elif param in (PARAM_SN1, PARAM_SN2, PARAM_SN3, PARAM_SN4, PARAM_SNL):
            setattr(st, param, value)

    async def async_update(self) -> dict[str, Any]:
        """Poll the device for current state.

        Volume/source/tone (gpv) is fetched every cycle. Zone/source names,
        max volume and LIM mode change rarely, so they are only refetched
        every STATIC_POLL_CYCLES cycles. Each command pays the response idle
        timeout, so skipping them keeps regular polls fast. Set commands echo
        the new value back and are parsed immediately, so values changed
        through this integration never appear stale.
        """
        # gpv: src, vol, bal, bas, tre for each zone
        await self._send_and_collect("$g1gpv")
        await self._send_and_collect("$g2gpv")
        if self._static_countdown <= 0:
            # gpn: zone name + source names for each zone (zone is don't-care for source names)
            await self._send_and_collect("$g1gpn")
            await self._send_and_collect("$g2gpn")
            # mxv and lim are not included in gpv so must be fetched explicitly
            await self._send_and_collect("$g1mxv")
            await self._send_and_collect("$g2mxv")
            await self._send_and_collect("$g1lim")
            await self._send_and_collect("$g2lim")
            self._static_countdown = STATIC_POLL_CYCLES
        self._static_countdown -= 1
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        return {
            "zones": {
                z: {name: getattr(st, name) for name in _ZONE_STATE_FIELDS}
                for z, st in self.zones.items()
            }
        }

    async def async_set_source(self, zone: int, source: str) -> None:
        await self._send_and_collect(f"$s{zone}src{source}")

    async def async_turn_on(self, zone: int) -> None:
        await self._send_and_collect(f"$s{zone}srcon")

    async def async_turn_off(self, zone: int) -> None:
        await self._send_and_collect(f"$s{zone}srcoff")

    async def async_set_volume(self, zone: int, volume: int) -> None:
        vol = max(0, min(VOLUME_MAX, int(volume)))
        await self._send_and_collect(f"$s{zone}vol{vol}")

    async def async_volume_step(self, zone: int, direction: str) -> None:
        if direction not in ("+", "-"):
            raise ValueError("direction must be + or -")
        await self._send_and_collect(f"$s{zone}vol{direction}")

    async def async_set_mute(self, zone: int, muted: bool) -> None:
        # Spec example: "$s1mute\r\n" / "$s1moff\r\n" — not "$s1volmute"
        await self._send_and_collect(f"$s{zone}{'mute' if muted else 'moff'}")

    async def async_set_max_volume(self, zone: int, volume: int) -> None:
        vol = max(0, min(VOLUME_MAX, int(volume)))
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
        if value not in LIM_VALUES:
            raise ValueError("Invalid LIM value")
        await self._send_and_collect(f"$s{zone}lim{value}")

    async def async_send_raw(self, cmd: str) -> list[str]:
        """Send a raw protocol command and return response lines. For diagnostic use only."""
        return await self._send_and_collect(cmd)

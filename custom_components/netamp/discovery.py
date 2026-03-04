from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Final

_LOGGER = logging.getLogger(__name__)

UDP_PORT: Final = 30303
UDP_PAYLOAD_PREFIX: Final = "IPNetAmp:"
UDP_FIND: Final = "FIND:"

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def _is_mac_address(token: str) -> bool:
    """Return True if *token* looks like a MAC address (XX:XX:XX:XX:XX:XX)."""
    return bool(_MAC_RE.match(token))

@dataclass(frozen=True)
class NetAmpDiscovery:
    ip: str
    logical: str | None = None
    netbios: str | None = None
    mac: str | None = None

class _DiscoveryProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.transport: asyncio.DatagramTransport | None = None
        self.responses: list[str] = []

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr) -> None:
        try:
            s = data.decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001
            return
        self.responses.append(s)

async def async_discover_netamps(timeout: float = 1.0) -> list[NetAmpDiscovery]:
    """Broadcast FIND to locate NetAmp devices.

    Spec: send UDP payload -> "IPNetAmp:X:FIND:" where X is 0 to request all.
    Response payload is a \r\n separated list ending with IP.
    """
    loop = asyncio.get_running_loop()
    proto = _DiscoveryProtocol()

    transport, _ = await loop.create_datagram_endpoint(
        lambda: proto,
        local_addr=("0.0.0.0", 0),
        allow_broadcast=True,
    )

    try:
        # Broadcast address
        payload = f"{UDP_PAYLOAD_PREFIX}0:{UDP_FIND}".encode("ascii", "ignore")
        transport.sendto(payload, ("255.255.255.255", UDP_PORT))

        await asyncio.sleep(timeout)

        devices: dict[str, NetAmpDiscovery] = {}

        for resp in proto.responses:
            # Example response: "IPNetAmp\r\nC\r\nH\r\nL\r\n1\r\n2\r\nFIND\r\nB\r\nM\r\nIP\r\n"
            parts = [p for p in resp.replace("\n", "").split("\r") if p != ""]
            if not parts:
                continue
            if parts[0] != "IPNetAmp":
                continue
            # Ensure at least enough fields; spec shows 11 items after header but may vary.
            ip = parts[-1] if len(parts) >= 2 else None
            if not ip:
                continue

            logical = None
            netbios = None
            mac = None
            # Heuristic: logical number is 4th line (index 3) in spec
            if len(parts) >= 4:
                logical = parts[3]
            # NetBIOSName B is second-to-last 2 lines before mac and ip per spec; but be defensive:
            # spec order: header, C, H, L, 1,2, FIND, B, M, IP
            if len(parts) >= 10:
                netbios = parts[-3]
                mac = parts[-2]
            else:
                # fallback: try to find a MAC-looking token
                for token in parts:
                    if _is_mac_address(token):
                        mac = token
                # netbios: any token that isn't numeric, isn't FIND, isn't MAC, isn't checksum-ish
                for token in reversed(parts):
                    if token in ("IPNetAmp", "FIND"):
                        continue
                    if token.isdigit():
                        continue
                    if _is_mac_address(token):
                        continue
                    if token == ip:
                        continue
                    netbios = token
                    break

            devices[ip] = NetAmpDiscovery(ip=ip, logical=logical, netbios=netbios, mac=mac)

        return sorted(devices.values(), key=lambda d: d.ip)
    finally:
        transport.close()

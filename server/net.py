"""Best-effort discovery of this machine's LAN address(es), so the join link /
QR code can default to something a phone on the same Wi-Fi can actually reach —
without the operator having to look up their IP and set ISAFAN_PUBLIC_URL.

VPN adapters show up here too and can outrank the real Wi-Fi address, so the
whole ordered list is returned; the host screen lets the operator pick another
if the first one doesn't work.
"""

from __future__ import annotations

import ipaddress
import socket


def _primary_ip() -> str | None:
    """Source IP the OS would use to reach the internet — usually the active
    Wi-Fi/Ethernet address. Sends no packets."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def _all_ipv4() -> list[str]:
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except (socket.gaierror, OSError):
        return []
    out: list[str] = []
    for info in infos:
        ip = info[4][0]
        if ip not in out:
            out.append(ip)
    return out


def _usable(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return (
        addr.version == 4
        and addr.is_private
        and not addr.is_loopback
        and not addr.is_link_local
    )


def _rank(ip: str) -> int:
    # Home LANs are overwhelmingly 192.168/16; 172.16/12 next; 10/8 last because
    # that range is also where corporate/consumer VPNs (e.g. Surfshark) land.
    if ip.startswith("192.168."):
        return 0
    if ip.startswith("172."):
        return 1
    return 2


def lan_ips() -> list[str]:
    """Private IPv4 addresses for this host, best guess first."""
    primary = _primary_ip()
    found: list[str] = []
    for ip in ([primary] if primary else []) + _all_ipv4():
        if ip and _usable(ip) and ip not in found:
            found.append(ip)
    found.sort(key=lambda ip: (_rank(ip), 0 if ip == primary else 1))
    return found

"""本机可用于手机连接的地址探测。

以前这段逻辑在桌面端，只给窗口用。现在网页控制台也要展示，
而手机端连的是「服务端认为的地址」而不是某个人机器上的变量，所以收拢到这里。

排序：Tailscale（100.64.0.0/10）→ 局域网（192.168 / 10 / 172.16-31）→ 其它
"""

from __future__ import annotations

import socket


def _is_tailscale(ip: str) -> bool:
    """Tailscale 用 100.64.0.0/10 这段（RFC 6598 的运营商级 NAT）。"""
    if not ip.startswith("100."):
        return False
    try:
        second = int(ip.split(".")[1])
    except (IndexError, ValueError):
        return False
    return 64 <= second <= 127


def _is_private(ip: str) -> bool:
    if ip.startswith("192.168.") or ip.startswith("10."):
        return True
    if ip.startswith("172."):
        try:
            return 16 <= int(ip.split(".")[1]) <= 31
        except (IndexError, ValueError):
            return False
    return False


def _rank(ip: str) -> int:
    if _is_tailscale(ip):
        return 0
    if _is_private(ip):
        return 1
    return 2


def local_addresses() -> list[str]:
    """返回本机所有可用的 IPv4 地址，按「Tailscale → 局域网 → 其它」排序。

    没有 Tailscale 时正常返回局域网地址，不报错也不提示。
    """
    found: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in found and not ip.startswith("127."):
                found.append(ip)
    except Exception:  # noqa: BLE001
        pass

    # 兜底：有些机器主机名解析只返回一个地址，再枚举一次
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in found and not ip.startswith("127."):
                found.append(ip)
    except Exception:  # noqa: BLE001
        pass

    return sorted(found, key=_rank)


def addresses_with_port(port: int) -> list[dict]:
    """给界面用的带端口形式。"""
    out = []
    for ip in local_addresses():
        out.append(
            {
                "address": ip,
                "port": port,
                "kind": "tailscale" if _is_tailscale(ip) else ("lan" if _is_private(ip) else "other"),
            }
        )
    return out

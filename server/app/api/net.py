"""本机网络信息（给网页控制台展示连接地址用）。

免鉴权：网页控制台在**配对之前**就要能看到「该连哪个地址」，
否则用户根本没法开始配对。这里只暴露本机内网地址，不涉及任何凭据。
"""

from __future__ import annotations

import socket

from fastapi import APIRouter, Request

from ..core.config import resolve_port
from ..platform.netinfo import addresses_with_port

router = APIRouter(tags=["net"])


@router.get("/api/net/addresses")
def addresses(request: Request) -> dict:
    # 优先用本次请求实际到达的端口，最能反映真实情况
    port = request.url.port
    if not port:
        port = resolve_port(remember=False)
    return {
        "port": port,
        "hostname": socket.gethostname(),
        "addresses": addresses_with_port(port),
    }

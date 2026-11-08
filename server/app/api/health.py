"""健康检查接口（无需鉴权，用于连接测试）。"""

from __future__ import annotations

import time

from fastapi import APIRouter

from ..core.auth import ensure_pairing_code, has_any_token
from ..core.config import load_config
from ..core.pairing import STATE

router = APIRouter(tags=["health"])

VERSION = "0.1.0"


@router.get("/api/health")
def health() -> dict:
    # 还没有任何设备配对时，保证始终有一个可用的配对码
    if not has_any_token():
        due = (STATE.pairing_code is None) or (
            time.monotonic() > STATE.pairing_code_expires_at
        )
        if due:
            ensure_pairing_code(int(load_config().get("pairing_code_ttl_seconds", 300)))

    return {
        "ok": True,
        "version": VERSION,
        "pairing_pending": not has_any_token(),
        "server_time": STATE.now_iso(),
        "uptime_seconds": STATE.uptime_seconds(),
    }

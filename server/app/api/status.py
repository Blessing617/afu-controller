"""服务自检状态（需要 token）。"""

from __future__ import annotations

from fastapi import APIRouter

from ..platform import winutil
from ..platform.discovery import detect_all
from ..core.pairing import STATE

router = APIRouter(tags=["status"])

VERSION = "0.1.0"


@router.get("/api/status")
def status() -> dict:
    return {
        "version": VERSION,
        "locked": winutil.is_locked(),
        "is_admin": winutil.is_admin(),
        "server_time": STATE.now_iso(),
        "uptime_seconds": STATE.uptime_seconds(),
        "current_task": STATE.current_task,
        "paths": detect_all(),
    }

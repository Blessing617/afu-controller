"""临时调试接口。仅允许本机调用，定位完应删除。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(tags=["debug"])


class WriteTestRequest(BaseModel):
    dir: str


def _local(request: Request) -> bool:
    return request.client.host in ("127.0.0.1", "::1")


def _run(cmd: list[str]) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=20, stdin=subprocess.DEVNULL, creationflags=0x08000000)
        raw = out.stdout or out.stderr
        for enc in ("gbk", "utf-8"):
            try:
                return raw.decode(enc)
            except Exception:
                continue
        return raw.decode("utf-8", errors="replace")
    except Exception as exc:
        return f"ERR {exc}"


@router.get("/api/debug/token")
def token_info(request: Request) -> dict:
    """完整令牌信息：whoami /all 原始输出 + 完整性级别。"""
    if not _local(request):
        raise HTTPException(status_code=403, detail="local only")

    integrity = ""
    try:
        import ctypes
        from ctypes import wintypes

        TOKEN_QUERY = 0x0008
        TokenIntegrityLevel = 25
        h = wintypes.HANDLE()
        ctypes.windll.advapi32.OpenProcessToken(
            ctypes.windll.kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(h)
        )
        size = wintypes.DWORD(0)
        ctypes.windll.advapi32.GetTokenInformation(h, TokenIntegrityLevel, None, 0, ctypes.byref(size))
        buf = ctypes.create_string_buffer(size.value)
        ok = ctypes.windll.advapi32.GetTokenInformation(
            h, TokenIntegrityLevel, buf, size, ctypes.byref(size)
        )
        if ok:
            sid_ptr = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
            sub_auth_count = ctypes.cast(sid_ptr, ctypes.POINTER(ctypes.c_ubyte))[1]
            last = ctypes.cast(sid_ptr + 8 + (sub_auth_count - 1) * 4, ctypes.POINTER(ctypes.c_ulong))[0]
            levels = {0x1000: "Low", 0x2000: "Medium", 0x2100: "MediumPlus", 0x3000: "High", 0x4000: "System"}
            integrity = levels.get(last, f"0x{last:X}")
    except Exception as exc:
        integrity = f"ERR {exc}"

    return {
        "integrity_level": integrity,
        "whoami_all": _run(["whoami", "/all"]),
        "cwd": os.getcwd(),
        "temp": os.environ.get("TEMP", ""),
    }


@router.post("/api/debug/write-test")
def write_test(req: WriteTestRequest, request: Request) -> dict:
    if not _local(request):
        raise HTTPException(status_code=403, detail="local only")
    target = Path(req.dir)
    if not target.is_dir():
        raise HTTPException(status_code=400, detail=f"目录不存在：{target}")
    result = {"dir": str(target), "writable": False, "error": ""}
    tmp = target / "_admin_write_test.txt"
    try:
        tmp.write_text("ok", encoding="utf-8")
        tmp.unlink(missing_ok=True)
        result["writable"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result

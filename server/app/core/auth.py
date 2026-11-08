"""配对与 token 鉴权。

- 首次连接：用一次性配对码换长期 token（`POST /api/pair`）
- 之后每次请求携带 `Authorization: Bearer <token>`
- token 落盘在 `server/data/auth.json`，服务重启后仍然有效
"""

from __future__ import annotations

import json
import secrets
import time
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse

from .config import DATA_DIR
from .pairing import STATE

AUTH_FILE: Path = DATA_DIR / "auth.json"
PAIRING_HINT_FILE: Path = DATA_DIR / "pairing_code.txt"

# 不需要 token 的路径
PUBLIC_PATHS = {
    "/api/health",
    "/api/pair",
    "/api/pair/status",
    # 网页控制台在配对前就要能显示连接地址与「还缺什么软件」，
    # 否则新用户无法开始配对（/api/deps 不返回安装路径，见该接口注释）
    "/api/net/addresses",
    "/api/deps",
    # 首次引导：新用户还没配对，引导页必须能开
    "/api/onboarding/status",
    "/api/onboarding/done",
    "/welcome",
    # MAA 远程控制协议：MAA 不带 token 来轮询
    "/api/maa/getTask",
    "/api/maa/reportStatus",
    "/docs",
    "/openapi.json",
    "/redoc",
}

# 免鉴权的静态资源前缀：控制台页面本身与自托管的文档资源
PUBLIC_PREFIXES = (
    "/static/",
    "/docs",
    "/redoc",
    "/swagger-assets/",
    "/swagger-ui/",
)


def _load() -> dict:
    if not AUTH_FILE.exists():
        return {"tokens": []}
    try:
        return json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"tokens": []}


def _save(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def issue_token(device: str = "") -> str:
    """签发新 token 并落盘。"""
    token = secrets.token_urlsafe(32)
    data = _load()
    data.setdefault("tokens", []).append(
        {"token": token, "device": device, "issued_at": int(time.time())}
    )
    _save(data)
    STATE.paired = True
    return token


def token_valid(token: str) -> bool:
    if not token:
        return False
    return any(item.get("token") == token for item in _load().get("tokens", []))


def has_any_token() -> bool:
    return bool(_load().get("tokens"))


def extract_token(request: Request) -> str:
    raw = request.headers.get("authorization", "")
    if raw.lower().startswith("bearer "):
        return raw[7:].strip()
    return request.headers.get("x-token", "").strip()


def publish_pairing_code(ttl_seconds: int) -> str:
    """生成配对码：打印到日志、写提示文件，方便用户在电脑上看到。"""
    code = STATE.issue_pairing_code(ttl_seconds)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PAIRING_HINT_FILE.write_text(
        f"{code}\n（{ttl_seconds} 秒内有效，仅可使用一次）\n", encoding="utf-8"
    )
    print(f"[pair] 配对码：{code}（{ttl_seconds} 秒内有效）", flush=True)
    return code


def ensure_pairing_code(ttl_seconds: int) -> str:
    """若当前没有有效配对码则补发一个；已配对则不分配。"""
    if has_any_token():
        return ""
    return publish_pairing_code(ttl_seconds)


async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if path in PUBLIC_PATHS:
        return await call_next(request)
    if any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
        return await call_next(request)
    # 网页控制台首页本身
    if path in ("/", "/index.html"):
        return await call_next(request)
    if not token_valid(extract_token(request)):
        return JSONResponse(
            status_code=401,
            content={"error": "unauthorized", "message": "缺少或无效的 token，请先配对"},
        )
    return await call_next(request)

"""配对接口。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.auth import has_any_token, issue_token, publish_pairing_code
from ..core.config import load_config
from ..core.pairing import STATE

router = APIRouter(tags=["pair"])


class PairRequest(BaseModel):
    code: str
    device: str = ""


@router.post("/api/pair")
def pair(req: PairRequest) -> dict:
    if not STATE.check_pairing_code(req.code):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_code", "message": "配对码无效或已过期，请在电脑上重新生成"},
        )
    token = issue_token(req.device)
    return {"token": token, "paired": True}


@router.post("/api/pair/refresh")
def refresh_pairing_code() -> dict:
    """重新生成配对码（本机调试用；受 token 保护）。"""
    cfg = load_config()
    ttl = int(cfg.get("pairing_code_ttl_seconds", 300))
    code = publish_pairing_code(ttl)
    return {"code": code, "ttl_seconds": ttl}


@router.get("/api/pair/status")
def pair_status() -> dict:
    return {"paired": has_any_token(), "code_pending": STATE.pairing_code is not None}

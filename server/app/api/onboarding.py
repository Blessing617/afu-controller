"""首次引导接口。

引导内容是「许可 + 依赖检查 + 怎么连手机」，走浏览器页面展示。
不做成桌面模态框的原因：引导要放官网链接和较长的说明，tkinter 里排版很难看。
"""

from __future__ import annotations

from fastapi import APIRouter

from ..core.auth import has_any_token
from ..core.config import is_first_run, mark_onboarding_done

router = APIRouter(tags=["onboarding"])


@router.get("/api/onboarding/status")
def status() -> dict:
    return {
        "first_run": is_first_run(),
        "paired": has_any_token(),
    }


@router.post("/api/onboarding/done")
def done() -> dict:
    mark_onboarding_done()
    return {"ok": True}

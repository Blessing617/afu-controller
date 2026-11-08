"""MAA 远程控制协议端点（MAA 侧调用，无需 token）。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..engine.maa import MAA

router = APIRouter(tags=["maa"])


@router.post("/api/maa/getTask")
async def get_task(request: Request) -> dict:
    # MAA 的请求体可能是空的（实测），读不出来也不影响
    try:
        await request.body()
    except Exception:
        pass
    return {"tasks": MAA.take_tasks()}


@router.post("/api/maa/reportStatus")
async def report_status(request: Request) -> dict:
    body: dict = {}
    try:
        raw = await request.body()
        if raw:
            import json

            body = json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        body = {}

    task_id = str(body.get("task", ""))
    status = str(body.get("status", ""))
    payload = body.get("payload", "")
    result = MAA.on_report(task_id, status, payload if isinstance(payload, str) else "")
    return {"ok": True, **result}


@router.get("/api/maa/status")
def maa_status() -> dict:
    return MAA.stats()

"""WebSocket 事件流。

任务状态变化与日志行通过这里推给 APP，避免前端靠轮询。
鉴权：连接时带 `?token=...`（HTTP 中间件不覆盖 WebSocket）。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..core.auth import token_valid

router = APIRouter(tags=["ws"])


class Hub:
    """保存活跃连接，并把后台线程的事件安全地投递到事件循环。"""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)
        if self._loop is None:
            self._loop = asyncio.get_running_loop()

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def _send(self, ws: WebSocket, text: str) -> None:
        try:
            await ws.send_text(text)
        except Exception:
            self.disconnect(ws)

    def broadcast(self, event: dict[str, Any]) -> None:
        """可从任意线程调用。"""
        if not self._clients:
            return
        text = json.dumps(event, ensure_ascii=False, default=str)
        loop = self._loop
        if loop is None or not loop.is_running():
            return
        for ws in list(self._clients):
            try:
                asyncio.run_coroutine_threadsafe(self._send(ws, text), loop)
            except Exception:
                self.disconnect(ws)


HUB = Hub()


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    token = ws.query_params.get("token", "")
    if not token_valid(token):
        await ws.close(code=4401)
        return

    await HUB.connect(ws)
    try:
        await ws.send_text(json.dumps({"type": "hello"}, ensure_ascii=False))
        while True:
            # 客户端不需要发东西；这里只是保持连接并响应 ping
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        HUB.disconnect(ws)


def emit_task_event(kind: str, run) -> None:
    """把任务事件交给 Hub 广播。run 为 TaskRun。"""
    try:
        HUB.broadcast({"type": "task", "event": kind, "task": run.to_dict()})
    except Exception:
        pass


def emit_chain_event(kind: str, chain_run) -> None:
    """把任务链事件交给 Hub 广播。

    与单任务的 {"type":"task"} 并存，老客户端忽略即可。
    """
    try:
        HUB.broadcast({"type": "chain", "event": kind, "chain": chain_run.to_dict()})
    except Exception:
        pass

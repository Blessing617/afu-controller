"""启动期（lifespan）的回归测试。

为什么要单独立这一条：lifespan 里有一批**延迟导入**（编排器、配对状态、唤醒），
分层重构时最容易漏改。而 `TestClient(app)` 不写 `with` 是不会触发 lifespan 的，
所以那批代码可以一直坏着而 114 个测试全绿——2026-11-08 就是这么翻的车：
`from .orchestrator import ...` 没跟着搬到 `core/`，应用一启动就退出，
界面永远显示「正在启动…」。
"""

from __future__ import annotations

import asyncio

import pytest


def test_lifespan_starts_and_stops(monkeypatch):
    from app import main as m

    # 唤醒线程与配对码不需要真的跑
    monkeypatch.setattr(m.keepawake, "start", lambda *a, **k: None)
    monkeypatch.setattr(m.keepawake, "stop", lambda *a, **k: None)
    monkeypatch.setattr(m, "ensure_pairing_code", lambda *a, **k: None)

    async def _run():
        async with m.lifespan(m.app):
            pass

    asyncio.run(_run())   # 起不来会在这里抛 ModuleNotFoundError / ImportError


def test_lifespan_registers_listeners(monkeypatch):
    """监听器要真的接到状态机上（否则手机端收不到任务事件）。"""
    from app import main as m
    from app.core import orchestrator as orch
    from app.core import state as st

    monkeypatch.setattr(m.keepawake, "start", lambda *a, **k: None)
    monkeypatch.setattr(m.keepawake, "stop", lambda *a, **k: None)
    monkeypatch.setattr(m, "ensure_pairing_code", lambda *a, **k: None)

    before_tasks = len(st._listeners)
    before_chain = len(orch._listeners)

    async def _run():
        async with m.lifespan(m.app):
            pass

    asyncio.run(_run())

    assert len(st._listeners) >= before_tasks
    assert len(orch._listeners) >= before_chain
    assert st._listeners, "任务事件监听器没注册上"
    assert orch._listeners, "链事件监听器没注册上"


def test_health_endpoint_works(monkeypatch):
    from fastapi.testclient import TestClient

    from app import main as m

    monkeypatch.setattr(m.keepawake, "start", lambda *a, **k: None)
    monkeypatch.setattr(m.keepawake, "stop", lambda *a, **k: None)
    monkeypatch.setattr(m, "ensure_pairing_code", lambda *a, **k: None)

    with TestClient(m.app) as client:      # with 才会跑 lifespan
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["ok"] is True

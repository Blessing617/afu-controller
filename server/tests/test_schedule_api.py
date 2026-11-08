"""定时接口：配置读写与强制停止。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app.core import auth, schedule
    from app.main import app

    monkeypatch.setattr(auth, "token_valid", lambda token: True)
    monkeypatch.setattr(schedule, "SCHEDULE_FILE", tmp_path / "schedule.json")
    return TestClient(app)


def test_get_returns_shape(client):
    r = client.get("/api/schedule")
    assert r.status_code == 200
    body = r.json()
    for key in ("enabled", "times", "weekdays", "next_run", "scheduler_running", "last_runs"):
        assert key in body
    assert body["enabled"] is False
    assert body["times"] == []


def test_put_saves_and_returns_next_run(client):
    r = client.put(
        "/api/schedule",
        json={"enabled": True, "times": ["08:00", "20:00"], "weekdays": []},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert body["times"] == ["08:00", "20:00"]
    assert body["next_run"] is not None

    again = client.get("/api/schedule").json()
    assert again["enabled"] is True
    assert again["times"] == ["08:00", "20:00"]


def test_put_rejects_bad_time(client):
    r = client.put("/api/schedule", json={"enabled": True, "times": ["25:99"]})
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_schedule"


def test_put_rejects_too_many(client):
    r = client.put(
        "/api/schedule",
        json={"times": [f"{h:02d}:00" for h in range(1, 10)]},
    )
    assert r.status_code == 400


def test_put_keeps_fired_history(client, monkeypatch):
    """改时间点不该让「今天已经跑过」失效，否则同一天会重复触发。"""
    from datetime import datetime

    from app.core import schedule as mod

    sched = mod.load_schedule()
    sched.mark_fired(datetime.now(), "08:00")
    mod.save_schedule(sched)

    r = client.put("/api/schedule", json={"enabled": True, "times": ["08:00"]})
    assert r.status_code == 200

    reloaded = mod.load_schedule()
    assert reloaded.last_fired, "last_fired 被清掉了，会导致同日重复触发"


def test_stop_calls_reset(client, monkeypatch):
    from app.api import schedule as api_mod

    calls = []
    def _fake_reset():
        calls.append("reset")
        return ["MuMuNxMain.exe"], ""

    monkeypatch.setattr(api_mod, "reset_environment", _fake_reset)
    r = client.post("/api/schedule/stop")
    assert r.status_code == 200
    assert calls == ["reset"]
    assert r.json()["killed"] == ["MuMuNxMain.exe"]


def test_stop_reports_nothing_to_close(client, monkeypatch):
    from app.api import schedule as api_mod

    monkeypatch.setattr(api_mod, "reset_environment", lambda: ([], ""))
    r = client.post("/api/schedule/stop")
    assert r.json()["killed"] == []
    assert "没有需要关闭" in r.json()["message"]

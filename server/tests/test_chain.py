"""任务链与编排的测试。

这些测试不依赖真实引擎：执行器用 monkeypatch 假造，
真实引擎的验收在实机上做（见 tasks.md 第 6 组）。
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from app.core import chain as chain_mod
from app.core.chain import Chain, ChainError, ChainStep


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """已配对 + 数据目录指向 tmp 的客户端。"""
    from app.core import auth
    from app.main import app

    monkeypatch.setattr(auth, "token_valid", lambda token: True)
    monkeypatch.setattr(chain_mod, "CHAIN_FILE", tmp_path / "chain.json")
    return TestClient(app)


# ---------------------------------------------------------------- 数据模型
def test_default_chain_has_three_steps():
    c = Chain.default()
    assert [s.game for s in c.steps] == ["arknights", "genshin", "starrail"]
    assert all(s.enabled for s in c.steps)
    assert c.policy == "skip"


def test_chain_roundtrip():
    c = Chain.default()
    c.steps[0].tasks = ["Infrast", "Recruit"]
    c.steps[1].enabled = False
    data = c.to_dict()
    assert Chain.from_dict(data).to_dict() == data


def test_chain_rejects_bad_input():
    with pytest.raises(ChainError):
        Chain.from_dict({"steps": "nope"})
    with pytest.raises(ChainError):
        Chain.from_dict({"steps": [{"game": "minecraft"}]})
    with pytest.raises(ChainError):
        Chain.from_dict({"steps": [{"game": "genshin"}] * 11})


def test_chain_dedupes_tasks_keeping_order():
    c = Chain.from_dict(
        {"steps": [{"game": "genshin", "tasks": ["a", "b", "a"]}]}
    )
    assert c.steps[0].tasks == ["a", "b"]


def test_same_game_can_repeat():
    c = Chain.from_dict(
        {
            "steps": [
                {"game": "genshin"},
                {"game": "starrail"},
                {"game": "genshin", "label": "收尾"},
            ]
        }
    )
    assert [s.game for s in c.steps] == ["genshin", "starrail", "genshin"]
    assert c.steps[2].display_name == "收尾"


def test_empty_for_run():
    c = Chain.from_dict({"steps": [{"game": "genshin", "enabled": False}]})
    assert c.is_empty_for_run()


# ---------------------------------------------------------------- 接口
def test_get_chain_returns_default(client):
    r = client.get("/api/chain")
    assert r.status_code == 200
    assert len(r.json()["chain"]["steps"]) == 3


def test_put_chain_saves_and_backs_up(client, tmp_path):
    payload = {
        "steps": [{"game": "genshin"}, {"game": "starrail"}],
        "policy": "stop",
    }
    r = client.put("/api/chain", json=payload)
    assert r.status_code == 200
    saved = json.loads((tmp_path / "chain.json").read_text(encoding="utf-8"))
    assert [s["game"] for s in saved["steps"]] == ["genshin", "starrail"]
    assert saved["policy"] == "stop"

    # 再存一次，应生成备份
    client.put("/api/chain", json={"steps": [{"game": "genshin"}]})
    assert (tmp_path / "chain.json.bak").is_file()


def test_put_chain_rejects_invalid(client):
    r = client.put("/api/chain", json={"steps": [{"game": "nope"}]})
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_chain"


def test_engine_tasks_falls_back_when_missing(client, monkeypatch):
    monkeypatch.setattr(
        "app.platform.discovery.detect_all",
        lambda **kw: {
            "maa": {"found": False, "path": ""},
            "bettergi": {"found": False, "path": ""},
            "m7a": {"found": False, "path": ""},
        },
    )
    for game in ("arknights", "genshin", "starrail"):
        r = client.get(f"/api/engines/{game}/tasks")
        assert r.status_code == 200
        body = r.json()
        assert body["source"] == "error"
        assert body["items"], "兜底清单不能为空"


def test_engine_tasks_unknown_game(client):
    assert client.get("/api/engines/minecraft/tasks").status_code == 404


def test_chain_run_rejects_empty(client, tmp_path):
    client.put("/api/chain", json={"steps": [{"game": "genshin", "enabled": False}]})
    r = client.post("/api/chain/run")
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "empty_chain"


# ---------------------------------------------------------------- 调度器
class FakeEngine:
    """假造引擎执行：可控制每一步成功/失败/耗时。"""

    def __init__(self, results: dict[str, str]):
        self.results = results
        self.calls: list[str] = []

    def __call__(self, game, *, chain_id="", tasks=None, from_chain=False):
        from app.core.state import RUNNER, TaskState

        self.calls.append(game)
        run = RUNNER.try_start(game, f"fake-{game}")
        run.chain_id = chain_id
        state = {
            "success": TaskState.SUCCESS,
            "failed": TaskState.FAILED,
        }.get(self.results.get(game, "success"), TaskState.SUCCESS)
        RUNNER.finish(run, state, error="" if state == TaskState.SUCCESS else "模拟失败")
        return run


def _run_chain(monkeypatch, steps, results, policy="skip"):
    from app.core import orchestrator
    from app.core import tasks as tasks_api

    fake = FakeEngine(results)
    monkeypatch.setattr(tasks_api, "start_single", fake)
    monkeypatch.setattr(tasks_api, "stop_current", lambda: None)

    orch = orchestrator.Orchestrator()
    chain = Chain.from_dict({"steps": steps, "policy": policy})
    run = orch.start(chain)

    for _ in range(200):
        if run.state == "finished":
            break
        time.sleep(0.02)
    return orch, run, fake


def test_chain_runs_in_order(monkeypatch):
    from app.core.state import RUNNER

    RUNNER._current = None
    RUNNER._history.clear()
    _, run, fake = _run_chain(
        monkeypatch,
        [
            {"game": "starrail"},
            {"game": "arknights"},
            {"game": "genshin"},
        ],
        {},
    )
    assert fake.calls == ["starrail", "arknights", "genshin"]
    assert all(s.state.value == "success" for s in run.steps)


def test_disabled_step_is_skipped(monkeypatch):
    from app.core.state import RUNNER

    RUNNER._current = None
    RUNNER._history.clear()
    _, run, fake = _run_chain(
        monkeypatch,
        [
            {"game": "arknights", "enabled": False},
            {"game": "genshin"},
        ],
        {},
    )
    assert fake.calls == ["genshin"]
    assert run.steps[0].state.value == "skipped"
    assert run.steps[1].state.value == "success"


def test_failure_skip_policy(monkeypatch):
    from app.core.state import RUNNER

    RUNNER._current = None
    RUNNER._history.clear()
    _, run, fake = _run_chain(
        monkeypatch,
        [{"game": "arknights"}, {"game": "genshin"}, {"game": "starrail"}],
        {"arknights": "failed"},
        policy="skip",
    )
    assert fake.calls == ["arknights", "genshin", "starrail"]
    assert run.steps[0].state.value == "failed"
    assert run.steps[1].state.value == "success"
    assert run.summary()["failed"] == 1
    assert run.summary()["success"] == 2


def test_failure_stop_policy(monkeypatch):
    from app.core.state import RUNNER

    RUNNER._current = None
    RUNNER._history.clear()
    _, run, fake = _run_chain(
        monkeypatch,
        [{"game": "arknights"}, {"game": "genshin"}, {"game": "starrail"}],
        {"arknights": "failed"},
        policy="stop",
    )
    assert fake.calls == ["arknights"]
    assert run.steps[0].state.value == "failed"
    assert run.steps[1].state.value == "not_run"
    assert run.steps[2].state.value == "not_run"


def test_chain_carries_task_selection(monkeypatch):
    """选中的子任务要跟着 chain 传到执行器。"""
    from app.core import tasks as tasks_api
    from app.core import orchestrator

    seen = {}

    def fake(game, *, chain_id="", tasks=None, from_chain=False):
        from app.core.state import RUNNER, TaskState

        seen[game] = list(tasks or [])
        run = RUNNER.try_start(game, "fake")
        RUNNER.finish(run, TaskState.SUCCESS)
        return run

    from app.core.state import RUNNER

    RUNNER._current = None
    RUNNER._history.clear()
    monkeypatch.setattr(tasks_api, "start_single", fake)
    orch = orchestrator.Orchestrator()
    chain = Chain.from_dict(
        {"steps": [{"game": "arknights", "tasks": ["Infrast", "Recruit"]}]}
    )
    run = orch.start(chain)
    for _ in range(100):
        if run.state == "finished":
            break
        time.sleep(0.02)
    assert seen["arknights"] == ["Infrast", "Recruit"]


def test_stop_mid_chain(monkeypatch):
    """跑到一半停：当前步 stopped，后续 not_run，已完成的保留结果。"""
    from app.core import orchestrator
    from app.core import tasks as tasks_api
    from app.core.state import RUNNER, TaskState

    RUNNER._current = None
    RUNNER._history.clear()

    started = []

    def slow(game, *, chain_id="", tasks=None, from_chain=False):
        started.append(game)
        run = RUNNER.try_start(game, f"slow-{game}")
        if len(started) >= 2:
            # 第二步不结束，交给用户停止
            return run
        RUNNER.finish(run, TaskState.SUCCESS)
        return run

    stopped = {"done": False}

    def stop():
        stopped["done"] = True
        cur = RUNNER.current()
        if cur is not None:
            RUNNER.finish(cur, TaskState.STOPPED, error="用户停止")

    monkeypatch.setattr(tasks_api, "start_single", slow)
    monkeypatch.setattr(tasks_api, "stop_current", stop)

    orch = orchestrator.Orchestrator()
    chain = Chain.from_dict(
        {"steps": [{"game": "arknights"}, {"game": "genshin"}, {"game": "starrail"}]}
    )
    run = orch.start(chain)

    for _ in range(200):
        if len(started) >= 2:
            break
        time.sleep(0.02)
    orch.request_stop()

    for _ in range(200):
        if run.state == "finished":
            break
        time.sleep(0.02)

    assert run.steps[0].state.value == "success"
    assert run.steps[1].state.value == "stopped"
    assert run.steps[2].state.value == "not_run"
    assert stopped["done"], "应该确实调用了 stop_current"


def test_orchestrator_is_not_blocked_by_its_own_guard(monkeypatch):
    """回归测试：调度器调用 start_single 时不能被「链在运行」的互斥检查挡住。

    曾经踩过：ORCH.start() 先把状态置成 running，工作线程再调 start_single
    时被自己设的检查拦下，导致整条链三步全失败。
    """
    from app.core import orchestrator
    from app.core import tasks as tasks_api
    from app.core.state import RUNNER, TaskState

    RUNNER._current = None
    RUNNER._history.clear()

    # 用真实的 start_single，只把引擎执行替换掉
    def fake_execute(game, run, paths, tasks):
        RUNNER.finish(run, TaskState.SUCCESS)

    monkeypatch.setattr(tasks_api, "_execute", fake_execute)
    monkeypatch.setattr(
        tasks_api, "precheck", lambda game: {k: {"found": True, "path": "x"} for k in
                                              ("genshin", "bettergi", "starrail", "m7a",
                                               "maa", "mumu")}
    )

    orch = orchestrator.Orchestrator()
    chain = Chain.from_dict({"steps": [{"game": "genshin"}]})
    run = orch.start(chain)
    for _ in range(200):
        if run.state == "finished":
            break
        time.sleep(0.02)
    # 关键断言：不能因为「正在执行任务链」而失败
    assert run.steps[0].state.value == "success", run.steps[0].error
    assert "正在执行任务链" not in run.steps[0].error

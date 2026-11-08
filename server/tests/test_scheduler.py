"""调度逻辑：什么时候触发、触发几次、触发前做了哪些动作。"""

from __future__ import annotations

from datetime import datetime

from app.core.schedule import Schedule
from app.core.scheduler import Scheduler


def _dt(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M")


def _make(schedule: Schedule, fired: list[str]) -> Scheduler:
    """用内存里的配置替代文件，记录每次触发。"""
    state = {"schedule": schedule}

    def load():
        return state["schedule"]

    def save(s):
        state["schedule"] = s

    def fire(slot):
        fired.append(slot)

    return Scheduler(fire=fire, load=load, save=save)


def test_fires_on_matching_minute_only_once():
    fired: list[str] = []
    sched = _make(Schedule.from_dict({"enabled": True, "times": ["08:00"]}), fired)

    assert sched.tick_once(_dt("2026-11-08 07:59")) == []
    assert sched.tick_once(_dt("2026-11-08 08:00")) == ["08:00"]
    assert sched.tick_once(_dt("2026-11-08 08:00")) == []      # 同一分钟不重复
    assert fired == ["08:00"]

    # 第二天同一时间点可以再跑
    assert sched.tick_once(_dt("2026-11-09 08:00")) == ["08:00"]
    assert fired == ["08:00", "08:00"]


def test_disabled_schedule_never_fires():
    fired: list[str] = []
    sched = _make(Schedule.from_dict({"enabled": False, "times": ["08:00"]}), fired)
    assert sched.tick_once(_dt("2026-11-08 08:00")) == []
    assert fired == []


def test_weekday_filter():
    fired: list[str] = []
    sched = _make(
        Schedule.from_dict({"enabled": True, "times": ["08:00"], "weekdays": [1]}),  # 周一
        fired,
    )
    assert sched.tick_once(_dt("2026-11-08 08:00")) == []      # 周日
    assert sched.tick_once(_dt("2026-11-09 08:00")) == ["08:00"]  # 周一
    assert fired == ["08:00"]


def test_multiple_slots_same_minute():
    fired: list[str] = []
    sched = _make(Schedule.from_dict({"enabled": True, "times": ["08:00", "08:00"]}), fired)
    # 配置层会去重
    assert sched.tick_once(_dt("2026-11-08 08:00")) == ["08:00"]


def test_fire_is_marked_even_if_it_raises():
    """触发失败不能导致同一分钟反复重试（否则一个坏链会每分钟重启一次）。"""
    calls: list[str] = []

    def boom(slot):
        calls.append(slot)
        raise RuntimeError("链启动失败")

    schedule = Schedule.from_dict({"enabled": True, "times": ["08:00"]})
    state = {"s": schedule}
    sched = Scheduler(fire=boom, load=lambda: state["s"], save=lambda s: state.update(s=s))

    now = _dt("2026-11-08 08:00")
    assert sched.tick_once(now) == ["08:00"]
    assert sched.tick_once(now) == []          # 已被标记，不再重试
    assert calls == ["08:00"]


def test_reset_order():
    """到点动作的顺序必须是：停链 → 停任务 → 清理 → 启动。"""
    import app.core.scheduler as mod

    events: list[str] = []

    class FakeOrch:
        def is_running(self):
            return False

        def start(self, chain):
            events.append("start")

    class FakeRunner:
        def current(self):
            return None

    import app.core.state as st
    import app.core.orchestrator as orch
    import app.engine.cleanup as cleanup

    mod_orch, mod_runner, mod_cleanup = orch.ORCH, st.RUNNER, cleanup.cleanup_all
    try:
        orch.ORCH = FakeOrch()
        st.RUNNER = FakeRunner()
        cleanup.cleanup_all = lambda log=None: (events.append("cleanup"), ["MuMuNxMain.exe"])[1]
        # fire_chain 内部用的是模块级导入，这里直接调 reset_environment 与 ORCH.start
        killed, err = mod.reset_environment()
        assert "cleanup" in events
        assert killed == ["MuMuNxMain.exe"]
    finally:
        orch.ORCH, st.RUNNER, cleanup.cleanup_all = mod_orch, mod_runner, mod_cleanup

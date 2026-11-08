"""卡死判定的测试。

关键要证明的是：判定看的是「距最后一次进展」而不是「启动后多久」。
"""

from __future__ import annotations

from app.core.stall import OK, STALLED, TOO_LONG, NO_START, StallWatch

MIN = 60.0


def test_slow_but_steady_task_is_never_killed():
    """慢机器上跑 35 分钟、但一直有进展 —— 不该被杀。"""
    watch = StallWatch(started_at=0.0)
    now = 0.0

    # 每 2 分钟来一次进展，持续 35 分钟
    for _ in range(18):
        now += 2 * MIN
        watch.progress(at=now)
        assert watch.verdict(now + 30) == OK

    assert watch.verdict(now) == OK
    # 总时长已经远超「20 分钟」这类固定上限
    assert now > 35 * MIN


def test_stalled_after_idle_minutes():
    watch = StallWatch(started_at=0.0)
    watch.progress(at=1 * MIN)
    assert watch.verdict(1 * MIN + 30) == OK
    # 10 分钟无进展
    assert watch.verdict(1 * MIN + 10 * MIN + 1) == STALLED


def test_no_start_if_never_progressed():
    watch = StallWatch(started_at=0.0)
    assert watch.verdict(5 * MIN) == OK
    assert watch.verdict(15 * MIN + 1) == NO_START


def test_hard_cap_for_endless_progress():
    """一直有进展却永不结束 —— 只能靠兜底。"""
    watch = StallWatch(started_at=0.0)
    now = 0.0
    for _ in range(100):
        now += 5 * MIN
        watch.progress(at=now)
    # 已经 8 小时
    assert watch.verdict(now) == TOO_LONG


def test_independent_of_start_time():
    """两个任务启动时间差很远，但「距上次进展」相同，判定必须相同。"""
    early = StallWatch(started_at=0.0)
    late = StallWatch(started_at=10_000.0)
    early.progress(at=100.0)
    late.progress(at=10_100.0)
    assert early.verdict(100.0 + 11 * MIN) == STALLED
    assert late.verdict(10_100.0 + 11 * MIN) == STALLED


def test_snapshot_reports_idle():
    watch = StallWatch(started_at=0.0)
    watch.progress(at=2 * MIN)
    snap = watch.snapshot(now=7 * MIN)
    assert snap.state == OK
    assert snap.idle_seconds == 5 * MIN
    assert snap.to_dict()["idle_seconds"] == 300.0

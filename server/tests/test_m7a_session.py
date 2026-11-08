"""星铁会话的判定测试。

核心断言：**运行记录一出现就判终态**，不等任何进程、不等任何管道。
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from app.core.stall import StallWatch
from app.engine.m7a_session import (
    STATE_FAILED,
    STATE_STOPPED,
    STATE_SUCCESS,
    STATE_STUCK,
    M7aSession,
    run_and_capture,
)

RUN_ID = "20261108-020836-928f"


def _setup(tmp_path: Path) -> tuple[M7aSession, Path]:
    """造一个假的 m7a 安装目录。"""
    exe = tmp_path / "m7a.exe"
    exe.write_bytes(b"")                       # 只要存在即可
    runs = tmp_path / "logs" / "runs"
    runs.mkdir(parents=True)
    session = M7aSession(exe, "divergent")
    session.attach(RUN_ID)
    return session, runs


def _write_record(runs: Path, **fields) -> None:
    data = {
        "schema": 1,
        "run_id": RUN_ID,
        "task": "divergent",
        "status": "running",
        "exit_code": None,
        "started_at": "2026-11-08T02:08:36+08:00",
        "ended_at": None,
        "error": None,
    }
    data.update(fields)
    (runs / f"{RUN_ID}.json").write_text(json.dumps(data), encoding="utf-8")


def test_success_record_is_decisive(tmp_path: Path):
    """真实场景：记录 success，而游戏进程还开着、日志还在写。"""
    session, runs = _setup(tmp_path)
    (runs / f"{RUN_ID}.log").write_text("开始「差分宇宙」\n", encoding="utf-8")

    poll = session.poll()
    assert poll.state is None, "还没写记录时不能提前下结论"

    _write_record(runs, status="success", exit_code=0, ended_at="2026-11-08T02:31:02+08:00")
    poll = session.poll()
    assert poll.state == STATE_SUCCESS
    assert poll.finished


def test_stopped_record(tmp_path: Path):
    session, runs = _setup(tmp_path)
    _write_record(runs, status="stopped", exit_code=6)
    assert session.poll().state == STATE_STOPPED


def test_failed_record(tmp_path: Path):
    session, runs = _setup(tmp_path)
    _write_record(runs, status="failed", exit_code=1, error="OCR 初始化失败")
    poll = session.poll()
    assert poll.state == STATE_FAILED
    assert "OCR" in poll.note


def test_stuck_only_when_no_progress(tmp_path: Path):
    """没有终态记录时，只有「长时间没进展」才判卡死。"""
    exe = tmp_path / "m7a.exe"
    exe.write_bytes(b"")
    runs = tmp_path / "logs" / "runs"
    runs.mkdir(parents=True)

    now = time.monotonic()
    stall = StallWatch(started_at=now - 3600, idle=600)
    stall.progress(at=now - 700)          # 11 分多钟没有新进展

    session = M7aSession(exe, "divergent", stall=stall)
    session.attach(RUN_ID)
    stall.progress(at=now - 700)          # attach 会记一次进展，这里覆盖成「11 分钟前」

    poll = session.poll()
    assert poll.state == STATE_STUCK
    assert "没有新的进展" in poll.note


def test_still_running_when_progressing(tmp_path: Path):
    """一直在写日志的任务，绝不能因为「跑了很久」被判卡死。"""
    exe = tmp_path / "m7a.exe"
    exe.write_bytes(b"")
    runs = tmp_path / "logs" / "runs"
    runs.mkdir(parents=True)
    (runs / f"{RUN_ID}.log").write_text("", encoding="utf-8")

    now = time.monotonic()
    stall = StallWatch(started_at=now - 7200, idle=600)   # 已经跑了 2 小时
    stall.progress(at=now - 5)                            # 5 秒前还有进展

    session = M7aSession(exe, "divergent", stall=stall)
    session.attach(RUN_ID)

    assert session.poll().state is None


def test_run_and_capture_is_not_held_by_grandchild(tmp_path: Path):
    """新实现用临时文件接输出，孙进程持有句柄也不影响返回时间。"""
    outer = (
        "import subprocess, sys\n"
        "subprocess.Popen(\n"
        "    [sys.executable, '-c', 'import time; time.sleep(4)'],\n"
        "    stdout=sys.stdout, close_fds=False,\n"
        ")\n"
    )
    started = time.monotonic()
    code, text = run_and_capture(
        [sys.executable, "-c", outer], cwd=tmp_path, timeout=2.0
    )
    elapsed = time.monotonic() - started

    assert code == 0
    assert elapsed < 2.0, f"被孙进程拖住了：{elapsed:.2f}s"


def test_run_and_capture_raises_on_real_timeout(tmp_path: Path):
    started = time.monotonic()
    try:
        run_and_capture(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            cwd=tmp_path,
            timeout=1.0,
        )
    except TimeoutError:
        pass
    else:  # pragma: no cover
        raise AssertionError("应当抛 TimeoutError")
    assert time.monotonic() - started < 4.0


def test_start_succeeds_when_record_appears_but_process_keeps_running(tmp_path, monkeypatch):
    """回归：`--detach` 的启动器进程会一直守着任务，不能等它退出。

    2026-11-08 09:38 的故障：任务已经在跑（run 记录写出来了），
    我们却因为「进程没退出」判超时并 kill 掉，任务被腰斩。
    """
    import threading

    import app.engine.m7a_session as mod

    exe = tmp_path / "m7a.exe"
    exe.write_bytes(b"")
    runs = tmp_path / "logs" / "runs"
    runs.mkdir(parents=True)

    class FakeProc:
        def poll(self):
            return None          # 一直活着，模拟「启动器守着任务」

        def kill(self):
            raise AssertionError("不该 kill 正在跑任务的进程")

    monkeypatch.setattr(mod.subprocess, "Popen", lambda *a, **k: FakeProc())
    monkeypatch.setattr(mod, "LAUNCH_TIMEOUT", 10)

    record = runs / f"{RUN_ID}.json"

    def _write_later():
        record.write_text("{}", encoding="utf-8")

    threading.Timer(1.2, _write_later).start()

    session = M7aSession(exe, "routine")
    assert session.start() == RUN_ID
    assert session.run_id == RUN_ID


def test_running_record_is_not_success(tmp_path: Path):
    """回归：记录里 status=running 时必须继续等，绝不能算成功。

    2026-11-08 09:49 的故障：读到一条旧的 running 记录（任务其实早被杀了），
    兜底逻辑把它当成功，链 2 秒就结束，互斥也随之失效。
    """
    session, runs = _setup(tmp_path)
    _write_record(runs, status="running", exit_code=None)

    poll = session.poll()
    assert poll.state is None, "running 不能被判成功"
    assert not poll.finished


def test_aborted_record_is_failed(tmp_path: Path):
    """aborted = 运行被异常中止（比如进程被外力结束），不能算成功。"""
    session, runs = _setup(tmp_path)
    _write_record(runs, status="aborted", exit_code=None)
    poll = session.poll()
    assert poll.state == STATE_FAILED
    assert "中止" in poll.note

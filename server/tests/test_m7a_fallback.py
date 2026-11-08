"""星铁启动的三条回退路径。

顺序：`--detach` 的输出 → 新出现的运行记录 → `--status` 的 active_run。
三条路都只读文件或执行短命命令，任何一条都不会让线程被句柄拖住。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from app.engine.m7a_session import M7aSession

RUN_ID = "20261108-020836-928f"


def test_parse_run_id_from_json_line():
    text = '正在启动…\n{"run_id": "%s", "status": "running"}\n' % RUN_ID
    assert M7aSession._parse_run_id(text) == RUN_ID


def test_parse_run_id_from_bare_string():
    text = "已启动：%s\n" % RUN_ID
    assert M7aSession._parse_run_id(text) == RUN_ID


def test_parse_run_id_absent():
    assert M7aSession._parse_run_id("启动失败：already running") == ""


def test_parse_active_run():
    text = json.dumps(
        {
            "version": "v2026.11.6",
            "active_run": {"run_id": RUN_ID, "task": "divergent"},
            "recent_runs": [],
        }
    )
    assert M7aSession._parse_active_run(text) == RUN_ID


def test_parse_active_run_when_idle():
    assert M7aSession._parse_active_run(json.dumps({"active_run": None})) == ""


def test_wait_new_record_picks_new_file(tmp_path: Path):
    exe = tmp_path / "m7a.exe"
    exe.write_bytes(b"")
    runs = tmp_path / "logs" / "runs"
    runs.mkdir(parents=True)
    (runs / "20261107-000000-0000.json").write_text("{}", encoding="utf-8")

    session = M7aSession(exe, "daily")
    before = session._record_names()

    (runs / f"{RUN_ID}.json").write_text("{}", encoding="utf-8")
    assert session._wait_new_record(before) == RUN_ID


def test_wait_new_record_times_out(monkeypatch, tmp_path: Path):
    exe = tmp_path / "m7a.exe"
    exe.write_bytes(b"")
    runs = tmp_path / "logs" / "runs"
    runs.mkdir(parents=True)
    session = M7aSession(exe, "daily")

    monkeypatch.setattr("app.engine.m7a_session.RECORD_WAIT", 1)
    started = time.monotonic()
    assert session._wait_new_record(set()) == ""
    assert time.monotonic() - started < 4

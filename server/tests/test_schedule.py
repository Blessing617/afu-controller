"""定时配置的解析与判定。"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from app.core.schedule import Schedule, ScheduleError, load_schedule, save_schedule


def _dt(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M")


def test_parse_and_normalize_times():
    s = Schedule.from_dict({"enabled": True, "times": ["8:00", "20:05"], "weekdays": []})
    assert s.times == ["08:00", "20:05"]
    assert s.enabled is True


def test_reject_bad_time():
    with pytest.raises(ScheduleError):
        Schedule.from_dict({"times": ["25:00"]})
    with pytest.raises(ScheduleError):
        Schedule.from_dict({"times": ["8点"]})


def test_reject_too_many_times():
    with pytest.raises(ScheduleError):
        Schedule.from_dict({"times": [f"{h:02d}:00" for h in range(9)]})


def test_reject_bad_weekday():
    with pytest.raises(ScheduleError):
        Schedule.from_dict({"weekdays": [0]})
    with pytest.raises(ScheduleError):
        Schedule.from_dict({"weekdays": [8]})


def test_weekdays_empty_means_every_day():
    s = Schedule.from_dict({"enabled": True, "times": ["08:00"]})
    assert s.active_on(_dt("2026-11-08 09:00"))     # 任意一天


def test_due_only_on_matching_minute_and_day():
    s = Schedule.from_dict(
        {"enabled": True, "times": ["08:00"], "weekdays": [7]}   # 2026-11-08 是周日(isoweekday=7)
    )
    assert s.due_slots(_dt("2026-11-08 08:00")) == ["08:00"]
    assert s.due_slots(_dt("2026-11-08 08:01")) == []
    assert s.due_slots(_dt("2026-11-09 08:00")) == []           # 周一，不匹配


def test_fired_once_per_day():
    s = Schedule.from_dict({"enabled": True, "times": ["08:00"]})
    now = _dt("2026-11-08 08:00")
    assert s.due_slots(now) == ["08:00"]
    s.mark_fired(now, "08:00")
    assert s.due_slots(now) == []
    # 第二天同一时间点可以再触发
    assert s.due_slots(_dt("2026-11-09 08:00")) == ["08:00"]


def test_disabled_never_due():
    s = Schedule.from_dict({"enabled": False, "times": ["08:00"]})
    assert s.due_slots(_dt("2026-11-08 08:00")) == []


def test_next_run_text():
    s = Schedule.from_dict({"enabled": True, "times": ["08:00", "20:00"]})
    assert s.next_run(_dt("2026-11-08 07:00")) == "今天 08:00"
    assert s.next_run(_dt("2026-11-08 09:00")) == "今天 20:00"
    assert s.next_run(_dt("2026-11-08 21:00")) == "明天 08:00"
    assert s.next_run(_dt("2026-11-08 21:00")) is not None


def test_next_run_none_when_disabled():
    s = Schedule.from_dict({"enabled": False, "times": ["08:00"]})
    assert s.next_run(_dt("2026-11-08 07:00")) is None


def test_corrupt_file_falls_back(tmp_path, monkeypatch):
    import app.core.schedule as mod

    monkeypatch.setattr(mod, "SCHEDULE_FILE", tmp_path / "schedule.json")
    (tmp_path / "schedule.json").write_text("{坏掉的", encoding="utf-8")
    s = mod.load_schedule()
    assert s.enabled is False and s.times == []
    assert (tmp_path / "schedule.corrupt.json").is_file()


def test_save_and_reload_keeps_last_fired(tmp_path, monkeypatch):
    import app.core.schedule as mod

    monkeypatch.setattr(mod, "SCHEDULE_FILE", tmp_path / "schedule.json")
    s = Schedule.from_dict({"enabled": True, "times": ["08:00"]})
    s.mark_fired(_dt("2026-11-08 08:00"), "08:00")
    mod.save_schedule(s)

    again = mod.load_schedule()
    assert again.enabled is True
    assert again.times == ["08:00"]
    assert again.last_fired, "last_fired 要能持久化，否则服务重启会重复触发"
    assert again.due_slots(_dt("2026-11-08 08:00")) == []

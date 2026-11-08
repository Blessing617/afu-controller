"""定时配置：什么时候自动跑整条任务链。

和 `chain.json` 分开存（`schedule.json`）的理由：
- 生命周期不同——链是「跑什么」，定时是「什么时候跑」，用户可能只改其中一样
- 单独文件好做整份替换与备份，写坏了只影响定时，不影响链

时间点用 `HH:MM` 字符串存。校验放在这里，`api` 层只负责把错误翻译成 400。
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR

SCHEDULE_FILE: Path = DATA_DIR / "schedule.json"

# 最多几个时间点：再多也不实用，还会让「下次运行」的推演变得难解释
MAX_TIMES = 8
# 保留最近多少条触发记录
KEEP_FIRED = 16

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")

_lock = threading.Lock()


class ScheduleError(ValueError):
    """定时配置不合法。上层映射为 HTTP 400。"""


@dataclass
class Schedule:
    enabled: bool = False
    times: list[str] = field(default_factory=list)       # ["08:00", "20:00"]
    weekdays: list[int] = field(default_factory=list)    # 1=周一 … 7=周日；空=每天
    # 触发去重：{"2026-11-08T08:00": "2026-11-08T08:00:12"}
    last_fired: dict[str, str] = field(default_factory=dict)

    # ---------- 序列化 ----------
    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "times": list(self.times),
            "weekdays": list(self.weekdays),
        }

    @staticmethod
    def from_dict(data: dict) -> "Schedule":
        if not isinstance(data, dict):
            raise ScheduleError("定时配置必须是对象")

        raw_times = data.get("times") or []
        if not isinstance(raw_times, list):
            raise ScheduleError("times 必须是数组")
        times: list[str] = []
        for item in raw_times:
            text = str(item).strip()
            if not text:
                continue
            m = _TIME_RE.match(text)
            if not m:
                raise ScheduleError(f"时间格式不对：{text!r}（要 HH:MM，例如 08:00）")
            times.append(f"{int(m.group(1)):02d}:{m.group(2)}")
        if len(times) > MAX_TIMES:
            raise ScheduleError(f"最多 {MAX_TIMES} 个时间点，当前 {len(times)} 个")
        # 去重并保持顺序
        seen: set[str] = set()
        times = [t for t in times if not (t in seen or seen.add(t))]

        raw_days = data.get("weekdays") or []
        if not isinstance(raw_days, list):
            raise ScheduleError("weekdays 必须是数组")
        weekdays: list[int] = []
        for item in raw_days:
            try:
                day = int(item)
            except (TypeError, ValueError):
                raise ScheduleError(f"weekdays 里不是数字：{item!r}") from None
            if not 1 <= day <= 7:
                raise ScheduleError("weekdays 只能是 1~7（1=周一）")
            weekdays.append(day)
        weekdays = sorted(set(weekdays))

        return Schedule(
            enabled=bool(data.get("enabled")),
            times=times,
            weekdays=weekdays,
        )

    # ---------- 判断 ----------
    def active_on(self, day: datetime) -> bool:
        """这一天要不要生效（星期匹配）。"""
        return not self.weekdays or day.isoweekday() in self.weekdays

    def due_slots(self, now: datetime) -> list[str]:
        """当前这一分钟命中了哪些时间点（且今天还没触发过）。"""
        if not self.enabled or not self.times:
            return []
        if not self.active_on(now):
            return []
        current = f"{now:%H:%M}"
        return [
            slot
            for slot in self.times
            if slot == current and self._key(now, slot) not in self.last_fired
        ]

    @staticmethod
    def _key(now: datetime, slot: str) -> str:
        return f"{now:%Y-%m-%d}T{slot}"

    def mark_fired(self, now: datetime, slot: str) -> None:
        key = self._key(now, slot)
        self.last_fired[key] = now.isoformat(timespec="seconds")
        if len(self.last_fired) > KEEP_FIRED:
            for old in sorted(self.last_fired)[:-KEEP_FIRED]:
                self.last_fired.pop(old, None)

    def next_run(self, now: datetime) -> str | None:
        """下次运行时间（人话），没有可用时间点或没启用时返回 None。"""
        if not self.enabled or not self.times:
            return None
        for offset in range(0, 8):
            day = now.fromordinal(now.toordinal() + offset)
            if not self.active_on(day):
                continue
            for slot in sorted(self.times):
                candidate = day.replace(
                    hour=int(slot[:2]), minute=int(slot[3:]), second=0, microsecond=0
                )
                if candidate > now:
                    head = "今天" if offset == 0 else ("明天" if offset == 1 else f"{day:%m-%d}")
                    return f"{head} {slot}"
        return None


# ---------------------------------------------------------------- 持久化
def load_schedule() -> Schedule:
    """读配置。文件不存在或损坏时返回默认（关闭、无时间点），不抛异常。"""
    if not SCHEDULE_FILE.is_file():
        return Schedule()
    try:
        data = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
        schedule = Schedule.from_dict(data)
        # last_fired 存在文件里，但不对外暴露
        raw_fired = data.get("last_fired") or {}
        if isinstance(raw_fired, dict):
            schedule.last_fired = {str(k): str(v) for k, v in raw_fired.items()}
        return schedule
    except Exception:
        # 坏文件不该让服务起不来，也不该悄悄清空用户的定时：
        # 改名留档，再按默认（关闭）继续
        try:
            SCHEDULE_FILE.replace(SCHEDULE_FILE.with_suffix(".corrupt.json"))
        except Exception:  # noqa: BLE001
            pass
        return Schedule()


def save_schedule(schedule: Schedule) -> dict:
    """整份替换并备份旧文件。"""
    with _lock:
        SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)
        backup = None
        if SCHEDULE_FILE.is_file():
            backup = SCHEDULE_FILE.with_suffix(".json.bak")
            try:
                backup.write_text(
                    SCHEDULE_FILE.read_text(encoding="utf-8"), encoding="utf-8"
                )
            except Exception:  # noqa: BLE001
                backup = None
        payload = schedule.to_dict()
        payload["last_fired"] = dict(schedule.last_fired)
        SCHEDULE_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return {
        "saved": True,
        # 注意别用 "times" 这个名字：接口返回的配置里也有 times（时间点列表），
        # 合并时会把它覆盖成数字（2026-11-08 踩过）
        "time_count": len(schedule.times),
        "backup": str(backup) if backup else "",
    }

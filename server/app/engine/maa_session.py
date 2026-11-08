"""方舟（MAA）的任务会话。

MAA 是事件驱动的：我们下发任务，它执行完再 `reportStatus` 回来。
所以这里的 `poll` 大部分时间只是「看有没有结果进来」，顺带用官方的
`HeartBeat` 确认它还在跑。

进展判定：远程控制协议没有中间进度，只能看 MAA 自己的 `debug/asst.log`
是否还在增长（实测空闲时该文件不写）。读不到日志时退化为「心跳 + 兜底上限」，
并在日志里注明降级，不编一个假判据。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Protocol

from ..core.progress import maa_heartbeat
from ..core.stall import OK, StallWatch
from ..core.supervisor import PollResult

# 心跳间隔
HEARTBEAT_SECONDS = 15
# 兜底上限
HARD_CAP_SECONDS = 6 * 3600


class MaaLike(Protocol):
    def online(self) -> bool: ...
    def submit_heartbeat(self) -> str: ...
    def take_result(self, task_id: str) -> dict | None: ...
    def submit(self, task_type: str, run=None) -> str: ...
    def current_task(self) -> str: ...


def asst_log_path(maa_exe: str | Path) -> Path:
    """MAA 的核心日志：`<安装目录>/debug/asst.log`。"""
    return Path(maa_exe).parent / "debug" / "asst.log"


class MaaSession:
    """一次方舟任务的会话。"""

    def __init__(
        self,
        adapter: MaaLike,
        task_id: str,
        *,
        asst_log: Path | None = None,
        started_at: float | None = None,
    ) -> None:
        self.adapter = adapter
        self.task_id = task_id
        self.asst_log = Path(asst_log) if asst_log else None
        self._stall = StallWatch(started_at=started_at)
        self._started = time.monotonic() if started_at is None else started_at
        self._next_beat = time.monotonic()
        self._last_size = self._size()
        self._downgraded = self._last_size is None
        self._stall.progress()

    def _size(self) -> int | None:
        if self.asst_log is None:
            return None
        try:
            return self.asst_log.stat().st_size
        except OSError:
            return None

    @property
    def downgraded(self) -> bool:
        return self._downgraded

    def poll(self) -> PollResult:
        result = PollResult()
        now = time.monotonic()

        stored = self.adapter.take_result(self.task_id)
        if stored is not None:
            if stored.get("status") == "SUCCESS":
                result.state = "success"
            else:
                result.state = "failed"
                result.note = f"MAA 回报 {stored.get('status')}"
            return result

        if now >= self._next_beat:
            self.adapter.submit_heartbeat()
            self._next_beat = now + HEARTBEAT_SECONDS

        current = maa_heartbeat(self.adapter.current_task())
        if current["running"]:
            result.markers["phase"] = "执行中"

        if not self.adapter.online():
            result.state = "failed"
            result.note = "MAA 已离线（未再轮询）"
            return result

        size = self._size()
        if size is None:
            self._downgraded = True
        elif self._last_size is None:
            # 日志文件晚于任务出现（MAA 刚启动），从当前长度开始跟
            self._last_size = size
            self._downgraded = False
        elif size != self._last_size:
            self._last_size = size
            self._downgraded = False
            self._stall.progress()

        if now - self._started >= HARD_CAP_SECONDS:
            result.state = "timeout"
            result.note = f"运行超过 {HARD_CAP_SECONDS // 3600} 小时仍未回报"
            return result

        if not self._downgraded and self._stall.verdict() != OK:
            result.state = "stuck"
            result.note = self._stall.reason()
            return result

        return result

    def stop(self, reason: str = "") -> None:
        self.adapter.submit("StopTask")

    def stall_snapshot(self) -> dict:
        return self._stall.snapshot().to_dict()

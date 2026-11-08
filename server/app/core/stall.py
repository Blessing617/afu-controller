"""卡死判定：看「距最后一次进展」多久，而不是「跑了多久」。

为什么不能用总时长
------------------
同一台机器今天快明天慢，同一个任务可能因为游戏内多刷了一波怪而多跑十分钟。
用总时长当上限，必然出现「慢机器被误杀」和「卡死要等一小时」两头不讨好。

实测依据（2026-10-23～11-08 日志统计）：
- 星铁单次运行内最长静默 3.4 分钟（战斗中），常在 2.5～3.1 分钟
- 原神一条龙跑满 40 分钟时，最长静默只有 31 秒

所以「10 分钟没有任何有效进展」在两边都只是 3～19 倍余量的安全线，
而「跑了多少分钟」完全不该参与判断。
"""

from __future__ import annotations

import time
from dataclasses import dataclass

# 启动后允许完全没有日志的时间：要覆盖 UAC 等待、游戏启动、引擎加载资源
FIRST_PROGRESS_SECONDS = 15 * 60
# 有进展之后，多久没有新的有效进展就认为卡死
IDLE_SECONDS = 10 * 60
# 兜底：一直有进展却永不结束（防挂一整夜）
HARD_CAP_SECONDS = 6 * 3600

OK = "ok"
NO_START = "no_start"
STALLED = "stalled"
TOO_LONG = "too_long"


@dataclass
class StallSnapshot:
    """给手机端看的进展情况。"""

    state: str
    elapsed_seconds: float
    idle_seconds: float | None
    last_progress_at: float | None

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "idle_seconds": (
                round(self.idle_seconds, 1) if self.idle_seconds is not None else None
            ),
            "last_progress_at": self.last_progress_at,
        }


class StallWatch:
    """判断一个正在跑的任务是「还在推进」还是「已经卡住」。"""

    def __init__(
        self,
        *,
        first_progress: float = FIRST_PROGRESS_SECONDS,
        idle: float = IDLE_SECONDS,
        hard_cap: float = HARD_CAP_SECONDS,
        started_at: float | None = None,
    ) -> None:
        self.first_progress = first_progress
        self.idle_limit = idle
        self.hard_cap = hard_cap
        self._started_at = time.monotonic() if started_at is None else started_at
        self._last_progress_at: float | None = None

    # ---------------- 记录进展 ----------------
    def progress(self, at: float | None = None) -> None:
        self._last_progress_at = time.monotonic() if at is None else at

    @property
    def has_progressed(self) -> bool:
        return self._last_progress_at is not None

    # ---------------- 判定 ----------------
    def verdict(self, now: float | None = None) -> str:
        now = time.monotonic() if now is None else now
        elapsed = now - self._started_at

        if elapsed >= self.hard_cap:
            return TOO_LONG

        if self._last_progress_at is None:
            return NO_START if elapsed >= self.first_progress else OK

        if now - self._last_progress_at >= self.idle_limit:
            return STALLED
        return OK

    def snapshot(self, now: float | None = None) -> StallSnapshot:
        now = time.monotonic() if now is None else now
        idle = None if self._last_progress_at is None else now - self._last_progress_at
        return StallSnapshot(
            state=self.verdict(now),
            elapsed_seconds=now - self._started_at,
            idle_seconds=idle,
            last_progress_at=self._last_progress_at,
        )

    def reason(self) -> str:
        """把判定翻译成人话，写进任务错误信息。"""
        state = self.verdict()
        if state == TOO_LONG:
            return f"运行时长异常（{self.hard_cap / 3600:g} 小时），已终止"
        if state == NO_START:
            return f"启动后 {self.first_progress / 60:g} 分钟没有任何输出"
        if state == STALLED:
            return f"超过 {self.idle_limit / 60:g} 分钟没有新的进展"
        return ""

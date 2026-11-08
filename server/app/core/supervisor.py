"""任务监督循环：三个引擎共用同一套「轮询 → 收敛终态 → 广播一次」的逻辑。

为什么要抽这一层
----------------
改造前三个引擎各写一套等待循环（m7a 阻塞等进程、BGI 自己轮询日志、MAA 自己
`sleep` 等回报），于是「什么时候算结束」有三份实现、三套 bug。这里只保留一份：

    while 任务没结束:
        result = job.poll()          # 引擎自己提供证据
        追加日志 / 更新进度
        result.state 非空 → 收敛终态并 finish（只广播一次）

适配器实现 `Job` 协议即可，不许自己改任务状态（见 `.spec/code-structure`）。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol

from .state import TaskRun, TaskRunner, TaskState

# 轮询节拍。1 秒足够让手机端看到「进度在动」，也不会把子进程调用打满。
TICK_SECONDS = 1.0


@dataclass
class PollResult:
    """一次轮询的结论。`state` 为 None 表示还在跑。"""

    state: str | None = None
    markers: dict[str, str] = field(default_factory=dict)
    lines: list[str] = field(default_factory=list)
    note: str = ""

    @property
    def finished(self) -> bool:
        return self.state is not None


class Job(Protocol):
    """引擎会话要满足的最小接口。"""

    def poll(self) -> PollResult: ...

    def stop(self, reason: str = "") -> None: ...


# PollResult.state → TaskState
_STATE_MAP = {
    "success": TaskState.SUCCESS,
    "failed": TaskState.FAILED,
    "stopped": TaskState.STOPPED,
    "stuck": TaskState.FAILED,
    "timeout": TaskState.TIMEOUT,
}


def _to_task_state(state: str) -> TaskState:
    return _STATE_MAP.get(state, TaskState.FAILED)


def supervise(
    runner: TaskRunner,
    run: TaskRun,
    job: Job,
    *,
    tick: float = TICK_SECONDS,
    finish: bool = True,
) -> TaskState:
    """盯住一个任务直到结束。

    `finish=False` 时只返回结论、不改任务终态——多任务串行时用，
    免得第一个子任务成功就把整个任务标记成结束。
    """
    while True:
        if run.ended_at is not None:
            # 用户点了停止；这里只负责让引擎也停下来，终态已由停止流程写好
            _safe_stop(job, "用户停止")
            return run.state

        try:
            result = job.poll()
        except Exception as exc:  # noqa: BLE001 —— 轮询本身出错也要收尾
            if finish:
                runner.finish(run, TaskState.FAILED, error=f"轮询异常：{exc}")
            return TaskState.FAILED

        for line in result.lines:
            runner.append_log(run, line)
        if result.markers:
            run.progress = dict(result.markers)

        # 让手机端能显示「距上次进展 N 分钟」，而不是只有一个已经跑了多久
        snapshot = getattr(job, "stall_snapshot", None)
        if callable(snapshot):
            try:
                run.stall = snapshot()
            except Exception:  # noqa: BLE001
                pass

        if result.finished:
            state = _to_task_state(result.state or "failed")
            if result.state == "stuck":
                _safe_stop(job, result.note)
            if finish:
                # 成功时不要把「完成标志」之类的 note 当错误写进去，
                # 否则手机上「成功」旁边会多一句让人困惑的话
                runner.finish(
                    run, state, error="" if state == TaskState.SUCCESS else result.note
                )
            elif result.note:
                # 多任务串行时由调用方决定终态，但原因要留住
                run.error = result.note
            return state

        time.sleep(tick)


def _safe_stop(job: Job, reason: str) -> None:
    try:
        job.stop(reason)
    except Exception:  # noqa: BLE001
        pass

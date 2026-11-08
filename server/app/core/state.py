"""任务状态与前台互斥队列（core 层，唯一状态持有者）。

原在 engine/base.py，移到 core 是为了让依赖方向正确：
core 不该反向依赖 engine，而「任务是什么状态」本来就不是引擎的事。

规则：
- 同一时刻最多一个「占用前台键鼠」的任务在运行
- 重复启动返回冲突（上层映射为 HTTP 409）
- 「用户停止」是独立状态，不算失败
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class TaskState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    STOPPED = "stopped"
    TIMEOUT = "timeout"


@dataclass
class TaskRun:
    run_id: str
    game: str            # genshin / starrail / arknights
    title: str
    state: TaskState
    started_at: float
    ended_at: float | None = None
    exit_code: int | None = None
    error: str = ""
    log_tail: list[str] = field(default_factory=list)
    # 所属任务链（单步启动时为空）。用来把同一次编排的多个 run 串起来。
    chain_id: str = ""
    # 这一步选了哪些子任务（空 = 按引擎当前配置全跑）
    tasks: list[str] = field(default_factory=list)
    # 引擎给出的进度标记（阶段 x/y、任务 i/n、战斗中…），给手机端展示
    progress: dict[str, str] = field(default_factory=dict)
    # 引擎自己的运行编号（星铁的 run_id），停止时用它精确下发指令
    engine_run_id: str = ""
    # 进展快照：距上次进展多久、是否已判卡死（给手机端显示「卡了多久」）
    stall: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "game": self.game,
            "title": self.title,
            "state": self.state.value,
            "chain_id": self.chain_id,
            "tasks": list(self.tasks),
            "progress": dict(self.progress),
            "engine_run_id": self.engine_run_id,
            "stall": dict(self.stall),
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": (
                round((self.ended_at or time.time()) - self.started_at, 1)
            ),
            "exit_code": self.exit_code,
            "error": self.error,
            "log_tail": self.log_tail[-50:],
        }


class TaskConflict(Exception):
    """已有任务在运行。"""

    def __init__(self, current: TaskRun | None) -> None:
        self.current = current
        super().__init__("已有任务正在运行")


class TaskRunner:
    """前台任务互斥队列（内存态，单机足够）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current: TaskRun | None = None
        self._history: list[TaskRun] = []

    # ---- 查询 ----
    def current(self) -> TaskRun | None:
        with self._lock:
            return self._current

    def history(self, limit: int = 20) -> list[TaskRun]:
        with self._lock:
            return list(self._history[-limit:])

    # ---- 启动 ----
    def try_start(self, game: str, title: str) -> TaskRun:
        """尝试开始一个新任务；已有任务在跑时抛 TaskConflict。"""
        with self._lock:
            if self._current is not None:
                raise TaskConflict(self._current)
            run = TaskRun(
                run_id=uuid.uuid4().hex[:12],
                game=game,
                title=title,
                state=TaskState.RUNNING,
                started_at=time.time(),
            )
            self._current = run
        _emit("started", run)
        return run

    # ---- 结束 ----
    def finish(
        self,
        run: TaskRun,
        state: TaskState,
        *,
        exit_code: int | None = None,
        error: str = "",
    ) -> TaskRun:
        with self._lock:
            # 已经结束的任务不再覆盖：用户点「停止」会先把状态置为 stopped，
            # 而适配器线程在引擎进程退出后还会尝试 finish 一次，
            # 如果不拦，就会把 stopped 覆盖成 failed。
            if run.ended_at is not None:
                return run
            run.state = state
            run.ended_at = time.time()
            if exit_code is not None:
                run.exit_code = exit_code
            if error:
                run.error = error
            self._history.append(run)
            if self._current is run:
                self._current = None
        _emit("finished", run)
        return run

    def append_log(self, run: TaskRun, line: str, keep: int = 200) -> None:
        line = line.rstrip()
        if not line:
            return
        run.log_tail.append(line)
        if len(run.log_tail) > keep:
            del run.log_tail[: len(run.log_tail) - keep]


# ---- 事件监听（WebSocket 广播用；回调由 main 注册，避免循环导入）----
_listeners: list = []


def add_listener(fn) -> None:
    if fn not in _listeners:
        _listeners.append(fn)


def _emit(kind: str, run: "TaskRun") -> None:
    for fn in list(_listeners):
        try:
            fn(kind, run)
        except Exception:
            pass


RUNNER = TaskRunner()

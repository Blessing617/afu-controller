"""任务链调度器：按顺序把多个游戏的步骤串起来跑。

设计要点
--------
1. **复用现有 RUNNER**，不新建任务运行器。每一步仍然是一个 `TaskRun`，
   只是带上 `chain_id` 把同一次编排的多个 run 串起来。这样单步启动 / 停止 /
   日志 / WebSocket 广播全都不用改。

2. **串行**。三个引擎都要抢前台键鼠，并行会互相打架（现有 `TaskRunner`
   本身就是互斥的），所以链内也严格一步一停。

3. **写配置必须在启动引擎之前**。MAA 启动后会把自己内存里的配置整份写回
   文件，晚改会被覆盖（详见 engine/apply.py 的说明）。

4. 链状态只存内存。服务重启后链视为未运行，**不会自动续跑**——
   半夜续跑一个半截的链比直接停掉更危险。
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

from . import tasks as task_api
from .chain import Chain, ChainStep, GAME_LABELS, POLICY_STOP
from .state import RUNNER, TaskRun, TaskState


class StepState(str, Enum):
    PENDING = "pending"       # 还没轮到
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"       # 用户关掉了这一步
    NOT_RUN = "not_run"       # 因为前面的失败/停止没跑到
    STOPPED = "stopped"       # 用户在这步中途点了停止


@dataclass
class StepResult:
    index: int
    game: str
    name: str
    state: StepState = StepState.PENDING
    started_at: float = 0.0
    ended_at: float | None = 0.0
    error: str = ""
    run_id: str = ""
    tasks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "game": self.game,
            "name": self.name,
            "state": self.state.value,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": (
                round((self.ended_at or time.time()) - self.started_at, 1)
                if self.started_at
                else 0.0
            ),
            "error": self.error,
            "run_id": self.run_id,
            "tasks": list(self.tasks),
        }


@dataclass
class ChainRun:
    chain_id: str
    steps: list[StepResult]
    policy: str
    state: str = "running"      # running / finished
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None
    error: str = ""

    @property
    def total(self) -> int:
        return len([s for s in self.steps if s.state is not StepState.SKIPPED])

    def current_index(self) -> int:
        for i, s in enumerate(self.steps):
            if s.state is StepState.RUNNING:
                return i
        return -1

    def summary(self) -> dict:
        count = {k.value: 0 for k in StepState}
        for s in self.steps:
            count[s.state.value] = count.get(s.state.value, 0) + 1
        return count

    def to_dict(self) -> dict:
        current = self.current_index()
        return {
            "chain_id": self.chain_id,
            "state": self.state,
            "policy": self.policy,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "error": self.error,
            "current_index": current,
            "total": self.total,
            "steps": [s.to_dict() for s in self.steps],
            "summary": self.summary(),
        }


# 链事件广播（由 main 注册，避免循环导入）
_listeners: list = []


def add_listener(fn) -> None:
    if fn not in _listeners:
        _listeners.append(fn)


def _emit(kind: str, chain_run: ChainRun) -> None:
    for fn in list(_listeners):
        try:
            fn(kind, chain_run)
        except Exception:
            pass


class Orchestrator:
    """同一时刻最多跑一条链。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current: ChainRun | None = None
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()

    # ---- 查询 ----
    def current(self) -> ChainRun | None:
        with self._lock:
            return self._current

    def is_running(self) -> bool:
        run = self.current()
        return run is not None and run.state == "running"

    def request_stop(self) -> bool:
        """请求停止整条链。返回 True 表示确实有链在跑。"""
        if not self.is_running():
            return False
        self._stop_flag.set()
        return True

    # ---- 启动 ----
    def start(self, chain: Chain) -> ChainRun:
        """开始执行一条链。已有链在跑时抛 RuntimeError。"""
        with self._lock:
            if self._current is not None and self._current.state == "running":
                raise RuntimeError("已有任务链在运行")

            steps = [
                StepResult(
                    index=i,
                    game=s.game,
                    name=s.display_name,
                    state=StepState.PENDING if s.enabled else StepState.SKIPPED,
                    ended_at=0.0 if s.enabled else time.time(),
                    tasks=list(s.tasks),
                )
                for i, s in enumerate(chain.steps)
            ]
            run = ChainRun(
                chain_id=uuid.uuid4().hex[:12],
                steps=steps,
                policy=chain.policy,
            )
            self._current = run
            self._stop_flag.clear()

        _emit("started", run)
        self._thread = threading.Thread(
            target=self._worker, args=(chain, run), daemon=True, name="orchestrator"
        )
        self._thread.start()
        return run

    # ---- 主循环 ----
    def _worker(self, chain: Chain, run: ChainRun) -> None:
        aborted = False
        try:
            for step_def, result in zip(chain.steps, run.steps):
                # 用户关掉的步骤：直接标记跳过
                if not step_def.enabled:
                    result.state = StepState.SKIPPED
                    result.ended_at = result.ended_at or time.time()
                    _emit("step", run)
                    continue

                # 前面失败（stop 策略）或用户停止：后面的都不跑
                if aborted or self._stop_flag.is_set():
                    result.state = StepState.NOT_RUN
                    result.ended_at = time.time()
                    _emit("step", run)
                    continue

                self._run_step(step_def, result, run)
                _emit("step", run)

                if result.state in (StepState.FAILED,) and run.policy == POLICY_STOP:
                    aborted = True
                if self._stop_flag.is_set():
                    aborted = True

            run.state = "finished"
        except Exception as exc:  # noqa: BLE001 —— 调度器本身出错也要收尾
            run.error = f"编排异常：{exc}"
            run.state = "finished"
        finally:
            run.ended_at = time.time()
            # 收尾：还没定状态的步骤一律记「未执行」
            for result in run.steps:
                if result.state is StepState.PENDING:
                    result.state = StepState.NOT_RUN
                    result.ended_at = time.time()
            self._stop_flag.clear()
            _emit("finished", run)

    def _run_step(self, step: ChainStep, result: StepResult, chain_run: ChainRun) -> None:
        """执行一步。所有异常都收敛成「这一步失败」，绝不打断整条链。"""

        result.state = StepState.RUNNING
        result.started_at = time.time()
        _emit("step", chain_run)

        try:
            task_run = task_api.start_single(
                step.game,
                chain_id=chain_run.chain_id,
                tasks=list(step.tasks),
            )
        except Exception as exc:  # noqa: BLE001
            result.state = StepState.FAILED
            result.error = str(exc)
            result.ended_at = time.time()
            return

        result.run_id = task_run.run_id

        # 等这一步结束。同时盯着停止标志：用户喊停要能立刻打断。
        while task_run.ended_at is None:
            if self._stop_flag.is_set():
                try:
                    task_api.stop_current()
                except Exception:
                    pass
            time.sleep(0.5)
            current = RUNNER.current()
            if current is not None and current.run_id == task_run.run_id:
                task_run = current
                continue
            # 引擎已经把自己 finish 掉了
            break

        final = self._final_state(task_run)
        result.state = final
        result.error = task_run.error or ""
        result.ended_at = time.time()

    @staticmethod
    def _final_state(task_run: TaskRun) -> StepState:
        if task_run.ended_at is None:
            return StepState.FAILED
        return {
            TaskState.SUCCESS: StepState.SUCCESS,
            TaskState.STOPPED: StepState.STOPPED,
            TaskState.FAILED: StepState.FAILED,
            TaskState.TIMEOUT: StepState.FAILED,
        }.get(task_run.state, StepState.FAILED)


ORCH = Orchestrator()

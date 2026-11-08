"""MAA（明日方舟）适配器 —— 基于官方「远程控制协议」。

MAA 主动轮询我们的端点取任务、执行完再回报结果。所以这一侧不需要启动任何进程。

协议要点（实测 + 源码 `src/MaaWpfGui/Services/RemoteControl/RemoteControlService.cs`）：
- `getTask` 的 POST 可能没有 body；不能用缺字段来拒绝
- `device` 可能是空字符串，不能当唯一键
- 同一 task id 不会重复执行，用完即弃（所以每次心跳都要新 id）
- **`HeartBeat`** 任务走“立即执行”队列，回报的 `payload` 是 MAA 当前正在执行的
  顺序任务 id，空闲时为空字符串 —— 这是官方给的状态查询
- 一次 `LinkStart` 从头到尾都是**同一个** `_currentSequentialTaskId`，
  所以心跳只能回答「在不在跑」，**不能当进展用**

判定分工：
- 判活 / 离线：心跳 + `getTask` 轮询
- 终态：`reportStatus` 的 SUCCESS / FAILED
- 进展：MAA 自己的 `debug/asst.log` 字节增长（远程控制协议没有中间进度）
"""

from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path

from ..platform import proc
from ..core.state import TaskRunner, TaskRun, TaskState
from ..platform.window import minimize

TASK_TITLE = "明日方舟·一键长草"
ONLINE_WINDOW_SECONDS = 15   # 15 秒内来轮询过就算在线
HEARTBEAT_SECONDS = 15       # 心跳间隔
WATCH_TICK = 2               # 会话检查间隔
HARD_CAP_SECONDS = 6 * 3600


class MaaAdapter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queue: list[dict] = []
        self._pending: dict[str, TaskRun] = {}
        self._results: dict[str, dict] = {}
        self._heartbeats: dict[str, float] = {}
        self._maa_task = ""
        self._last_poll = 0.0
        self._polls = 0

    # ---- 状态 ----
    def online(self) -> bool:
        with self._lock:
            return (time.monotonic() - self._last_poll) < ONLINE_WINDOW_SECONDS

    def stats(self) -> dict:
        with self._lock:
            return {
                "online": (time.monotonic() - self._last_poll) < ONLINE_WINDOW_SECONDS,
                "polls": self._polls,
                "queued": len(self._queue),
                "pending": len(self._pending),
                "current_task": self._maa_task,
                "last_poll_seconds_ago": (
                    round(time.monotonic() - self._last_poll, 1) if self._polls else None
                ),
            }

    # ---- MAA 侧调用 ----
    def take_tasks(self) -> list[dict]:
        with self._lock:
            self._last_poll = time.monotonic()
            self._polls += 1
            items = self._queue
            self._queue = []
            return items

    def on_report(self, task_id: str, status: str, payload: str) -> dict:
        with self._lock:
            # 心跳回报：只更新「当前在跑哪个任务」，不改变任务状态
            if task_id in self._heartbeats:
                self._heartbeats.pop(task_id, None)
                self._maa_task = str(payload or "")
                return {"matched": False, "kind": "heartbeat", "current": self._maa_task}

            run = self._pending.pop(task_id, None)
            self._results[task_id] = {
                "status": status.upper(),
                "payload": payload,
                "at": time.monotonic(),
            }
        # 终态不在这里写，由会话层统一收敛（适配器不许直接改任务状态）
        return {"matched": run is not None, "kind": "task"}

    # ---- 编排侧调用 ----
    def submit(self, task_type: str, run: TaskRun | None = None) -> str:
        task_id = uuid.uuid4().hex
        with self._lock:
            self._queue.append({"id": task_id, "type": task_type})
            if run is not None:
                self._pending[task_id] = run
        return task_id

    def submit_heartbeat(self) -> str:
        beat_id = uuid.uuid4().hex
        with self._lock:
            self._queue.append({"id": beat_id, "type": "HeartBeat"})
            self._heartbeats[beat_id] = time.monotonic()
            # 只保留最近 20 个未回报的心跳，避免 MAA 不回时无限堆积
            if len(self._heartbeats) > 20:
                for old in sorted(self._heartbeats, key=self._heartbeats.get)[:10]:
                    self._heartbeats.pop(old, None)
        return beat_id

    def take_result(self, task_id: str) -> dict | None:
        with self._lock:
            return self._results.pop(task_id, None)

    def current_task(self) -> str:
        with self._lock:
            return self._maa_task

    # ---- 会话 ----
    def watch(
        self,
        runner: TaskRunner,
        run: TaskRun,
        task_id: str,
        *,
        asst_log: Path | None = None,
    ) -> TaskState:
        """等待任务结束（兼容入口）。判定逻辑在 `maa_session.MaaSession`。"""
        from ..core.supervisor import supervise
        from .maa_session import MaaSession

        session = MaaSession(self, task_id, asst_log=asst_log)
        if session.downgraded:
            runner.append_log(run, "⚠ 读不到 MAA 日志，进展判定降级为心跳 + 兜底上限")
        return supervise(runner, run, session)


MAA = MaaAdapter()

# 兼容旧导入路径
from .maa_session import asst_log_path  # noqa: E402,F401


# ---------- 自动启动（免去手动开 MAA / MuMu）----------
def _spawn(path: str, args: list[str] | None = None) -> bool:
    """后台启动一个程序，父进程退出也不影响它。"""
    exe = Path(path)
    if not exe.is_file():
        return False
    try:
        proc.spawn([str(exe)] + (args or []), cwd=str(exe.parent))
        return True
    except Exception:
        return False


def ensure_online(paths: dict, runner: TaskRunner, run: TaskRun) -> bool:
    """确保 MAA 在线：不在线就依次拉起 MuMu 与 MAA，并等它来轮询。"""
    if MAA.online():
        runner.append_log(run, "MAA 已在线")
        return True

    mumu = (paths.get("mumu") or {}).get("path", "")
    if mumu:
        runner.append_log(run, "启动 MuMu 模拟器…")
        _spawn(mumu, ["control", "-v", "0", "launch"])
        _wait(runner, run, 20, "等待模拟器启动")

    maa_exe = (paths.get("maa") or {}).get("path", "")
    if not maa_exe:
        runner.append_log(run, "未找到 MAA 路径")
        return False

    runner.append_log(run, f"启动 MAA：{maa_exe}")
    if not _spawn(maa_exe):
        runner.append_log(run, "MAA 启动失败")
        return False

    # MAA 启动后会自动读取远程控制端点并轮询；这里把它的窗口收起来，
    # 否则它会和游戏窗口抢焦点，导致 M7A / BGI 点击无效。
    _wait(runner, run, 4, "等待 MAA 窗口出现")
    if minimize("MAA.exe"):
        runner.append_log(run, "已最小化 MAA 窗口")
    if minimize("MuMuNxMain.exe"):
        runner.append_log(run, "已最小化 MuMu 窗口")

    for _ in range(90):
        if _wait(runner, run, 1, ""):
            return False
        if MAA.online():
            runner.append_log(run, "MAA 已上线")
            return True
    runner.append_log(run, "等待 MAA 上线超时（90 秒）")
    return False


def _wait(runner: TaskRunner, run: TaskRun, seconds: float, note: str) -> bool:
    """可被打断的等待。返回 True 表示等待期间任务已被停止。"""
    if note:
        runner.append_log(run, note)
    deadline = time.monotonic() + seconds
    while True:
        if run.ended_at is not None:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(0.2, remaining))


def RUNNER_FINISH(run: TaskRun, state: TaskState, *, error: str = "") -> None:
    """延迟导入 RUNNER，避免循环依赖。"""
    from ..core.state import RUNNER

    RUNNER.finish(run, state, error=error)

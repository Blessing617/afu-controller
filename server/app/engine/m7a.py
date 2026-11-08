"""三月七小助手（M7A）适配器入口。

真正的会话逻辑在 `m7a_session.py`：启动/轮询/停止。
这里只保留「多任务串行」这一层编排，以及一个读最近运行记录的兼容函数。

多任务为什么要串行：m7a 一次只接受一个 task id，而且两个自动化进程同时操作
同一款游戏本来就会互相打架（抢前台键鼠）。
"""

from __future__ import annotations

import json
from pathlib import Path

from ..core.supervisor import supervise
from ..core.state import TaskRun, TaskRunner, TaskState
from .m7a_session import M7aSession, _decode  # noqa: F401 — _decode 供测试/排查复用
from ..platform.window import activate

TASK_ID = "daily"
TASK_TITLE = "星铁·日常"


def _runs_dir(exe: Path) -> Path:
    return exe.parent / "logs" / "runs"


def latest_run_record(exe: Path) -> dict:
    """读最近一次运行记录（兼容旧调用；新流程用 `M7aSession.read_record`）。"""
    runs = _runs_dir(exe)
    if not runs.is_dir():
        return {}
    files = sorted(runs.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return {}
    try:
        return json.loads(files[0].read_text(encoding="utf-8"))
    except Exception:
        return {}


def run_daily(
    runner: TaskRunner,
    run: TaskRun,
    exe: Path,
    tasks: list[str] | None = None,
) -> TaskState:
    """执行星铁任务，阻塞直到结束（调用方应放在后台线程）。

    `tasks` 为空时跑默认的 `daily`（保持原有行为）。
    选中多个任务时依次串行执行，全部成功才算成功。
    """
    if not exe.is_file():
        runner.finish(run, TaskState.FAILED, error=f"未找到 m7a.exe：{exe}")
        return TaskState.FAILED

    ids = [t for t in (tasks or []) if t.strip()] or [TASK_ID]

    # 前置：把游戏窗口切到前台。窗口在后台时 M7A 能截图但点击无效，
    # 表现为日志里反复「切换至 手机菜单 时基准图像错误」。
    moved = activate("StarRail.exe")
    runner.append_log(
        run,
        "游戏窗口已前置" if moved else "游戏当前未运行，将由 M7A 自行启动（正常流程）",
    )

    total = len(ids)
    for index, task_id in enumerate(ids, 1):
        if run.ended_at is not None:
            return run.state

        if total > 1:
            runner.append_log(run, f"—— 第 {index}/{total} 个任务：{task_id} ——")

        session = M7aSession(exe, task_id)
        try:
            run_id = session.start()
        except RuntimeError as exc:
            runner.finish(run, TaskState.FAILED, error=str(exc))
            return TaskState.FAILED

        run.engine_run_id = run_id
        runner.append_log(
            run,
            f"$ m7a.exe {task_id} --after-finish None --detach"
            + (f"  → 运行编号 {run_id}" if run_id else "  → 未取到运行编号（按日志判定）"),
        )

        state = supervise(runner, run, session, finish=False)
        if state != TaskState.SUCCESS:
            reason = f"任务 {task_id} 未成功，已停止后续任务" if total > 1 else ""
            runner.finish(run, state, error=run.error or reason)
            return state

    runner.finish(run, TaskState.SUCCESS)
    return TaskState.SUCCESS

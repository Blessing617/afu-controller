"""任务相关的 HTTP 接口。

这一层只做三件事：参数校验、把 core 的领域异常翻译成 HTTP 状态码、组装响应。
启动/停止/清理的实际逻辑都在 `core/tasks.py`。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..core import tasks as core_tasks
from ..core.orchestrator import ORCH
from ..core.state import RUNNER, TaskConflict
from ..core.tasks import GAMES, PrecheckError

router = APIRouter(tags=["tasks"])

_VALID_GAMES = tuple(GAMES)


def _as_http(exc: PrecheckError) -> HTTPException:
    status = 409 if exc.error == "locked" else 400
    return HTTPException(
        status_code=status,
        detail={
            "error": exc.error,
            "message": exc.message,
            "missing": [m["id"] for m in exc.missing_items],
            "missing_items": exc.missing_items,
        },
    )


@router.post("/api/tasks/{game}/run")
def run_task(game: str, payload: dict | None = None) -> dict:
    """单游戏启动。

    可选 body：`{"tasks": ["Infrast", "Recruit"]}`。
    传了就按这些子任务执行（并写回引擎配置），不传就按引擎当前配置全跑。
    """
    if game not in GAMES:
        raise HTTPException(status_code=404, detail=f"未知游戏：{game}")

    # 链正在跑的时候不允许**用户**单步插入，否则两个任务抢前台键鼠。
    # 编排器自己走 core.tasks.start_single，不经过这里。
    if ORCH.is_running():
        raise HTTPException(
            status_code=409,
            detail={"error": "chain_running", "message": "正在执行任务链，请先停止"},
        )

    tasks = list((payload or {}).get("tasks") or [])
    try:
        run = core_tasks.start_single(game, tasks=tasks)
    except TaskConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "busy",
                "message": "已有任务在运行",
                "current": exc.current.to_dict() if exc.current else None,
            },
        )
    except PrecheckError as exc:
        raise _as_http(exc)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail={"error": "start_failed", "message": str(exc)}
        )
    return run.to_dict()


@router.post("/api/cleanup/all")
def cleanup_everything() -> dict:
    """关闭所有游戏与自动化工具（编排页的「关闭游戏和工具」用）。

    和编排的「停止」不同：停止是「先停任务再清理」，
    这个是**纯粹清理**——任务没在跑、但游戏/工具还留在后台占内存时用它。
    """
    if RUNNER.current() is not None:
        raise HTTPException(
            status_code=409,
            detail={"error": "busy", "message": "有任务在运行，请先停止"},
        )

    killed = core_tasks.cleanup_all_now()
    return {
        "killed": killed,
        "message": ("已关闭：" + "、".join(killed)) if killed else "没有需要关闭的进程",
    }


@router.post("/api/games/{game}/cleanup")
def cleanup_game(game: str) -> dict:
    """手机端主动关闭某个游戏相关的进程，释放内存。"""
    if game not in GAMES:
        raise HTTPException(status_code=404, detail=f"未知游戏：{game}")

    killed = core_tasks.cleanup_game_now(game)
    return {
        "game": game,
        "killed": killed,
        "message": ("已关闭：" + "、".join(killed)) if killed else "没有需要关闭的进程",
    }


@router.get("/api/tasks/current")
def current_task() -> dict:
    run = RUNNER.current()
    return {
        "current": run.to_dict() if run else None,
        "history": [r.to_dict() for r in RUNNER.history(10)],
    }


@router.post("/api/tasks/stop")
def stop_task() -> dict:
    try:
        return core_tasks.stop_current().to_dict()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

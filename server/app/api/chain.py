"""任务链接口。

- `GET  /api/chain`              当前任务链
- `PUT  /api/chain`              保存任务链（整份替换，自动备份）
- `POST /api/chain/run`          开始执行
- `POST /api/chain/stop`         停止整条链
- `GET  /api/chain/status`       链执行状态
- `GET  /api/engines/{game}/tasks` 该引擎的能力清单
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..core.chain import Chain, ChainError, load_chain, save_chain
from ..engine.capability import list_tasks
from ..core.orchestrator import ORCH

router = APIRouter(tags=["chain"])

_VALID_GAMES = ("arknights", "genshin", "starrail")


# ---------------------------------------------------------------- 任务链
@router.get("/api/chain")
def get_chain() -> dict:
    return {"chain": load_chain().to_dict()}


@router.put("/api/chain")
def put_chain(payload: dict) -> dict:
    """整份替换任务链。

    执行中不允许改链：调度器已经按旧链分工，中途改会让结果对不上。
    """
    if ORCH.is_running():
        raise HTTPException(
            status_code=409,
            detail={"error": "chain_running", "message": "任务链执行中，不能修改"},
        )
    try:
        chain = Chain.from_dict(payload)
    except ChainError as exc:
        raise HTTPException(
            status_code=400, detail={"error": "invalid_chain", "message": str(exc)}
        )
    return save_chain(chain)


@router.post("/api/chain/run")
def run_chain() -> dict:
    chain = load_chain()
    if chain.is_empty_for_run():
        raise HTTPException(
            status_code=400,
            detail={"error": "empty_chain", "message": "没有可执行的步骤"},
        )
    try:
        run = ORCH.start(chain)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=409, detail={"error": "busy", "message": str(exc)}
        )
    return run.to_dict()


@router.post("/api/chain/stop")
def stop_chain() -> dict:
    """停止整条链：当前步终止 → 后续不再执行 → 清理残留进程。

    编排的「停止」语义和游戏页的单步停止不同：
    用户点它就是要「全停」，不希望某个游戏还在后台跑着占内存。
    """
    if not ORCH.request_stop():
        raise HTTPException(
            status_code=404, detail={"error": "idle", "message": "没有正在执行的任务链"}
        )

    # 立刻终止当前这一步（不等调度器下一轮轮询）
    try:
        from . import tasks as tasks_api

        tasks_api.stop_current()
    except Exception:
        pass

    # 用户要的是「全停」：关闭所有游戏与工具进程，不管哪个游戏在跑
    cleaned: list[str] = []
    try:
        from ..engine.cleanup import cleanup_all

        cleaned = cleanup_all()
    except Exception:
        pass

    run = ORCH.current()
    result = run.to_dict() if run else {"stopping": True}
    result["cleaned"] = cleaned
    return result


@router.get("/api/chain/status")
def chain_status() -> dict:
    run = ORCH.current()
    return {
        "running": ORCH.is_running(),
        "chain": run.to_dict() if run else None,
    }


# ---------------------------------------------------------------- 能力清单
@router.get("/api/engines/{game}/tasks")
def engine_tasks(game: str) -> dict:
    """某个引擎能执行哪些子任务。

    单个引擎读不到时**不会 500**，而是返回兜底清单并把 `source` 标成 `error`，
    这样界面永远有东西可选，另外两个引擎也照常显示。
    """
    if game not in _VALID_GAMES:
        raise HTTPException(
            status_code=404,
            detail={"error": "unknown_game", "message": f"未知游戏：{game}"},
        )
    from ..platform.discovery import detect_all

    return list_tasks(game, detect_all()).to_dict()

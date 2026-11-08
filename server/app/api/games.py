"""游戏与工具探测结果接口。"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.config import set_manual_path
from ..platform.discovery import KEYS, LABELS, detect_all

router = APIRouter(tags=["games"])

# 三个游戏页面对应的游戏 key
GAME_KEYS = ["genshin", "starrail", "maa_games"]


class PathRequest(BaseModel):
    path: str = ""


def _game_snapshot() -> dict:
    paths = detect_all()

    def ok(*keys: str) -> bool:
        return all(paths.get(k, {}).get("found") for k in keys)

    return {
        "games": {
            "genshin": {
                "label": "原神",
                "ready": ok("genshin", "bettergi"),
                "requires": ["genshin", "bettergi"],
            },
            "starrail": {
                "label": "崩坏：星穹铁道",
                "ready": ok("starrail", "m7a"),
                "requires": ["starrail", "m7a"],
            },
            "arknights": {
                "label": "明日方舟",
                "ready": ok("maa", "mumu"),
                "requires": ["maa", "mumu"],
            },
        },
        "paths": paths,
        "keys": KEYS,
        "labels": LABELS,
    }


@router.get("/api/games")
def games() -> dict:
    return _game_snapshot()


@router.post("/api/discover")
def discover() -> dict:
    detect_all(force=True)
    return _game_snapshot()


@router.post("/api/games/{key}/path")
def set_path(key: str, req: PathRequest) -> dict:
    if key not in KEYS:
        raise HTTPException(status_code=404, detail=f"未知目标：{key}")

    value = (req.path or "").strip().strip('"')
    if not value:
        # 清空手动指定，交回自动探测
        set_manual_path(key, "")
        return {"ok": True, "cleared": True, **_game_snapshot()}

    path = Path(value)
    if not path.is_file():
        raise HTTPException(
            status_code=400,
            detail=f"该路径下没有找到可执行文件：{value}",
        )
    set_manual_path(key, str(path))
    return {"ok": True, **_game_snapshot()}

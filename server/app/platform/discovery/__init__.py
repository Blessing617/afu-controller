"""游戏与工具的路径探测。

对外只暴露 `detect_all()` / `get_game()` 与 `KEYS` / `LABELS`。
每个结果结构：{"path": str, "found": bool, "source": str, "label": str}
source 取值：manual | registry | known-file | scan | cache | none
"""

from __future__ import annotations

from .manager import KEYS, LABELS, detect_all, get_game

__all__ = ["KEYS", "LABELS", "detect_all", "get_game"]

"""依赖清单接口。

给三处用：桌面界面展示、手机端缺失提示、网页控制台。

注：这里**只管「游戏与小助手」这类外部软件**。
公网访问走 Tailscale Funnel（系统级安装，由用户在电脑上一次性配好），
不在这个清单里管理。
"""

from __future__ import annotations

from fastapi import APIRouter

from ..core.deps import deps_status
from ..platform.discovery import detect_all

router = APIRouter(tags=["deps"])


@router.get("/api/deps")
def deps_list(include_paths: bool = False) -> dict:
    """依赖清单。

    这个接口**免鉴权**（见 auth.PUBLIC_PATHS）：网页控制台在配对之前就要能
    告诉用户「还缺什么、去哪装」，否则新用户根本没法开始。
    代价是任何人都能看到「装了没装」。

    所以具体安装路径默认**不返回**，只有带 token 的请求传 include_paths=true 才给，
    避免把用户磁盘目录结构暴露给未授权的人。
    """
    paths = detect_all()
    items = deps_status(paths)
    if not include_paths:
        for item in items:
            item["path"] = ""
    missing = [item["id"] for item in items if not item["found"] and not item["optional"]]
    return {
        "items": items,
        "missing": missing,
        "all_required_ready": not missing,
    }

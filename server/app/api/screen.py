"""游戏实时画面接口。

GET /api/screen/{game}?quality=70  → image/jpeg

设计要点（见 .spec/specs/live-screen）：
- 错误一律返回顶层 {"error","message"}：APP 的 ErrorDetail 按这个结构解析，
  用 HTTPException(detail=...) 会多包一层 detail，手机上就拿不到人话文案了
- 成功时用响应头带元信息（截图时间 / 耗时 / 尺寸），客户端据此显示「这张图是什么时候的」
- 路由是同步函数：FastAPI 会把它放进线程池，20~40ms 的编码不会卡住事件循环
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, Response

from ..platform import window as win
from ..platform.capture import DEFAULT_QUALITY, CaptureError, capture

router = APIRouter(tags=["screen"])


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "message": message})


@router.get("/api/screen/{game}")
def screen(game: str, quality: int = Query(DEFAULT_QUALITY)):
    if game not in win.GAME_PROCESSES:
        options = "、".join(win.GAME_PROCESSES)
        return _error(404, "unknown_game", f"未知游戏：{game}（可选：{options}）")

    try:
        result = capture(game, quality)
    except CaptureError as exc:
        return _error(exc.status, exc.code, exc.message)
    except Exception as exc:  # noqa: BLE001
        # 截图失败只是「这一次没图」，绝不影响正在跑的任务
        return _error(500, "capture_failed", f"截图失败：{exc}")

    return Response(
        content=result.data,
        media_type="image/jpeg",
        headers={
            "X-Captured-At": result.captured_at,
            "X-Capture-Ms": f"{result.elapsed_ms:.1f}",
            "X-Image-Width": str(result.width),
            "X-Image-Height": str(result.height),
            "Cache-Control": "no-store",
        },
    )

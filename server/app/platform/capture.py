"""画面截图：把屏幕抓成一张 JPEG，供手机端实时查看。

为什么三个游戏走同一条「全屏截图」
----------------------------------
- MAA 的 CaptureImage 返回几十 MB base64，另外两个引擎没有稳定的外部截图接口
- 早先方舟额外走一次 `adb exec-out screencap`，要起子进程、依赖模拟器在线，
  失败还要多等一轮超时，期间全局锁一直被持有
- 三个游戏本来共用一张全屏画面，方舟却给出另一种比例，切页观感不一致

所以只保留一条路：屏幕是什么就截什么。游戏没开也能看到桌面。

几条硬约束（见 .spec/specs/live-screen）：
- 不激活、不移动、不改变窗口层级 —— 否则会和引擎的模拟点击抢焦点
- 全黑图不算成功，要返回明确错误（独占全屏 / 屏幕休眠时会出现）
- 全局串行：多个请求同时来时排队，不要并发操作屏幕
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from io import BytesIO

from PIL import Image

from . import window as win
from .capture_win32 import CaptureError, CaptureResult, grab_fullscreen

# 输出尺寸与编码：缩到 960 宽，默认 quality 60 时体积远小于 300KB
MAX_WIDTH = 960
DEFAULT_QUALITY = 60
MIN_QUALITY = 30
MAX_QUALITY = 90

# 全黑判定：缩成 32×32 后亮度最大值低于这个值，就当作「没渲染出画面」
BLACK_LUMA_THRESHOLD = 8

# 同一时刻只允许一个截图：并发操作屏幕既无意义又容易互相干扰
_LOCK = threading.Lock()

__all__ = [
    "CaptureError",
    "CaptureResult",
    "DEFAULT_QUALITY",
    "MAX_WIDTH",
    "capture",
    "clamp_quality",
    "game_label",
    "is_black",
]


def clamp_quality(value: int) -> int:
    """quality 越界时夹紧，而不是报错——用户随手填个数不该拿到 4xx。"""
    try:
        q = int(value)
    except (TypeError, ValueError):
        return DEFAULT_QUALITY
    return max(MIN_QUALITY, min(MAX_QUALITY, q))


def game_label(game: str) -> str:
    return win.GAME_TITLES.get(game, game)


def is_black(image: Image.Image) -> bool:
    """缩小后看亮度极值，判断是否截到一张全黑的图。"""
    small = image.resize((32, 32)).convert("L")
    _, brightest = small.getextrema()
    return brightest < BLACK_LUMA_THRESHOLD


def capture(game: str, quality: int = DEFAULT_QUALITY) -> CaptureResult:
    """截一张全屏画面并编码成 JPEG。"""
    label = game_label(game)
    q = clamp_quality(quality)

    with _LOCK:
        started = time.perf_counter()
        image = grab_fullscreen()

        if is_black(image):
            raise CaptureError(
                "capture_black",
                f"截到的{label}画面是全黑的（屏幕可能被关闭或休眠），请先唤醒电脑",
                409,
            )

        if image.width > MAX_WIDTH:
            ratio = MAX_WIDTH / image.width
            image = image.resize(
                (MAX_WIDTH, max(1, round(image.height * ratio))),
                Image.Resampling.BILINEAR,
            )

        buf = BytesIO()
        image.save(buf, "JPEG", quality=q, optimize=True)
        elapsed = (time.perf_counter() - started) * 1000

        return CaptureResult(
            data=buf.getvalue(),
            width=image.width,
            height=image.height,
            quality=q,
            elapsed_ms=round(elapsed, 1),
            captured_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        )

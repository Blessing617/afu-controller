"""图标与资源：品牌 Logo、三个游戏的图标、资源目录查找。"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

import backend
from motion import PageSwitcher
from tokens import (
    FONT_MONO,
    GAME_ORDER,
    GAME_STYLE,
    GAP_L,
    GAP_M,
    GAP_S,
    RADIUS_CARD,
    SIZE_CODE,
)
from theme import build_qss, palette, system_is_dark
from ui.widgets import StatusPill, _card, _clear_layout, _dot

# QtSvg 是 Essentials 之外的模块，可能没装
try:
    from PySide6.QtSvg import QSvgRenderer as QtSvgRenderer
except Exception:  # noqa: BLE001

    class QtSvgRenderer:  # type: ignore[no-redef]
        def __init__(self, *_a, **_k) -> None:
            raise RuntimeError("缺少 QtSvg")

        def isValid(self) -> bool:  # noqa: N802
            return False

        def render(self, *_a, **_k) -> None:
            return



def _log(msg: str) -> None:
    """写一行日志到数据目录的 app.log（打包后没有控制台）。"""
    try:
        from datetime import datetime

        from app.core.config import DATA_DIR

        path = Path(DATA_DIR) / "app.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")
    except Exception:  # noqa: BLE001
        pass

def _is_admin() -> bool:
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False

class AssetsMixin:
    """图标与资源相关的界面方法。"""

    def _make_logo_pixmap(self, size: int) -> QtGui.QPixmap:
        """用矢量图标文件渲染；没有就从 SVG 源临时画一个。"""
        for path in (
            *self._asset_roots("app-icon.svg"),
            Path(__file__).resolve().parent.parent.parent / "assets" / "icons" / "app-icon.svg",
            Path(getattr(sys, "_MEIPASS", ".")) / "assets" / "icons" / "app-icon.svg",
        ):
            if path.is_file():
                renderer = QtSvgRenderer(str(path))
                if not renderer.isValid():
                    continue
                pix = QtGui.QPixmap(size * 2, size * 2)
                pix.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(pix)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                renderer.render(painter)
                painter.end()
                pix.setDevicePixelRatio(2.0)
                return pix
        # 兜底：画个圆角方块
        pix = QtGui.QPixmap(size, size)
        pix.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setBrush(QtGui.QColor("#4D8DFF"))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(0, 0, size, size, size * 0.24, size * 0.24)
        painter.end()
        return pix

    def _set_game_icon(self, label: QtWidgets.QLabel, key: str) -> None:
        """游戏图标。同一个图标只从磁盘读一次。

        切页会反复走到这里，每次重新打开 PNG/解析 SVG 没有必要；
        缓存按 key 存 QPixmap，缩放留给调用时的 label 尺寸。
        """
        cache = getattr(self, "_game_icon_cache", None)
        if cache is None:
            cache = self._game_icon_cache = {}

        pix = cache.get(key)
        if pix is None:
            pix = self._load_game_icon(key)
            cache[key] = pix

        if pix is not None and not pix.isNull():
            label.setPixmap(
                pix.scaled(
                    label.width(),
                    label.height(),
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
            )
            return

        # 什么都没有就显示简称，至少不空着
        label.setText(GAME_STYLE[key]["short"])

    def _load_game_icon(self, key: str):
        """从磁盘加载一个游戏图标。

        优先用官方图标（`official_ui/` 里是已经统一过规格的版本：
        去掉了底部品牌条、裁成正方形、带透明圆角），
        取不到再退回项目自带的原创矢量图形。
        """
        # 1) 官方图标（已规格化，运行时从本机游戏目录提取后处理）
        for base in self._asset_roots():
            for sub in ("official_ui", "official"):
                for ext in ("png", "ico"):
                    official = base / sub / f"{key}.{ext}"
                    if official.is_file():
                        pix = QtGui.QPixmap(str(official))
                        if not pix.isNull():
                            return pix

        # 2) 项目自带的原创 SVG
        for base in self._asset_roots():
            svg = base / f"game-{key}.svg"
            if svg.is_file():
                renderer = QtSvgRenderer(str(svg))
                if not renderer.isValid():
                    continue
                pix = QtGui.QPixmap(56, 56)
                pix.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(pix)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                renderer.render(painter)
                painter.end()
                pix.setDevicePixelRatio(2.0)
                return pix
        return None

    def _asset_roots(self, *names: str) -> list[Path]:
        """资源目录：打包后在 _MEIPASS 下，源码运行在项目根下。"""
        roots = []
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            roots.append(Path(meipass) / "assets" / "icons")
        roots.append(Path(__file__).resolve().parent.parent.parent / "assets" / "icons")
        return roots

    def _decor_pixmap(self, name: str, width: int, height: int) -> QtGui.QPixmap:
        """渲染装饰图形（水波、气泡、尾鳍），失败时返回空图不报错。"""
        for base in self._asset_roots():
            svg = base / f"{name}.svg"
            if not svg.is_file():
                continue
            renderer = QtSvgRenderer(str(svg))
            if not renderer.isValid():
                continue
            dpr = 2
            pix = QtGui.QPixmap(width * dpr, height * dpr)
            pix.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(pix)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            renderer.render(painter)
            painter.end()
            pix.setDevicePixelRatio(dpr)
            return pix
        return QtGui.QPixmap()

    def _nav_icon(self, name: str, color: str, size: int = 18) -> QtGui.QIcon:
        """把 SVG 图标按指定颜色渲染成 QIcon。

        SVG 里统一用黑色描边，这里用 SourceIn 合成整体着色，
        这样同一份源文件就能服务深浅两套主题与选中/未选中两种状态。
        """
        cache = getattr(self, "_nav_icon_cache", None)
        if cache is None:
            cache = self._nav_icon_cache = {}
        key = (name, color, size)
        cached = cache.get(key)
        if cached is not None:
            return cached

        for base in self._asset_roots():
            svg = base / f"{name}.svg"
            if not svg.is_file():
                continue
            renderer = QtSvgRenderer(str(svg))
            if not renderer.isValid():
                continue
            dpr = 2
            pix = QtGui.QPixmap(size * dpr, size * dpr)
            pix.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(pix)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            renderer.render(painter)
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
            painter.fillRect(pix.rect(), QtGui.QColor(color))
            painter.end()
            pix.setDevicePixelRatio(dpr)
            icon = QtGui.QIcon(pix)
            cache[key] = icon
            return icon
        return QtGui.QIcon()

    def _cache_funnel_domain(self) -> None:
        """把 Tailscale Funnel 的固定域名读出来存进配置。

        域名 = `<本机名>.<tailnet后缀>.ts.net`，用 `tailscale status --json`
        一次就能拿到，不需要用户去敲命令或开网页。
        实测这一步需要管理员权限，所以放在启动时（此时通常已是管理员）。
        """
        try:
            from app.core.config import load_config, save_config

            cfg = load_config()
            cached = str(cfg.get("public_url") or "")

            import json
            import shutil
            import subprocess

            exe = shutil.which("tailscale") or shutil.which("tailscale.exe")
            if not exe and sys.platform == "win32":
                cand = Path("C:/Program Files/Tailscale/tailscale.exe")
                if cand.is_file():
                    exe = str(cand)
            if not exe:
                return

            out = subprocess.run(
                [exe, "status", "--json"],
                capture_output=True,
                text=True,
                timeout=10,
                stdin=subprocess.DEVNULL,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
            if out.returncode != 0:
                # 拿不到（多半是没管理员权限）：保留上次缓存，不覆盖
                return
            data = json.loads(out.stdout)
            dns = str((data.get("Self") or {}).get("DNSName") or "").rstrip(".")
            if not dns.endswith(".ts.net"):
                return
            url = f"https://{dns}"
            if url != cached:
                cfg["public_url"] = url
                save_config(cfg)
                _log(f"已读取 Tailscale 固定域名：{url}")
        except Exception as exc:  # noqa: BLE001
            _log(f"读取 Tailscale 域名失败：{exc}")

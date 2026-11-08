"""电脑端主题：调色板、字体加载、QSS 入口。

QSS 内容在 qss.py（按页面拆开，避免单文件过长）。
这里的配色全部来自 tokens.py，和手机端 Theme.kt 是同一组数值。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtGui, QtWidgets

from tokens import (
    BRAND,
    BRAND_DEEP,
    BRAND_SOFT,
    DANGER,
    DARK_BG,
    DARK_LINE,
    DARK_MUTED,
    DARK_SURFACE,
    DARK_SURFACE_2,
    DARK_TEXT,
    FONT_FILE,
    FONT_FAMILY,
    FONT_TITLE,
    LIGHT_BG,
    LIGHT_LINE,
    LIGHT_MUTED,
    LIGHT_SURFACE,
    LIGHT_SURFACE_2,
    LIGHT_TEXT,
    OK,
    WARN,
)

# 加载成功后这里是实际注册的字体族名；失败时退回系统字体
_loaded_title_family: str = FONT_TITLE


def system_is_dark() -> bool:
    """读系统主题。读不到当深色（深色更省电，截图也不刺眼）。"""
    if sys.platform != "win32":
        return True
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        try:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return int(value) == 0
        finally:
            winreg.CloseKey(key)
    except Exception:  # noqa: BLE001
        return True


def resolve_asset(rel: str) -> Path | None:
    """找随包资源：开发时在项目根，打包后在 _MEIPASS。"""
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / rel)
    here = Path(__file__).resolve().parent
    candidates.append(here.parent / rel)   # desktop/../assets/...
    candidates.append(here / rel)          # desktop/assets/...
    for path in candidates:
        if path.exists():
            return path
    return None


def register_fonts(app: QtWidgets.QApplication) -> str:
    """把标题字体注册进 Qt，返回可用字体族名（失败时返回系统字体名）。"""
    global _loaded_title_family
    path = resolve_asset(FONT_FILE)
    if path is not None:
        font_id = QtGui.QFontDatabase.addApplicationFont(str(path))
        families = QtGui.QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
        if families:
            _loaded_title_family = families[0]
            return _loaded_title_family
    _loaded_title_family = FONT_FAMILY
    return _loaded_title_family


def title_font(pixel_size: int = 23, bold: bool = False) -> QtGui.QFont:
    """标题/数字用的圆体。加载失败时自动是系统字体。"""
    font = QtGui.QFont(_loaded_title_family)
    font.setPixelSize(pixel_size)
    font.setBold(bold)
    return font


def body_font(pixel_size: int = 14, bold: bool = False) -> QtGui.QFont:
    font = QtGui.QFont(FONT_FAMILY)
    font.setPixelSize(pixel_size)
    font.setBold(bold)
    return font


def mono_font(pixel_size: int = 19, bold: bool = False) -> QtGui.QFont:
    font = QtGui.QFont("Consolas")
    font.setStyleHint(QtGui.QFont.Monospace)
    font.setPixelSize(pixel_size)
    font.setBold(bold)
    return font


def palette(dark: bool) -> dict[str, str]:
    if dark:
        return {
            "bg": DARK_BG,
            "surface": DARK_SURFACE,
            "surface2": DARK_SURFACE_2,
            "surface2_hover": "#26365A",
            "line": DARK_LINE,
            "text": DARK_TEXT,
            "muted": DARK_MUTED,
            "brand": BRAND_SOFT,
            "brand_hover": "#85A6FF",
            "ok": "#4CBF76",
            "warn": WARN,
            "danger": "#FF6B6B",
            "sidebar": "#111B30",
            "card_line": "rgba(255, 255, 255, 14)",
            "nav_active_bg": "#1E2E50",
            "nav_active_fg": "#BFD2FF",
            "nav_active_line": "rgba(109, 147, 255, 95)",
            "chip_bg": "#1E2E50",
            "chip_fg": "#BFD2FF",
            "scroll": "#2A3A5C",
        }
    return {
        "bg": LIGHT_BG,
        "surface": LIGHT_SURFACE,
        "surface2": LIGHT_SURFACE_2,
        "surface2_hover": "#FFE9D2",
        "line": LIGHT_LINE,
        "text": LIGHT_TEXT,
        "muted": LIGHT_MUTED,
        "brand": BRAND,
        "brand_hover": "#4B7CF5",
        "ok": "#2E8B4F",
        "warn": "#B87A16",
        "danger": "#C8363A",
        "sidebar": "#FFFFFF",
        "card_line": "rgba(27, 36, 54, 13)",
        "nav_active_bg": "#EAF0FF",
        "nav_active_fg": BRAND_DEEP,
        "nav_active_line": "rgba(58, 111, 240, 90)",
        "chip_bg": "#EAF0FF",
        "chip_fg": BRAND_DEEP,
        "scroll": "#E9DCC7",
    }


def build_qss(dark: bool) -> str:
    from qss import build_qss as _build

    return _build(palette(dark))


__all__ = [
    "build_qss",
    "palette",
    "system_is_dark",
    "register_fonts",
    "resolve_asset",
    "title_font",
    "body_font",
    "mono_font",
]

"""通用小控件：卡片、状态点、状态胶囊。"""

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



def _dot(color: str, size: int = 10) -> QtWidgets.QLabel:
    """一个彩色圆点，用来配合文字表达状态（不只靠颜色，还配文字）。"""
    label = QtWidgets.QLabel()
    label.setFixedSize(size, size)
    label.setStyleSheet(f"background:{color};border-radius:{size // 2}px;")
    return label

def _clear_layout(layout: QtWidgets.QLayout) -> None:
    """清空布局里的控件（用来重建列表）。"""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()

def _card(title: str = "") -> tuple[QtWidgets.QFrame, QtWidgets.QVBoxLayout]:
    """建一个卡片。返回 (卡片, 卡片的竖向布局)。"""
    frame = QtWidgets.QFrame()
    frame.setObjectName("Card")
    outer = QtWidgets.QVBoxLayout(frame)
    outer.setContentsMargins(GAP_L, GAP_L - 4, GAP_L, GAP_L - 4)
    outer.setSpacing(GAP_M)
    if title:
        label = QtWidgets.QLabel(title.upper())
        label.setObjectName("CardTitle")
        outer.addWidget(label)
    return frame, outer

class StatusPill(QtWidgets.QWidget):
    """状态胶囊：圆点 + 文字。颜色与文字同时表达状态，色弱用户也能分辨。"""

    def __init__(self, text: str = "", color: str = "", parent=None) -> None:
        super().__init__(parent)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self._dot = _dot(color or "#888888", 9)
        self._text = QtWidgets.QLabel(text)
        self._text.setWordWrap(True)
        row.addWidget(self._dot, 0, QtCore.Qt.AlignTop)
        row.addWidget(self._text, 1)

    def set(self, text: str, color: str) -> None:
        self._dot.setStyleSheet(f"background:{color};border-radius:4px;")
        self._text.setText(text)


__all__ = ['StatusPill', '_card', '_clear_layout', '_dot']

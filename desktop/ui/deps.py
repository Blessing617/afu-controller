"""依赖清单页：外部软件是否就绪 + 官网链接。"""

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

# 每个游戏依赖哪些外部软件；缺失时用哪个人类可读的名字
_MISSING_LABELS = {
    "maa": "MAA",
    "mumu": "MuMu",
    "genshin": "原神",
    "bettergi": "BetterGI",
    "starrail": "星穹铁道",
    "m7a": "三月七",
}

_GAME_REQUIRES = {
    "arknights": ["maa", "mumu"],
    "genshin": ["genshin", "bettergi"],
    "starrail": ["starrail", "m7a"],
}


def _state_style(color: str) -> str:
    """游戏状态标签做成小胶囊：浅色底 + 状态色文字。"""
    c = color.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return (
        f"color:{color};background:rgba({r},{g},{b},30);"
        "border-radius:11px;padding:4px 10px;font-size:12px;"
    )


class DepsPageMixin:
    """依赖清单页：外部软件是否就绪 + 官网链接。"""

    def _build_deps(self) -> QtWidgets.QWidget:
        page, body = self._scroll_page(
            "依赖清单",
            "这些软件需要自己在电脑上装好，本程序不代为下载。装好后点「重新检查」。",
        )
        card, box = _card("外部软件")
        self.deps_box = box
        self.deps_hint = QtWidgets.QLabel("正在检查…")
        self.deps_hint.setObjectName("Muted")
        box.addWidget(self.deps_hint)

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_check_deps = QtWidgets.QPushButton("重新检查")
        self.btn_check_deps.setObjectName("Primary")
        self.btn_check_deps.setCursor(QtCore.Qt.PointingHandCursor)
        btn_row.addWidget(self.btn_check_deps)
        btn_row.addStretch(1)
        box.addLayout(btn_row)
        body.addWidget(card)
        body.addStretch(1)
        return page

    def _apply_paths(self, paths: dict) -> None:
        if not paths:
            return

        p = palette(self.dark)
        for key in GAME_ORDER:
            requires = _GAME_REQUIRES[key]
            ready = all((paths.get(k) or {}).get("found") for k in requires)
            label = self.game_rows[key][1]
            if ready:
                label.setText("可用")
                label.setStyleSheet(_state_style(p["ok"]))
            else:
                missing = [
                    _MISSING_LABELS[k]
                    for k in requires
                    if not (paths.get(k) or {}).get("found")
                ]
                label.setText("缺 " + "、".join(missing))
                label.setStyleSheet(_state_style(p["warn"]))

    def _load_deps_async(self, force: bool = False) -> None:
        """发起一次依赖检查。

        注意：依赖页是**懒构建**的，启动时它可能还不存在。所以这里所有控件访问
        都要带 hasattr 保护——早先直接写 `self.btn_check_deps`，结果启动阶段就
        AttributeError，后台线程静默死掉，总览页永远停在「正在检查外部软件…」。
        """
        if self._busy:
            return
        self._busy = True
        btn = getattr(self, "btn_check_deps", None)
        if btn is not None:
            btn.setEnabled(False)
        hint = getattr(self, "deps_hint", None)
        if hint is not None:
            hint.setText("正在检查…")
        if getattr(self, "overview_deps", None) is not None and not force:
            self.overview_deps.setText("正在检查外部软件…")

        def work() -> None:
            try:
                from app.core.deps import deps_status
                from app.platform.discovery import detect_all

                paths = detect_all(force=force)
                items = deps_status(paths)
                # 必须用信号回主线程：QTimer.singleShot 在后台线程里不会生效，
                # 因为那个线程没有事件循环 —— 这正是之前界面一直停在「正在检查…」的原因。
                self.sig_deps.emit(items)
            except Exception as exc:  # noqa: BLE001
                self.sig_deps_error.emit(str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _render_deps(self, items: list[dict]) -> None:
        p = palette(self.dark)

        # 总览页先更新——它不依赖依赖页是否存在
        missing_all = [i for i in items if not i["found"] and not i.get("optional")]
        if getattr(self, "overview_deps", None) is not None:
            if missing_all:
                names = "、".join(i["name"] for i in missing_all)
                self.overview_deps.setText(
                    f"⚠ 还缺 {len(missing_all)} 个外部软件：{names}。"
                    "去「依赖清单」页看下载地址。"
                )
                self.overview_deps.setStyleSheet(f"color:{p['danger']};")
            else:
                self.overview_deps.setText("✓ 运行所需的软件都装好了，可以开始用")
                self.overview_deps.setStyleSheet(f"color:{p['ok']};")

        btn = getattr(self, "btn_check_deps", None)
        if btn is not None:
            btn.setEnabled(True)
        self._busy = False

        # 依赖页还没建过：列表等用户真的点进去再渲染
        if not hasattr(self, "deps_box"):
            return

        # 用固定容器，每次清空重建，避免残留旧行
        if not hasattr(self, "_deps_container"):
            self._deps_container = QtWidgets.QWidget()
            col = QtWidgets.QVBoxLayout(self._deps_container)
            col.setContentsMargins(0, 0, 0, 0)
            col.setSpacing(0)
            self._deps_layout = col
            # 插在 hint 之后，而不是索引 0 —— 索引 0 是卡片标题的位置，
            # 插那里会把「外部软件」这个标题挤到列表下面去。
            self.deps_box.insertWidget(1, self._deps_container)

        col = self._deps_layout
        _clear_layout(col)

        for item in items:
            row = QtWidgets.QWidget()
            h = QtWidgets.QHBoxLayout(row)
            h.setContentsMargins(0, 8, 0, 8)
            h.setSpacing(12)

            name_col = QtWidgets.QVBoxLayout()
            name_col.setSpacing(1)
            name = QtWidgets.QLabel(item["name"])
            name_font = name.font()
            name_font.setBold(True)
            name.setFont(name_font)
            role = QtWidgets.QLabel(item["role"])
            role.setObjectName("Muted")
            role.setWordWrap(True)
            # 说明文字很长时不能把整行撑宽，给它一个宽松但有限的最大宽度
            role.setMaximumWidth(460)
            name_col.addWidget(name)
            name_col.addWidget(role)
            h.addLayout(name_col, 1)

            if item["found"]:
                tag = QtWidgets.QLabel("已就绪")
                tag.setStyleSheet(f"color:{p['ok']};")
            elif item.get("optional"):
                tag = QtWidgets.QLabel("可选未装")
                tag.setStyleSheet(f"color:{p['warn']};")
            else:
                tag = QtWidgets.QLabel("未安装")
                tag.setStyleSheet(f"color:{p['danger']};")
            # 标签和链接不参与拉伸，保证它们永远贴在最右边、不会被挤掉
            tag.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)
            h.addWidget(tag)

            link = QtWidgets.QLabel(
                f'<a href="{item["url"]}" style="color:{p["brand"]};'
                f'text-decoration:none;">官网</a>'
            )
            link.setOpenExternalLinks(True)
            link.setCursor(QtCore.Qt.PointingHandCursor)
            link.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)
            h.addWidget(link)

            col.addWidget(row)

        missing = [i for i in items if not i["found"] and not i.get("optional")]
        self.deps_hint.setText(
            "必需项都齐了，可以开始用" if not missing else f"还缺 {len(missing)} 项必需软件"
        )
        self.deps_hint.setStyleSheet(
            f"color:{p['ok'] if not missing else p['danger']};"
        )

    def _render_deps_error(self, msg: str) -> None:
        self._busy = False
        btn = getattr(self, "btn_check_deps", None)
        if btn is not None:
            btn.setEnabled(True)
        hint = getattr(self, "deps_hint", None)
        if hint is not None:
            hint.setText(f"检查失败：{msg}")
        # 总览页也要变：否则用户停在总览页，只会看到「正在检查外部软件…」一直转
        if hasattr(self, "overview_deps"):
            self.overview_deps.setText(f"⚠ 检查外部软件失败：{msg}")
            self.overview_deps.setStyleSheet(f"color:{palette(self.dark)['danger']};")

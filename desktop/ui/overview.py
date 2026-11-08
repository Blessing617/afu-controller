"""总览页：服务状态、手机连接信息、三个游戏是否可用。

连接卡拆在 overview_connect.py，公网地址卡拆在 overview_funnel.py，
这里只负责页面组装、服务卡、游戏卡与快照分发。
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

import backend
from theme import body_font, palette
from tokens import GAME_ORDER, GAME_STYLE, GAP_S
from ui.candy import CandyButton, CandyPill
from ui.overview_connect import ConnectCardMixin, _divider
from ui.overview_funnel import FunnelCardMixin
from ui.widgets import _card


class OverviewPageMixin(ConnectCardMixin, FunnelCardMixin):
    """总览页。"""

    def _build_overview(self) -> QtWidgets.QWidget:
        page, body = self._scroll_page(
            "总览",
            "服务是否正常、手机该填什么、三个游戏能不能跑，一眼看完。",
        )
        p = palette(getattr(self, "dark", False))

        # ---- 服务 ----
        card, box = _card("")
        top = QtWidgets.QHBoxLayout()
        top.setSpacing(10)
        self.overview_service = CandyPill("正在启动…", p["warn"])
        top.addWidget(self.overview_service, 0)
        top.addStretch(1)
        self.btn_toggle = CandyButton("停止服务", "danger")
        self.btn_toggle.setFixedHeight(34)
        top.addWidget(self.btn_toggle, 0)
        box.addLayout(top)

        self.overview_note = QtWidgets.QLabel("")
        self.overview_note.setObjectName("Muted")
        self.overview_note.setWordWrap(True)
        box.addWidget(self.overview_note)

        self.deps_divider = _divider(p)
        box.addWidget(self.deps_divider)

        self.overview_deps = QtWidgets.QLabel("正在检查外部软件…")
        self.overview_deps.setWordWrap(True)
        self.overview_deps.setStyleSheet(f"color:{p['muted']};")
        box.addWidget(self.overview_deps)
        body.addWidget(card)

        # ---- 手机怎么连 ----
        body.addWidget(self._build_connect_card())

        # ---- 三个游戏 ----
        card, box = _card("三个游戏")
        self.game_rows: dict[str, tuple[QtWidgets.QLabel, QtWidgets.QLabel]] = {}
        for index, key in enumerate(GAME_ORDER):
            if index:
                box.addWidget(_divider(p))
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(12)
            icon = QtWidgets.QLabel()
            # 44px：比图标本身略大一点，留出呼吸空间，也避免圆角被贴边切掉
            icon.setFixedSize(44, 44)
            icon.setAlignment(QtCore.Qt.AlignCenter)
            self._set_game_icon(icon, key)
            name = QtWidgets.QLabel(GAME_STYLE[key]["label"])
            name.setFont(body_font(13.5, bold=True))
            state = QtWidgets.QLabel("读取中…")
            state.setObjectName("GameState")
            state.setStyleSheet(f"color:{p['muted']};font-size:12px;")
            state.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            row.addWidget(icon, 0)
            row.addWidget(name, 0)
            row.addStretch(1)
            row.addWidget(state, 0)
            box.addLayout(row)
            self.game_rows[key] = (icon, state)
        body.addWidget(card)

        # ---- 公网固定地址 ----
        body.addWidget(self._build_funnel_card())
        body.addStretch(1)
        return page

    def _apply_snapshot(self, snap) -> None:
        """把后台采集到的连接信息画到界面上。

        只在数据真的变了的时候才动控件：`ConnectionCollector` 已经做了
        「内容相同不发信号」，这里再拿一次本地快照做保险。
        """
        if not isinstance(snap, backend.ConnectionSnapshot):
            return
        if snap == self._last_snapshot:
            return
        self._last_snapshot = snap

        self._apply_connect_snapshot(snap)
        self._render_funnel(snap.tailscale)

"""总览页的「手机怎么连上这台电脑」卡片。

拆出来单独一个文件：它既是总览页最大的卡片，也是改动最频繁的地方。
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

import backend
from theme import body_font, mono_font, palette, title_font
from tokens import GAP_M, GAP_S, SIZE_CODE
from ui.candy import CandyButton, CandyFoldRow, CandyPill
from ui.widgets import _card


def _step_row(number: int, text: str, p: dict[str, str]) -> QtWidgets.QWidget:
    """「① 填地址」这种带圆号的步骤标题。"""
    row = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    num = QtWidgets.QLabel(str(number))
    num.setFixedSize(20, 20)
    num.setAlignment(QtCore.Qt.AlignCenter)
    num.setStyleSheet(
        f"background:{p['nav_active_bg']};color:{p['nav_active_fg']};"
        "border-radius:10px;font-size:11px;font-weight:bold;"
    )
    label = QtWidgets.QLabel(text)
    label.setFont(body_font(13, bold=True))
    layout.addWidget(num)
    layout.addWidget(label)
    layout.addStretch(1)
    return row


def _divider(p: dict[str, str]) -> QtWidgets.QLabel:
    line = QtWidgets.QLabel()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background:{p['line']};")
    return line


class ConnectCardMixin:
    """连接卡：地址 → 配对码，两步竖排。"""

    def _build_connect_card(self) -> QtWidgets.QWidget:
        p = palette(getattr(self, "dark", False))
        card, box = _card("手机怎么连上这台电脑")

        intro = QtWidgets.QLabel("打开手机上的「阿福代肝控制器」APP，按下面两步填。")
        intro.setObjectName("Muted")
        intro.setWordWrap(True)
        box.addWidget(intro)

        # ---- 第 1 步：地址 ----
        box.addSpacing(GAP_S)
        box.addWidget(_step_row(1, "填地址", p))

        addr_row = QtWidgets.QHBoxLayout()
        addr_row.setSpacing(10)
        self.primary_addr = QtWidgets.QLabel("正在获取…")
        self.primary_addr.setObjectName("Addr")
        self.primary_addr.setFont(mono_font(19, bold=True))
        self.primary_addr.setWordWrap(True)
        self.primary_addr.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        addr_row.addWidget(self.primary_addr, 1)
        box.addLayout(addr_row)

        # 徽标与复制按钮单独一行：窄窗口（860px）下地址才不会被迫断行
        action_row = QtWidgets.QHBoxLayout()
        action_row.setSpacing(10)
        self.addr_source = CandyPill("检查中", p["warn"])
        self.addr_source.setFixedHeight(24)
        action_row.addWidget(self.addr_source, 0)
        action_row.addStretch(1)
        self.btn_copy_addr = CandyButton("复制地址", "accent")
        self.btn_copy_addr.setFixedHeight(38)
        action_row.addWidget(self.btn_copy_addr, 0)
        box.addLayout(action_row)

        self.addr_hint = QtWidgets.QLabel("")
        self.addr_hint.setObjectName("Muted")
        self.addr_hint.setWordWrap(True)
        box.addWidget(self.addr_hint)

        # ---- 其它地址：默认折叠，避免同一组信息显示两遍 ----
        self.addr_fold = CandyFoldRow("其它可用地址")
        self.addr_fold.clicked.connect(self._on_toggle_extra_addrs)
        fold_row = QtWidgets.QHBoxLayout()
        fold_row.setContentsMargins(0, 0, 0, 0)
        fold_row.addWidget(self.addr_fold, 0)
        fold_row.addStretch(1)
        box.addSpacing(2)
        box.addLayout(fold_row)

        self.extra_addr_box = QtWidgets.QWidget()
        self.connect_addrs = QtWidgets.QVBoxLayout(self.extra_addr_box)
        self.connect_addrs.setContentsMargins(0, 2, 0, 0)
        self.connect_addrs.setSpacing(4)
        self.extra_addr_box.setVisible(False)
        box.addWidget(self.extra_addr_box)

        # 兼容旧字段：只用于内部状态，不再直接显示
        self.addr_label = QtWidgets.QLabel("")
        self.addr_label.setVisible(False)
        box.addWidget(self.addr_label)

        # ---- 第 2 步：配对码 ----
        box.addSpacing(GAP_S)
        box.addWidget(_divider(p))
        box.addSpacing(GAP_S)
        box.addWidget(_step_row(2, "填配对码", p))

        code_row = QtWidgets.QHBoxLayout()
        code_row.setSpacing(12)
        self.pair_pill = CandyPill("未配对", p["warn"])
        self.code_label = QtWidgets.QLabel("—")
        self.code_label.setFont(mono_font(SIZE_CODE - 2, bold=True))
        self.code_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        code_row.addWidget(self.pair_pill, 0)
        code_row.addWidget(self.code_label, 0)
        code_row.addStretch(1)
        self.btn_refresh_code = CandyButton("换一个", "soft")
        self.btn_refresh_code.setFixedHeight(34)
        code_row.addWidget(self.btn_refresh_code, 0)
        box.addLayout(code_row)

        self.code_hint = QtWidgets.QLabel("配对码只能用一次，有效期 5 分钟。")
        self.code_hint.setObjectName("Muted")
        self.code_hint.setWordWrap(True)
        box.addWidget(self.code_hint)

        return card

    def _on_toggle_extra_addrs(self) -> None:
        fold = getattr(self, "addr_fold", None)
        box = getattr(self, "extra_addr_box", None)
        if fold is None or box is None:
            return
        fold.toggle_text()
        box.setVisible(fold.checked)

    def _apply_connect_snapshot(self, snap: backend.ConnectionSnapshot) -> None:
        """把采集到的地址与配对信息画到连接卡上。"""
        p = palette(self.dark)

        if snap.primary:
            self.primary_addr.setText(snap.primary)
            self.addr_hint.setText(snap.primary_hint)
            is_public = snap.primary.startswith("https://")
            self.addr_source.set_state("公网固定" if is_public else "局域网", p["ok"] if is_public else p["warn"])
            if hasattr(self, "set_side_source"):
                self.set_side_source(
                    "公网固定" if is_public else "仅局域网",
                    p["ok"] if is_public else p["warn"],
                )
        else:
            self.primary_addr.setText("正在获取…")
            self.addr_hint.setText("")
            self.addr_source.set_state("检查中", p["warn"])

        # 配对状态
        if snap.paired:
            self.pair_pill.set_state("已配对", p["ok"])
            self.code_label.setText("")
            self.btn_refresh_code.setText("重新配对")
            self.code_hint.setText("需要换一台手机时，点「重新配对」生成新的配对码。")
        else:
            self.pair_pill.set_state("未配对", p["warn"])
            self.code_label.setText(snap.pairing_code or "—")
            self.btn_refresh_code.setText("换一个")
            self.code_hint.setText("配对码只能用一次，有效期 5 分钟。")

        # 其它地址
        kind = {"tailscale": "Tailscale", "lan": "局域网", "other": "其它"}
        others = list(snap.addresses or [])
        if others:
            self.addr_fold.setText(f"其它可用地址（{len(others)}）")
            self.addr_fold.setVisible(True)
        else:
            self.addr_fold.setVisible(False)
            self.extra_addr_box.setVisible(False)
            self.addr_fold.checked = False

        from ui.widgets import _clear_layout

        _clear_layout(self.connect_addrs)
        for a in others:
            row = QtWidgets.QWidget()
            h = QtWidgets.QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(10)
            addr = QtWidgets.QLabel(a.text)
            addr.setFont(mono_font(13))
            addr.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            tag = QtWidgets.QLabel(kind.get(a.kind, ""))
            tag.setObjectName("Muted")
            h.addWidget(addr)
            h.addWidget(tag)
            h.addStretch(1)
            self.connect_addrs.addWidget(row)

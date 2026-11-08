"""糖果风格的自绘控件：按钮、状态胶囊、折叠行。

为什么不全靠 QSS：QSS 做不到「按压缩放回弹」和「按钮底部厚度」，
而这两样正是本次视觉方向的核心。自绘的代价是要自己管字号、悬停、禁用态，
但换来的是布局不抖动（不用改 geometry）和一致的按压手感。
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from theme import body_font, palette, title_font
from tokens import ACCENT, ACCENT_DEEP, BRAND, BRAND_DEEP, MOTION_TAP_MS


def _is_dark(widget: QtWidgets.QWidget) -> bool:
    return bool(getattr(widget.window(), "dark", False))


class CandyButton(QtWidgets.QPushButton):
    """按 kind 画成糖果按钮：primary / accent / soft / ghost / danger。"""

    def __init__(self, text: str = "", kind: str = "soft", parent=None) -> None:
        super().__init__(text, parent)
        self.kind = kind
        self._press = 0.0
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self._anim = QtCore.QVariantAnimation(self)
        self._anim.setDuration(MOTION_TAP_MS)
        self._anim.valueChanged.connect(self._on_anim)

    # ---- 动画 ----
    def _on_anim(self, value) -> None:
        self._press = float(value)
        self.update()

    def _animate_to(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._press)
        self._anim.setEndValue(target)
        self._anim.start()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == QtCore.Qt.LeftButton and self.isEnabled():
            self._animate_to(1.0)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._animate_to(0.0)
        super().mouseReleaseEvent(event)

    def enterEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().leaveEvent(event)

    # ---- 尺寸 ----
    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        fm = QtGui.QFontMetrics(self._text_font())
        w = fm.horizontalAdvance(self.text()) + (56 if self.kind in ("primary", "accent") else 40)
        h = 42 if self.kind in ("primary", "accent") else 36
        return QtCore.QSize(w, h)

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return self.sizeHint()

    def _text_font(self) -> QtGui.QFont:
        bold = self.kind in ("primary", "accent")
        return body_font(13.5, bold)

    def _colors(self) -> dict[str, QtGui.QColor]:
        p = palette(_is_dark(self))
        disabled = not self.isEnabled()
        if self.kind == "primary":
            base, top = QtGui.QColor(BRAND), QtGui.QColor("#4B7CF5")
            fg = QtGui.QColor("#FFFFFF")
        elif self.kind == "accent":
            base, top = QtGui.QColor(ACCENT_DEEP), QtGui.QColor("#FF9A82")
            fg = QtGui.QColor("#FFFFFF")
        elif self.kind == "danger":
            base = top = QtGui.QColor("transparent")
            fg = QtGui.QColor(p["danger"])
        elif self.kind == "ghost":
            base = top = QtGui.QColor("transparent")
            fg = QtGui.QColor(p["muted"])
        else:  # soft
            base = top = QtGui.QColor(p["surface2"])
            fg = QtGui.QColor(p["text"])
        if disabled:
            fg = QtGui.QColor(p["muted"])
        return {"base": base, "top": top, "fg": fg, "p": p}

    # ---- 绘制 ----
    def paintEvent(self, event) -> None:  # noqa: N802
        c = self._colors()
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        scale = 1.0 - 0.04 * self._press
        rect = QtCore.QRectF(self.rect())
        shrink_w = rect.width() * (1 - scale) / 2
        shrink_h = rect.height() * (1 - scale) / 2
        rect = rect.adjusted(shrink_w, shrink_h, -shrink_w, -shrink_h)
        radius = rect.height() / 2
        hovered = self.underMouse() and self.isEnabled()
        thick = 3.0 if self.kind in ("primary", "accent") else 0.0

        if c["base"].alpha() > 0 or self.kind in ("soft",):
            painter.setPen(QtCore.Qt.NoPen)
            # 底部厚度：先铺深色，再铺上浮的高光面
            if thick:
                painter.setBrush(QtGui.QColor(c["base"].darker(118)))
                painter.drawRoundedRect(rect, radius, radius)
            grad = QtGui.QLinearGradient(rect.topLeft(), rect.bottomLeft())
            grad.setColorAt(0.0, c["top"].lighter(106) if hovered else c["top"])
            grad.setColorAt(1.0, c["base"])
            painter.setBrush(grad)
            body = rect.adjusted(0, 0, 0, -thick) if thick else rect
            painter.drawRoundedRect(body, radius, radius)
        else:
            # 幽灵 / 危险：只有悬停时才有底色与描边
            if hovered:
                painter.setPen(QtCore.Qt.NoPen)
                painter.setBrush(QtGui.QColor(c["p"]["surface2"]))
                painter.drawRoundedRect(rect, radius, radius)
            if self.kind == "danger":
                pen = QtGui.QPen(c["fg"])
                pen.setWidthF(1.4)
                painter.setPen(pen)
                painter.setBrush(QtCore.Qt.NoBrush)
                painter.drawRoundedRect(rect.adjusted(0.7, 0.7, -0.7, -0.7), radius, radius)

        painter.setPen(c["fg"])
        painter.setFont(self._text_font())
        painter.drawText(rect, QtCore.Qt.AlignCenter, self.text())
        painter.end()


class CandyPill(QtWidgets.QWidget):
    """状态胶囊：圆点 + 文字，底色为状态色的浅化版本。"""

    def __init__(self, text: str = "", color: str = "#3BA55D", parent=None) -> None:
        super().__init__(parent)
        self._text = text
        self._color = QtGui.QColor(color)
        self.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)

    def set_state(self, text: str, color: str) -> None:
        self._text = text
        self._color = QtGui.QColor(color)
        # 文字变长后必须重算 sizeHint，否则布局还按旧宽度排，
        # 后面的字会被裁掉（曾经四步检查表只显示出「①」就是这个原因）。
        self.updateGeometry()
        self.update()

    def set(self, text: str, color: str) -> None:  # 兼容旧的 StatusPill 调用
        self.set_state(text, color)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        fm = QtGui.QFontMetrics(body_font(12.5))
        return QtCore.QSize(fm.horizontalAdvance(self._text) + 48, 30)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        soft = QtGui.QColor(self._color)
        soft.setAlpha(28)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(soft)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        painter.setBrush(self._color)
        dot_r = 3.2
        cy = rect.center().y()
        painter.drawEllipse(QtCore.QPointF(rect.left() + 13, cy), dot_r, dot_r)
        painter.setPen(QtGui.QColor(self._color).darker(115))
        painter.setFont(body_font(12.5))
        painter.drawText(
            rect.adjusted(24, 0, -12, 0), QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, self._text
        )


class CandyFoldRow(QtWidgets.QPushButton):
    """「其它可用地址（3）›」这种可展开的紧凑行。"""

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setFlat(True)
        self.checked = False
        self.setFixedHeight(30)
        self._font = body_font(12)

    def toggle_text(self) -> None:
        self.checked = not self.checked
        self.update()

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        fm = QtGui.QFontMetrics(self._font)
        return QtCore.QSize(fm.horizontalAdvance(self.text()) + 46, 30)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = palette(_is_dark(self))
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QtCore.Qt.NoPen)
        bg = QtGui.QColor(p["brand"])
        bg.setAlpha(22)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 12, 12)
        painter.setPen(QtGui.QColor(p["brand"]))
        painter.setFont(self._font)
        fm = QtGui.QFontMetrics(self._font)
        text_w = fm.horizontalAdvance(self.text())
        painter.drawText(rect.adjusted(12, 0, 0, 0), QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, self.text())
        # 右侧箭头：展开后朝下
        cx = rect.left() + 18 + text_w
        cy = rect.center().y()
        painter.setBrush(QtCore.Qt.NoBrush)
        pen = QtGui.QPen(QtGui.QColor(p["brand"]))
        pen.setWidthF(1.6)
        painter.setPen(pen)
        path = QtGui.QPainterPath()
        if self.checked:
            path.moveTo(cx, cy + 3.5)
            path.lineTo(cx + 4, cy - 1.5)
            path.lineTo(cx + 8, cy + 3.5)
        else:
            path.moveTo(cx, cy - 1.5)
            path.lineTo(cx + 4, cy + 3)
            path.lineTo(cx + 8, cy - 1.5)
        painter.drawPath(path)


class CandyDialog(QtWidgets.QDialog):
    """圆角卡片对话框：标题 + 说明 + 两个糖果按钮。

    替代 QMessageBox：默认的 Windows 消息框是方角灰底，和现在这套界面不是一路的。
    """

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        title: str,
        message: str,
        confirm_text: str = "确定",
        cancel_text: str = "取消",
        danger: bool = False,
    ) -> None:
        super().__init__(parent)
        # _is_dark 读的是 window().dark；对话框自己就是顶层，所以这里补一个同名属性
        self.dark = bool(getattr(parent, "dark", False))
        p = palette(self.dark)
        self.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.FramelessWindowHint)
        self.setModal(True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QtWidgets.QFrame()
        card.setStyleSheet(
            f"QFrame{{background:{p['surface']};border:1px solid {p['card_line']};"
            f"border-radius:22px;}}"
        )
        outer.addWidget(card)

        box = QtWidgets.QVBoxLayout(card)
        box.setContentsMargins(22, 22, 22, 20)
        box.setSpacing(12)

        heading = QtWidgets.QLabel(title)
        heading.setFont(title_font(17))
        heading.setWordWrap(True)
        box.addWidget(heading)

        body = QtWidgets.QLabel(message)
        body.setWordWrap(True)
        body.setStyleSheet(f"color:{p['muted']};")
        box.addWidget(body)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        cancel = CandyButton(cancel_text, "ghost")
        cancel.setFixedHeight(40)
        cancel.clicked.connect(self.reject)
        ok = CandyButton(confirm_text, "danger" if danger else "primary")
        ok.setFixedHeight(40)
        ok.clicked.connect(self.accept)
        row.addWidget(cancel, 1)
        row.addWidget(ok, 1)
        box.addLayout(row)

        self.setMinimumWidth(400)

"""电脑端界面的动效 token 与切换动画。

数值与手机端 `android/.../ui/Motion.kt` 保持同一套（见 tokens.py 顶部说明）。

为什么单独一个模块
------------------
动效最怕「各处各写一套时长和曲线」：同一窗口里一页 120ms 线性、另一页 300ms 弹跳，
看起来就像两个程序拼起来的。所以时长、曲线、位移幅度都在这里定一次。

实现方式
--------
`QStackedWidget` 没有内置转场，所以切页时手工给**目标页**挂两个并行动画：
透明度 0→1、位置「偏移一点点 → 本位」，曲线 OutCubic，200ms。
离场页直接消失（重叠闪烁比重叠淡出更难看，也更容易掉帧）。

两个踩过的坑：
- `QGraphicsOpacityEffect` 会让整页走离屏合成，静止时白吃性能，所以动画一结束就
  `setGraphicsEffect(None)`。
- `QPropertyAnimation(target, b"pos")` 结束后必须还原初始 pos，否则多切几次内容会越飘越远。
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6 import QtCore, QtWidgets

# ---- 时长（毫秒）----
# 同档手机端 ≤ 200ms；桌面窗口大一点，多给 60ms 让它看起来「滑得完」。
DURATION_SWITCH_MS = 220        # 导航项之间切换
DURATION_FADE_MS = 180          # 只做淡入时的兜底

# ---- 位移（占内容区宽度的比例）----
# 不动整页，只给它「落一下」的量。0.06 ≈ 60px/1000px，能感觉到方向，又不头晕。
SLIDE_RATIO = 0.06
SLIDE_MAX_PX = 40

# ---- 曲线 ----
EASING_OUT = QtCore.QEasingCurve.Type.OutCubic


def animations_enabled() -> bool:
    """系统是否允许播放窗口动画。

    Windows 的「显示动画」开关在注册表里；读不到就当允许（多数人默认开着）。
    """
    import sys

    if sys.platform != "win32":
        return True
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop\WindowMetrics"
        )
        try:
            value, _ = winreg.QueryValueEx(key, "MinAnimate")
            return str(value) != "0"
        finally:
            winreg.CloseKey(key)
    except Exception:  # noqa: BLE001
        return True


@dataclass
class _Running:
    """正在跑的动画，防止上一段没结束就被下一次切页覆盖。"""

    opacity: QtCore.QPropertyAnimation | None = None
    pos: QtCore.QPropertyAnimation | None = None
    effect: QtWidgets.QGraphicsOpacityEffect | None = None


class PageSwitcher(QtCore.QObject):
    """给 QStackedWidget 加一层「淡入 + 轻微位移」的切页效果。"""

    def __init__(self, stack: QtWidgets.QStackedWidget, parent=None) -> None:
        super().__init__(parent)
        self._stack = stack
        self._current: QtWidgets.QWidget | None = None

    def show(self, page: QtWidgets.QWidget, *, direction: int = 1) -> None:
        """切到 page。direction=+1 表示往右切（新页从右侧进来），-1 反之。"""
        if page is self._current or page is self._stack.currentWidget():
            if page is not self._stack.currentWidget():
                self._stack.setCurrentWidget(page)
            self._current = page
            return

        if not animations_enabled():
            self._finish_previous()
            self._stack.setCurrentWidget(page)
            self._current = page
            return

        self._finish_previous()
        self._current = page

        offset = min(SLIDE_MAX_PX, max(6, int(self._stack.width() * SLIDE_RATIO)))
        dx = offset * (1 if direction >= 0 else -1)
        home = QtCore.QPoint(0, 0)

        # 先把它摆好再显示，避免「从本位跳到偏移再回来」的闪烁
        page.move(home.x() + dx, home.y())
        self._stack.setCurrentWidget(page)

        effect = QtWidgets.QGraphicsOpacityEffect(page)
        effect.setOpacity(0.0)
        page.setGraphicsEffect(effect)

        group = QtCore.QParallelAnimationGroup(self)
        fade = QtCore.QPropertyAnimation(effect, b"opacity", self)
        fade.setDuration(DURATION_SWITCH_MS)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(EASING_OUT)
        group.addAnimation(fade)

        pos = QtCore.QPropertyAnimation(page, b"pos", self)
        pos.setDuration(DURATION_SWITCH_MS)
        pos.setStartValue(QtCore.QPoint(home.x() + dx, home.y()))
        pos.setEndValue(home)
        pos.setEasingCurve(EASING_OUT)
        group.addAnimation(pos)

        running = _Running(opacity=fade, pos=pos, effect=effect)
        self._running = running

        def _done() -> None:
            # 关键：动画结束立刻卸掉 effect 与偏移，静止时零成本
            page.move(home)
            page.setGraphicsEffect(None)
            self._running = None

        group.finished.connect(_done)
        group.start()
        self._group = group  # 持有引用，否则会被 Python GC 掉

    def _finish_previous(self) -> None:
        running = getattr(self, "_running", None)
        group = getattr(self, "_group", None)
        if group is not None:
            try:
                group.stop()
            except Exception:  # noqa: BLE001
                pass
        if running is not None:
            page = self._stack.currentWidget()
            if page is not None:
                page.move(0, 0)
                page.setGraphicsEffect(None)
        self._running = None
        self._group = None


class FadeIn:
    """给单个控件做一次性淡入（例如刚出现的提示条）。"""

    @staticmethod
    def play(widget: QtWidgets.QWidget) -> None:
        if not animations_enabled():
            return
        effect = QtWidgets.QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
        anim = QtCore.QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(DURATION_FADE_MS)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(EASING_OUT)

        def _done() -> None:
            widget.setGraphicsEffect(None)

        anim.finished.connect(_done)
        anim.start()
        widget._fade_anim = anim  # type: ignore[attr-defined]

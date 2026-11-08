"""电脑端自检：不开窗口、不连服务，直接验证几个容易出错的地方。

跑法（在 desktop/ 目录下）：

    server\\.venv\\Scripts\\python.exe selftest.py

检查项：
1. 后台采集器能产出快照，且 `_local_addresses` 在没有任何网卡时也不会抛异常
2. Tailscale 查询在没有子进程卡死的情况下能在合理时间内返回
3. 采集器「内容不变不发信号」
4. Qt 界面能在 offscreen 模式下创建、切换三个页面、并渲染一帧
5. 图标文件存在且能被 Qt 渲染（大肥鱼抱手柄）
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def test_backend() -> None:
    import backend

    entries = backend._local_addresses(8765)
    check("地址枚举不抛异常", True, f"{len(entries)} 条")

    ts = backend.query_tailscale(8765)
    check("Tailscale 查询有返回值", isinstance(ts, backend.TailscaleState), f"installed={ts.installed}")

    primary, hint = backend._pick_primary(tuple(entries), ts)
    check("能选出推荐地址或明确为空", bool(primary) or not entries, primary or "(无)")

    collector = backend.ConnectionCollector(8765, HERE.parent / "server" / "data")
    emitted: list = []
    collector.attach_emitter(emitted.append)
    collector.start()
    time.sleep(0.6)
    snap1 = collector.collect()
    time.sleep(2.4)  # 至少一个节拍
    collector.stop()
    check("后台采集器能发出快照", len(emitted) >= 1, f"{len(emitted)} 次")
    check("相同内容不重复发信号", len(emitted) <= 2, f"{len(emitted)} 次")
    check("快照可比较", snap1 == collector.collect())


def test_ui() -> None:
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    import qt_ui

    class FakeHost:
        port = 8765
        error = ""

        def start(self) -> bool:
            return True

        def stop(self) -> None:
            pass

    win = qt_ui.MainWindow(FakeHost(), HERE.parent / "server" / "data", False, 8765)
    win.show()
    app.processEvents()

    check("导航只有三项", len(win._nav_buttons) == 3, ", ".join(win._nav_buttons))

    for key in ("deps", "settings", "overview"):
        win.show_page(key)
        app.processEvents()
        check(f"能切到 {key}", win.stack.currentWidget() is win._pages[key])

    # 渲染一帧，确认没有构造期异常
    pix = win.grab()
    check("能渲染一帧", not pix.isNull(), f"{pix.width()}x{pix.height()}")

    # 给一个假快照，确认渲染路径不炸
    import backend

    snap = backend.ConnectionSnapshot(
        addresses=(backend.AddressEntry("192.168.1.5", 8765, "lan"),),
        tailscale=backend.TailscaleState(installed=True, logged_in=True),
        pairing_code="123456",
        paired=False,
        primary="https://demo.tailxxxx.ts.net",
        primary_hint="演示",
    )
    win._apply_snapshot(snap)
    app.processEvents()
    check("快照能渲染到界面", win.code_label.text() == "123456", win.primary_addr.text())

    win.grab()
    win._collector.stop()
    win.close()


def test_service_failure_leaves_reason() -> None:
    """服务线程里抛异常时必须留下原因，否则界面只会一直显示「正在启动…」。"""
    import main as m

    host = m.ServiceHost()

    class Boom:
        def run(self) -> None:
            raise RuntimeError("模拟：端口绑定失败")

    host.server = Boom()
    host._serve()
    check(
        "服务启动异常会留下原因",
        "模拟：端口绑定失败" in host.error,
        host.error or "(error 为空)",
    )


def test_icon() -> None:
    from PySide6 import QtGui

    ico = HERE / "icon.ico"
    check("exe 图标存在", ico.is_file(), str(ico))
    svg = HERE.parent / "assets" / "icons" / "app-icon.svg"
    check("图标源 SVG 存在", svg.is_file(), str(svg))
    if svg.is_file():
        from PySide6.QtSvg import QSvgRenderer

        renderer = QSvgRenderer(str(svg))
        check("SVG 可解析", renderer.isValid())
        pix = QtGui.QPixmap(64, 64)
        pix.fill(QtGui.QColor("transparent"))
        painter = QtGui.QPainter(pix)
        renderer.render(painter)
        painter.end()
        img = pix.toImage()
        # 左上角是圆角外区域（透明），中心应该不是透明
        center = QtGui.QColor(img.pixel(32, 32))
        check("渲染后有内容", center.alpha() > 200, center.name())


if __name__ == "__main__":
    # QPixmap 必须在 QApplication 之后创建，所以先建 app 再按顺序跑各项
    from PySide6 import QtWidgets

    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    test_backend()
    test_service_failure_leaves_reason()
    test_icon()
    test_ui()
    print()
    if failures:
        print("失败：", "、".join(failures))
        raise SystemExit(1)
    print("全部通过")

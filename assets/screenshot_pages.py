"""自动截取 Qt 主窗口的各页面，用于人工检查界面效果。

用法（在 desktop 目录下）：
    ..\\server\\.venv\\Scripts\\python.exe ..\\assets\\screenshot_pages.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def find_window(title: str):
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if buf.value == title:
                    found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def main() -> None:
    from PySide6 import QtWidgets
    from PIL import ImageGrab

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    hwnd = find_window("阿福代肝控制器")
    if not hwnd:
        raise SystemExit("找不到窗口，请先启动 desktop/main.py")

    import ctypes

    user32 = ctypes.windll.user32

    # 把窗口放到固定位置并指定一个够大的尺寸，再按**实际**矩形截图。
    # 之前写死截图区域，窗口实际比截的区域小时会看起来「内容被截断」，其实是截多了。
    user32.MoveWindow(hwnd, 30, 20, 1000, 720, True)
    user32.SetForegroundWindow(hwnd)
    time.sleep(1.0)

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    box = (rect.left, rect.top, rect.right, rect.bottom)
    print(f"窗口实际矩形：{box[2] - box[0]}x{box[3] - box[1]}")

    out_dir = ROOT / "_shots"
    out_dir.mkdir(exist_ok=True)

    # 依次点侧边栏四个导航项（坐标相对窗口左上角，随窗口位置走）
    left = rect.left
    top = rect.top
    targets = [
        ("overview", left + 130, top + 212),
        ("deps", left + 130, top + 272),
        ("connect", left + 130, top + 332),
        ("settings", left + 130, top + 392),
    ]
    for name, x, y in targets:
        user32.SetCursorPos(x, y)
        time.sleep(0.15)
        user32.mouse_event(0x02, 0, 0, 0, 0)   # 左键按下
        time.sleep(0.06)
        user32.mouse_event(0x04, 0, 0, 0, 0)   # 左键抬起
        time.sleep(1.5)
        img = ImageGrab.grab(bbox=box)
        path = out_dir / f"{name}.png"
        img.save(path)
        print(f"已截图 {path}  ({img.size[0]}x{img.size[1]})")

    print("完成")


if __name__ == "__main__":
    main()

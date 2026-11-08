"""Windows 相关的小工具：权限、锁屏。"""

from __future__ import annotations

from . import proc

import ctypes
import subprocess


def is_admin() -> bool:
    """当前进程是否具备管理员权限。"""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def is_locked() -> bool:
    """是否处于锁屏状态。

    已登录且已解锁时 LogonUI.exe 通常不在运行；锁屏时它会被启动。
    """
    try:
        out = proc.run(
            ["tasklist", "/FI", "IMAGENAME eq LogonUI.exe"],
            capture_output=True,
            timeout=5,
            stdin=subprocess.DEVNULL,
        )
        return b"LogonUI.exe" in out.stdout
    except Exception:
        return False


def process_alive(image_name: str) -> bool:
    """按镜像名判断进程是否在跑。"""
    try:
        out = proc.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}"],
            capture_output=True,
            timeout=5,
            stdin=subprocess.DEVNULL,
        )
        return image_name.lower().encode() in out.stdout.lower()
    except Exception:
        return False

"""子进程执行工具：抑制控制台窗口闪现。

背景（实测）：
服务用 PyInstaller `--windowed` 打包，进程本身没有控制台。
此时 `subprocess` 启动任意子进程（tasklist / taskkill / MuMuManager…）
都会为新进程创建一个控制台窗口——表现为屏幕上每 5 秒闪一下黑框。

统一通过 `CREATE_NO_WINDOW` 抑制。
"""

from __future__ import annotations

import subprocess

CREATE_NO_WINDOW = 0x08000000


def run(cmd: list[str], timeout: float = 15, cwd: str | None = None, **kwargs) -> subprocess.CompletedProcess:
    """执行命令并捕获输出，不弹窗口。

    多余的关键字（capture_output / stdin / creationflags …）会被忽略，
    统一由这里设置，避免调用点各写一套。
    """
    kwargs.pop("capture_output", None)
    kwargs.pop("stdin", None)
    kwargs.pop("creationflags", None)
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        timeout=timeout,
        stdin=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
    )


def spawn(cmd: list[str], cwd: str | None = None, **kwargs) -> subprocess.Popen:
    """后台启动一个进程，不弹窗口、不占用标准流。"""
    for k in ("stdin", "stdout", "stderr", "creationflags"):
        kwargs.pop(k, None)
    return subprocess.Popen(
        cmd,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
    )

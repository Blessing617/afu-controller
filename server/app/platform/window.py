"""窗口管理：把游戏窗口切到前台、把工具窗口最小化。

背景（实测）：
- M7A / BetterGI 依靠「窗口截图 + 模拟点击」，窗口不在前台时点击无效
- 单纯 SetForegroundWindow 经常失败：Windows 有「前台窗口锁定」，
  当调用者不是当前前台进程时会被拒绝（日志：Failed to set window foreground）
- 多个工具窗口（MAA / MuMu / BGI）同时存在时会互相抢焦点

解法：
- 激活：AttachThreadInput 附加到前台线程，绕过前台锁
- 最小化：工具窗口启动后立刻收起来，别跟游戏抢
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import proc

import ctypes
import subprocess
import time
from ctypes import wintypes

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

SW_RESTORE = 9
SW_MINIMIZE = 6

# 每个游戏「画面在哪个进程的窗口上」：
# - 原神 / 星铁：游戏本体进程
# - 方舟：跑在 MuMu 模拟器里，所以要截模拟器窗口（不截 MAA 自己的界面）
GAME_PROCESSES: dict[str, list[str]] = {
    "genshin": ["YuanShen.exe", "GenshinImpact.exe"],
    "starrail": ["StarRail.exe"],
    "arknights": [
        # 实测：MuMu 12 有两个进程——NxDevice 是安卓设备（游戏画面所在），
        # NxMain 是多开管理器（新建设备/批量操作），不能只按 NxMain 找
        "MuMuNxDevice.exe",
        "MuMuNxMain.exe",
        "MuMuPlayer.exe",
        "MuMuVMMHeadless.exe",
        "NemuPlayer.exe",
    ],
}

GAME_TITLES: dict[str, str] = {
    "arknights": "明日方舟",
    "genshin": "原神",
    "starrail": "崩坏：星穹铁道",
}

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# 找到的游戏窗口：句柄 + 屏幕矩形 + 是否最小化
@dataclass
class GameWindow:
    hwnd: int
    title: str
    left: int
    top: int
    width: int
    height: int
    minimized: bool


class _WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.UINT),
        ("flags", wintypes.UINT),
        ("showCmd", wintypes.UINT),
        ("ptMinPosition", wintypes.POINT),
        ("ptMaxPosition", wintypes.POINT),
        ("rcNormalPosition", wintypes.RECT),
    ]


# 显式声明句柄参数/返回值类型：64 位下不声明时 ctypes 按 int 处理，
# 句柄会被截断（HWND 的数值通常侥幸落在 32 位内，进程 HANDLE 则不一定）。
_user32.IsWindowVisible.argtypes = [wintypes.HWND]
_user32.IsWindowVisible.restype = wintypes.BOOL
_user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
_user32.GetWindowTextLengthW.restype = ctypes.c_int
_user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_user32.GetWindowTextW.restype = ctypes.c_int
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD
_user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_user32.GetWindowRect.restype = wintypes.BOOL
_user32.IsIconic.argtypes = [wintypes.HWND]
_user32.IsIconic.restype = wintypes.BOOL
_user32.GetWindowPlacement.argtypes = [wintypes.HWND, ctypes.POINTER(_WINDOWPLACEMENT)]
_user32.GetWindowPlacement.restype = wintypes.BOOL

_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
_kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL


def _pids_of(image_name: str) -> set[int]:
    try:
        out = proc.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/FO", "CSV", "/NH"],
            capture_output=True,
            timeout=8,
            stdin=subprocess.DEVNULL,
        )
        raw = out.stdout
    except Exception:
        return set()

    pids: set[int] = set()
    for enc in ("gbk", "utf-8"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith('"'):
            continue
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2:
            try:
                pids.add(int(parts[1]))
            except ValueError:
                continue
    return pids


def _windows_of(pids: set[int]) -> list[int]:
    found: list[int] = []

    def _cb(hwnd, _lparam):
        if not _user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and _user32.GetWindowTextLengthW(hwnd) > 0:
            found.append(hwnd)
        return True

    _user32.EnumWindows(_WNDENUMPROC(_cb), 0)
    return found


def _force_foreground(hwnd: int) -> bool:
    """绕过前台锁把窗口提到最前。"""
    _user32.ShowWindow(hwnd, SW_RESTORE)
    time.sleep(0.15)

    fg = _user32.GetForegroundWindow()
    if fg == hwnd:
        return True

    fg_tid = _user32.GetWindowThreadProcessId(fg, None) if fg else 0
    cur_tid = _kernel32.GetCurrentThreadId()

    attached = False
    if fg_tid and fg_tid != cur_tid:
        attached = bool(_user32.AttachThreadInput(fg_tid, cur_tid, True))

    try:
        _user32.BringWindowToTop(hwnd)
        _user32.SetForegroundWindow(hwnd)
        _user32.SetFocus(hwnd) if _user32.GetForegroundWindow() == hwnd else None
    finally:
        if attached:
            _user32.AttachThreadInput(fg_tid, cur_tid, False)

    time.sleep(0.3)
    return _user32.GetForegroundWindow() == hwnd


def activate(image_name: str, retries: int = 3) -> bool:
    """把 image_name 的主窗口切到前台，带重试。"""
    pids = _pids_of(image_name)
    if not pids:
        return False
    wins = _windows_of(pids)
    if not wins:
        return False

    hwnd = wins[0]
    for _ in range(retries):
        if _force_foreground(hwnd):
            return True
        time.sleep(0.4)
    return False


def minimize(image_name: str) -> int:
    """最小化某个程序的所有窗口，返回处理数量。"""
    pids = _pids_of(image_name)
    if not pids:
        return 0
    count = 0
    for hwnd in _windows_of(pids):
        _user32.ShowWindow(hwnd, SW_MINIMIZE)
        count += 1
    return count


def _exe_name_of_pid(pid: int) -> str:
    """拿到进程的可执行文件名。

    不用 tasklist 子进程：截图路径要跑在 100ms 预算内，
    而起一个 tasklist 就要几十毫秒（还会在打包后的无控制台环境里闪窗）。
    """
    if not pid:
        return ""
    handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if not _kernel32.QueryFullProcessImageNameW(
            handle, 0, buf, ctypes.byref(size)
        ):
            return ""
        return Path(buf.value).name
    except Exception:
        return ""
    finally:
        _kernel32.CloseHandle(handle)


def _normal_rect(hwnd: int) -> wintypes.RECT:
    """最小化窗口的 GetWindowRect 是 (-32000, -32000)，改用还原后的位置。"""
    placement = _WINDOWPLACEMENT()
    placement.length = ctypes.sizeof(_WINDOWPLACEMENT)
    if _user32.GetWindowPlacement(hwnd, ctypes.byref(placement)):
        return placement.rcNormalPosition
    return wintypes.RECT()


def _window_title(hwnd: int) -> str:
    length = _user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def find_game_window(game: str) -> GameWindow | None:
    """按游戏定位它当前的主窗口。

    同一进程可能有多个窗口（启动器、报错框、遮罩），取面积最大的可见顶层窗口。
    不激活、不移动窗口——截图不应该影响正在运行的任务。
    """
    names = {name.lower() for name in GAME_PROCESSES.get(game, [])}
    if not names:
        return None

    best: GameWindow | None = None
    best_area = 0

    def _cb(hwnd, _lparam):
        nonlocal best, best_area
        if not _user32.IsWindowVisible(hwnd):
            return True
        if _user32.GetWindowTextLengthW(hwnd) == 0:
            return True

        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return True
        if _exe_name_of_pid(pid.value).lower() not in names:
            return True

        minimized = bool(_user32.IsIconic(hwnd))
        if minimized:
            rect = _normal_rect(hwnd)
        else:
            rect = wintypes.RECT()
            if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return True

        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width < 64 or height < 64:
            return True

        area = width * height
        if area > best_area:
            best_area = area
            best = GameWindow(
                hwnd=int(hwnd),
                title=_window_title(hwnd),
                left=int(rect.left),
                top=int(rect.top),
                width=width,
                height=height,
                minimized=minimized,
            )
        return True

    try:
        _user32.EnumWindows(_WNDENUMPROC(_cb), 0)
    except Exception:
        return None
    return best

"""服务运行期间保持电脑唤醒。

背景（实机踩到）：用户带手机出门，服务常驻在家里的电脑上。系统屏保是
「180 秒 + 安全屏保」，也就是 3 分钟不操作就锁屏。之后手机点「开始」跑原神 / 星铁
会被拒绝——这两个必须模拟键鼠、必须让游戏窗口在前台，锁屏状态做不到。

做法（实测三种手段只有第三种可靠）：
1. `SetThreadExecutionState(ES_CONTINUOUS|ES_SYSTEM_REQUIRED|ES_DISPLAY_REQUIRED)`
   —— 阻止显示器休眠与系统睡眠；
2. 改屏保开关（注册表 / SystemParametersInfo）—— 在这台机器上被策略拒绝，无效；
3. **周期性按一下 F24 键**（虚拟功能键，按下立即释放）—— 重置系统空闲计时器，
   屏保与锁屏都不会触发。不用 Shift 是因为原神里 Shift 是冲刺键，任务执行时
   按下去会干扰脚本；F24 在三个游戏和应用里都没有绑定。
   任务运行期间干脆不按（引擎自己就在模拟操作，系统本来就不会判定空闲）。

不处理：用户主动 Win+L 锁屏。那是用户的选择，任务启动时会明确提示「请先在电脑上解锁」。
"""

from __future__ import annotations

import ctypes
import threading

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

# 屏保开关用 SystemParametersInfo 改（用户级、系统会广播变更）；
# 直接写注册表 HKCU\Control Panel\Desktop 会被拒绝访问。
SPI_GETSCREENSAVEACTIVE = 0x0010
SPI_SETSCREENSAVEACTIVE = 0x0011
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02

_REFRESH_SECONDS = 45  # 远小于屏保的 180 秒

_lock = threading.Lock()
_started = False
_original_screensaver: int | None = None
_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _set_execution_state(flags: int) -> None:
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
    except Exception:  # noqa: BLE001
        pass


def _read_screensaver() -> int | None:
    """读当前屏保开关（1=开，0=关）。"""
    value = ctypes.c_int(0)
    try:
        ok = ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETSCREENSAVEACTIVE, 0, ctypes.byref(value), 0
        )
    except Exception:  # noqa: BLE001
        return None
    return value.value if ok else None


def _write_screensaver(active: int) -> None:
    try:
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETSCREENSAVEACTIVE,
            active,
            None,
            SPIF_UPDATEINIFILE | SPIF_SENDCHANGE,
        )
    except Exception:  # noqa: BLE001
        pass


VK_F24 = 0x87  # 虚拟功能键：原神/星铁/方舟和常见应用都不绑定
KEYEVENTF_KEYUP = 0x0002
_LEFT_SCAN = 0x00


def _nudge() -> None:
    """按一下 F24 并立即释放，重置系统空闲计时（防屏保/防锁屏）。

    为什么不是 Shift：原神里 Shift 是冲刺，任务执行时按会干扰脚本。
    为什么不是鼠标：用户的动态壁纸（Wallpaper Engine）跟随鼠标活动，微移会让它抖动。
    F24 既没有字符输出、也没有任何游戏绑定。
    """
    try:
        user32 = ctypes.windll.user32
        user32.keybd_event(VK_F24, _LEFT_SCAN, 0, 0)
        user32.keybd_event(VK_F24, _LEFT_SCAN, KEYEVENTF_KEYUP, 0)
    except Exception:  # noqa: BLE001
        pass


# 「现在有任务在跑吗」由上层注入：platform 层不该知道任务状态模型。
_busy_probe = lambda: False  # noqa: E731


def set_busy_probe(fn) -> None:
    """注册「是否忙」的判定函数（由 core 或 main 在启动时提供）。"""
    global _busy_probe
    _busy_probe = fn


def _task_running() -> bool:
    """有任务在跑时不人为按键——引擎本身就在模拟操作。"""
    try:
        return bool(_busy_probe())
    except Exception:  # noqa: BLE001
        return False


def _loop() -> None:
    while not _stop_event.is_set():
        _set_execution_state(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        )
        if not _task_running():
            _nudge()
        _stop_event.wait(_REFRESH_SECONDS)
    # 清掉持续请求，交还系统控制
    _set_execution_state(ES_CONTINUOUS)


def start() -> bool:
    """开始保持唤醒（幂等）。"""
    global _started, _original_screensaver, _thread
    with _lock:
        if _started:
            return True
        _original_screensaver = _read_screensaver()
        _write_screensaver(0)
        _stop_event.clear()
        _thread = threading.Thread(target=_loop, daemon=True, name="keep-awake")
        _thread.start()
        _started = True
    return True


def stop() -> None:
    """停止保持唤醒，并把屏保恢复成原值（幂等）。"""
    global _started, _thread, _original_screensaver
    with _lock:
        if not _started:
            return
        _stop_event.set()
        if _thread is not None:
            _thread.join(timeout=2)
            _thread = None
        if _original_screensaver is not None:
            _write_screensaver(_original_screensaver)
            _original_screensaver = None
        _started = False


def is_active() -> bool:
    return _started

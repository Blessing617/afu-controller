"""任务结束后的资源清理。

**统一规则（用户明确要求）：只要「停止」，就关闭所有相关进程，不再区分场景。**

背景（实测）：
- MuMu 跑完不会自己退出，12.8GB 提交内存一直占着，曾把整机压到只剩 2GB
- 星铁跑完游戏本体也不会退，一直占 2.7GB
- 早先的规则是「成功/失败才清理，用户停止不清理」，结果用户点了停止，
  游戏还在后台占着内存 —— 这不符合直觉，已废除。

现在只有一条：stop → 全关。
"""

from __future__ import annotations

import json
import subprocess
import time

from ..platform import proc
from ..core.config import load_config

# 每个游戏相关的进程（顺序即关闭顺序：先关游戏/工具，最后关模拟器）
PROCESSES = {
    # MuMu 会额外常驻一批后台组件：主程序关了它们还在（托盘图标、远程控制仍在），
    # 实测任务结束后仍有 4 个、约 140MB。MuMuRemoteService 是 Windows 服务，单独停。
    "arknights": [
        "MAA.exe",
        "MuMuNxMain.exe",
        "MuMuNxDevice.exe",
        "MuMuVMMHeadless.exe",
        "MuMuNxService.exe",
        "MuMuRemoteBackend.exe",
        "MumuRemoteHealthd.exe",
    ],
    "genshin": ["YuanShen.exe", "BetterGI.exe"],
    "starrail": ["StarRail.exe", "m7a.exe"],
}

# 全部游戏涉及的进程（停止整条链时用）
ALL_PROCESSES = [
    "m7a.exe", "StarRail.exe",
    "BetterGI.exe", "YuanShen.exe",
    "MAA.exe", "MuMuNxMain.exe", "MuMuNxDevice.exe", "MuMuVMMHeadless.exe",
    "MuMuNxService.exe", "MuMuRemoteBackend.exe", "MumuRemoteHealthd.exe",
]

# 模拟器要用它自己的命令优雅关闭，避免损坏虚拟机
MUMU_MANAGER = "mumu"


def _enum_processes() -> set[str]:
    """枚举系统里正在运行的进程名（小写，含 .exe）。

    主路径是 Win32 的 EnumProcesses + QueryFullProcessImageNameW：
    跨会话可见、不依赖外部命令与编码。

    但实测（2026-11-08）：**普通权限下它只枚举到 4 个进程**，
    连 explorer.exe 都看不到；管理员权限下是 141 个。也就是说程序一旦没拿到
    管理员权限，`_alive()` 会永远返回 False，清理会完全空转却毫无提示。
    所以补一条 PowerShell 兜底：枚举结果异常少时用另一条路再取一次。
    """
    names = _enum_via_api()
    if len(names) < 20:
        names |= _enum_via_powershell()
    return names


def _enum_via_powershell() -> set[str]:
    """兜底枚举（权限受限时用）。取不到就返回空集合，不影响主流程。"""
    out = _ps("Get-Process | Select-Object -ExpandProperty Name")
    return {
        (line.strip() + ".exe").lower()
        for line in out.splitlines()
        if line.strip()
    }


def _enum_via_api() -> set[str]:
    """Win32 EnumProcesses 版本。"""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    names: set[str] = set()

    arr = (wintypes.DWORD * 4096)()
    needed = wintypes.DWORD()
    if not psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(needed)):
        return names

    count = needed.value // ctypes.sizeof(wintypes.DWORD)
    buf = ctypes.create_unicode_buffer(1024)
    size = wintypes.DWORD(1024)

    for i in range(count):
        pid = arr[i]
        if pid == 0:
            continue
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            continue
        try:
            size.value = 1024
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                names.add(buf.value.rsplit("\\", 1)[-1].lower())
        finally:
            kernel32.CloseHandle(handle)
    return names


def _alive(image: str) -> bool:
    """某个进程是否在跑。"""
    return image.lower() in _enum_processes()


def _kill(image: str) -> bool:
    """强杀某个进程（按进程名，杀所有同名实例）。"""
    out = _ps(
        f"Get-Process -Name '{image.rsplit('.', 1)[0]}' -ErrorAction SilentlyContinue | "
        f"Stop-Process -Force -ErrorAction SilentlyContinue; 'done'"
    )
    if out != "" and not _alive(image):
        return True
    # PowerShell 不可用时的兜底：直接 taskkill
    try:
        proc.run(
            ["taskkill", "/F", "/IM", image],
            capture_output=True,
            timeout=15,
            stdin=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def _ps(script: str, timeout: int = 20) -> str:
    """跑一段 PowerShell，返回解码后的 stdout。"""
    try:
        r = proc.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
        raw = r.stdout or b""
        for enc in ("utf-8", "gbk"):
            try:
                return raw.decode(enc).strip()
            except Exception:
                continue
        return raw.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def _mumu_exe(mumu_path: str = "") -> str:
    """MuMuManager.exe 的路径：优先用手动配置，否则自动探测。"""
    if mumu_path:
        return mumu_path
    try:
        from ..platform.discovery import detect_all

        return (detect_all().get(MUMU_MANAGER) or {}).get("path", "")
    except Exception:  # noqa: BLE001
        return ""


def _mumu_instances_running(exe: str) -> bool:
    """还有模拟器实例在跑吗（虚拟手机是否还开着）。"""
    try:
        out = proc.run(
            [exe, "info", "-v", "all"],
            capture_output=True,
            timeout=20,
            stdin=subprocess.DEVNULL,
        )
        data = json.loads(out.stdout.decode("utf-8", errors="replace"))
        return any(
            bool(v.get("is_process_started") or v.get("is_android_started"))
            for v in data.values()
            if isinstance(v, dict)
        )
    except Exception:  # noqa: BLE001
        return False


def _shutdown_mumu(mumu_path: str = "", wait_seconds: float = 30.0) -> bool:
    """用 MuMu 自己的命令优雅关闭模拟器（直接杀会损坏虚拟机镜像）。

    两个必须注意的点：

    1. **`-v all`**：只写 `-v 0` 会漏掉别的实例（同一个 MuMu 可以有多个设备）。
    2. **shutdown 是异步的**：命令返回不代表已经关掉。原来固定 `sleep(6)` 然后去杀进程，
       实测经常赶在虚拟机退出之前，结果主程序没了、那个「虚拟手机」还开着。
       所以这里轮询实例状态，直到真的关掉或超时。
    """
    exe = _mumu_exe(mumu_path)
    if not exe:
        return False
    try:
        proc.run(
            [exe, "control", "-v", "all", "shutdown"],
            capture_output=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
    except Exception:  # noqa: BLE001
        return False

    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if not _mumu_instances_running(exe):
            return True
        time.sleep(1)
    return False


MUMU_REMOTE_SERVICE = "MuMuRemoteService"


def _stop_mumu_service() -> bool:
    """停掉 MuMu 的 Windows 服务。

    它不是普通进程，`Stop-Process` 杀不掉；而它活着就会把
    `MuMuRemoteBackend` / `MumuRemoteHealthd` 重新拉起来。
    必须先 `sc stop`，再清进程。需要管理员权限（本程序默认以管理员运行）。
    """
    try:
        out = proc.run(
            ["sc", "stop", MUMU_REMOTE_SERVICE],
            capture_output=True,
            timeout=25,
            stdin=subprocess.DEVNULL,
        )
        return out.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def cleanup(game: str, log=None) -> list[str]:
    """关闭某游戏相关的进程，返回实际关闭的进程名。"""
    if game not in PROCESSES:
        return []

    def note(msg: str) -> None:
        if log:
            try:
                log(msg)
            except Exception:
                pass

    killed: list[str] = []

    if game == "arknights":
        note("清理：关闭 MAA")
        if _alive("MAA.exe") and _kill("MAA.exe"):
            killed.append("MAA.exe")

        # 先停服务：否则它会把下面那些后台组件重新拉起来
        note("清理：停止 MuMu 远程服务")
        if _stop_mumu_service():
            killed.append(f"{MUMU_REMOTE_SERVICE}(服务)")

        note("清理：关闭 MuMu 模拟器")
        if _shutdown_mumu():
            note("模拟器已关闭")

        # 依次清掉：设备 → 虚拟机 → 主程序 → 后台组件
        for image in PROCESSES["arknights"]:
            if image == "MAA.exe":
                continue
            if _alive(image) and _kill(image):
                killed.append(image)
        return killed

    for image in PROCESSES[game]:
        if _alive(image):
            note(f"清理：关闭 {image}")
            if _kill(image):
                killed.append(image)
    return killed


def cleanup_all(log=None) -> list[str]:
    """关闭**所有**游戏与自动化工具进程。

    停止任务链 / 用户点停止时统一走这里：用户要的是「全停」，
    不希望还有哪个游戏在后台占着几个 G 的内存。
    """
    def note(msg: str) -> None:
        if log:
            try:
                log(msg)
            except Exception:
                pass

    killed: list[str] = []

    # 先停服务（它会拉起后台组件），再优雅关模拟器，最后清残留
    note("清理：停止 MuMu 远程服务")
    if _stop_mumu_service():
        killed.append(f"{MUMU_REMOTE_SERVICE}(服务)")

    note("清理：关闭 MuMu 模拟器")
    if _shutdown_mumu():
        note("模拟器已关闭")

    for image in ALL_PROCESSES:
        if _alive(image):
            note(f"清理：关闭 {image}")
            if _kill(image):
                killed.append(image)
    return killed


def auto_cleanup_enabled() -> bool:
    return bool(load_config().get("auto_cleanup", True))


def maybe_auto_cleanup(game: str, state: str, log=None) -> list[str]:
    """任务进入终态后清理（只清该游戏）。

    规则：不管成功、失败、超时还是用户停止，都清掉**这个游戏**的进程。
    早先是「用户停止不清理」，结果点了停止游戏还占着几个 G，与预期相反。
    注意这里只清单个游戏；整条链停止才用 cleanup_all()。
    """
    if not auto_cleanup_enabled():
        return []
    return cleanup(game, log)

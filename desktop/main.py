"""阿福代肝控制器 · 电脑端桌面应用

双击运行即可：
- 没有管理员权限时通过 UAC 自我重启（一次即可）
- 内置启动本地服务（uvicorn），不需要开命令行
- 显示：服务状态 / 手机连接地址 / 配对码 / 三个游戏的可用性
- 关闭窗口即停止服务，不残留进程

依赖：server/.venv 里的 fastapi + uvicorn（本文件用该虚拟环境的解释器运行）
"""

from __future__ import annotations

import ctypes
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))

APP_TITLE = "阿福代肝控制器"
MUTEX_NAME = "Global\\GameOrchestratorDesktop_v1"
# 首选端口。真正的端口由 config.resolve_port() 决定：被占用就自动往后找。
DEFAULT_PORT = 8765


def _dir_writable(path: Path) -> bool:
    """真写一个文件试试。只看 os.access 在 Windows 上不可靠
    （ACL 与只读属性会绕过它），所以实测。"""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:  # noqa: BLE001
        return False


def _resolve_data_dir(app_root: Path) -> tuple[Path, bool]:
    """决定数据目录。返回 (目录, 是否发生了降级)。

    规则：优先用程序自带的 data 目录（便携、换机器跟着走）。
    放只读位置（比如 Program Files）时退回用户目录，界面上会说明。
    """
    preferred = app_root / "data"
    if _dir_writable(preferred):
        return preferred, False
    # 降级目录用 ASCII 名：中文路径在部分第三方工具里会出乱码
    fallback = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "GameOrchestrator" / "data"
    _dir_writable(fallback)
    return fallback, True


if FROZEN:
    # 打包后：exe 所在目录就是「应用根目录」，数据默认也放这里
    ROOT = Path(sys.executable).resolve().parent
    DATA_DIR, DATA_DIR_FALLBACK = _resolve_data_dir(ROOT)
    os.environ.setdefault("ORCH_DATA_DIR", str(DATA_DIR))
else:
    ROOT = Path(__file__).resolve().parent.parent
    # 源码运行：数据就在 server/data，由 config.py 自己决定，
    # 这里**不能**设 ORCH_DATA_DIR，否则会和现有配置、配对凭据分家。
    DATA_DIR = ROOT / "server" / "data"
    DATA_DIR_FALLBACK = False

SERVER_DIR = ROOT / "server"
if not FROZEN:
    sys.path.insert(0, str(SERVER_DIR))

# --windowed 打包后 sys.stdout / sys.stderr 是 None，
# uvicorn 初始化 logging 时要往这里挂 handler，会直接卡死。
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="replace")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")


def log(msg: str) -> None:
    """打包后没有控制台，所有关键信息落到 data/app.log。"""
    try:
        from datetime import datetime

        path = DATA_DIR / "app.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")
    except Exception:
        pass


# ---------------- 管理员权限 ----------------
def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    """用 UAC 重新启动自己。返回值表示是否成功发出请求。"""
    script = Path(__file__).resolve()
    python = sys.executable
    pythonw = Path(python).with_name("pythonw.exe")
    if pythonw.is_file():
        python = str(pythonw)
    params = f'"{script}"'
    try:
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", python, params, str(script.parent), 1
        )
        return rc > 32
    except Exception:
        return False


# ---------------- 单实例 ----------------
def acquire_single_instance() -> bool:
    """True 表示拿到锁（第一个实例）。"""
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if not handle:
            return True
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return False
        return True
    except Exception:
        return True


# ---------------- 地址 ----------------
def local_addresses() -> list[str]:
    """返回本机可用于手机连接的地址，Tailscale（100.x）排前面。"""
    found: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip not in found and not ip.startswith("127."):
                found.append(ip)
    except Exception:
        pass

    # 兜底：枚举本机网卡（避免只拿到一个地址）
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in found and not ip.startswith("127."):
                found.append(ip)
    except Exception:
        pass

    def rank(ip: str) -> int:
        return 0 if ip.startswith("100.") else (1 if ip.startswith("192.168.") else 2)

    return sorted(found, key=rank)


# ---------------- 服务 ----------------
class ServiceHost:
    """在后台线程里跑 uvicorn，并与界面共享状态。"""

    def __init__(self) -> None:
        self.server = None
        self.thread = None
        self.error = ""
        self.external = False   # 端口已被另一个服务实例占用
        self.port = DEFAULT_PORT

    def start(self) -> bool:
        # 先算实际端口：首选端口被别的程序占着就自动换一个
        try:
            from app.core.config import resolve_port

            self.port = resolve_port()
        except Exception as exc:  # noqa: BLE001
            log(f"端口自适应失败，退回默认端口：{exc}")
            self.port = DEFAULT_PORT
        if self.port != DEFAULT_PORT:
            log(f"端口 {DEFAULT_PORT} 被占用，改用 {self.port}")

        # 端口上已经有**本应用**的服务在跑（比如上次启动的实例），直接复用
        if self._port_open():
            self.external = True
            return True
        try:
            log("导入 uvicorn…")
            import uvicorn
            log("导入 app.main…")
            from app.main import app  # server/app/main.py
            log("模块导入完成")
        except Exception as exc:  # noqa: BLE001
            import traceback

            self.error = f"导入服务失败：{exc}"
            log("导入 app.main 失败：\n" + traceback.format_exc())
            return False

        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=self.port,
            log_level="warning",
            access_log=False,
            log_config=None,      # 关键：不让 uvicorn 重建 logging（依赖 stdout）
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        log(f"启动 uvicorn 线程（0.0.0.0:{self.port}）…")
        self.thread.start()

        # 等端口就绪。线程提前死掉就别再傻等 15 秒——那样界面会一直停在「正在启动…」，
        # 用户和排查的人都看不出发生了什么（2026-11-08 就是这么踩的）。
        for _ in range(60):
            time.sleep(0.25)
            if self._port_open():
                log(f"服务已就绪（端口 {self.port}）")
                return True
            if self.error:
                break
            if not self.thread.is_alive():
                self.error = self.error or "服务线程已退出（详见 app.log）"
                break
        self.error = self.error or "服务启动超时（端口未就绪）"
        log(f"服务启动失败：{self.error}")
        return False

    def _serve(self) -> None:
        """跑 uvicorn。

        打包后没有控制台，后台线程里的 traceback 本来会直接消失——
        表现就是「界面一直显示正在启动…、日志里却什么都没有」。
        所以这里必须自己接住异常并留下原因。
        """
        try:
            self.server.run()
        except Exception as exc:  # noqa: BLE001
            import traceback

            self.error = f"服务启动失败：{exc}"
            log("服务启动异常：\n" + traceback.format_exc())

    def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
            time.sleep(0.8)

    def _port_open(self) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                return True
        except Exception:
            return False



# ---------------- 公网隧道 ----------------
def run_qt_window() -> None:
    """启动 Qt 界面。

    服务逻辑类（ServiceHost）保持原样复用，这里只负责把展示层换成 Qt。
    公网访问只有 Tailscale Funnel 一条路，不再自带 tunnel 进程。
    """
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError as exc:  # noqa: BLE001
        log(f"缺少 PySide6：{exc}")
        ctypes.windll.user32.MessageBoxW(
            None,
            f"缺少界面依赖 PySide6，请重新安装完整版本。\n\n{exc}",
            APP_TITLE,
            0x10,
        )
        return

    from qt_ui import MainWindow

    # 高 DPI 在 Qt6 默认开启，这里只补一个圆润的字体渲染
    QtWidgets.QApplication.setHighDpiScaleFactorRoundingPolicy(
        QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setOrganizationName("GameOrchestrator")

    # 标题字体随包分发；没注册成功会自动退回系统字体（theme.register_fonts 里处理）
    try:
        import theme

        theme.register_fonts(app)
    except Exception:  # noqa: BLE001
        pass

    # 任务栏图标用同一个 app 图标，避免显示成 python。
    # 优先用 .ico（Windows 会按 DPI 挑最合适的尺寸，比 SVG 渲染出来的锐），
    # 取不到再退回 SVG。
    icon_path = _find_assets(["icon.ico", "app-icon.svg"])
    if icon_path:
        app.setWindowIcon(QtGui.QIcon(str(icon_path)))

    host = ServiceHost()
    window = MainWindow(host, DATA_DIR, DATA_DIR_FALLBACK, DEFAULT_PORT)
    if icon_path:
        window.setWindowIcon(QtGui.QIcon(str(icon_path)))
    window.show()
    window.start_bootstrap()

    log("Qt 界面已启动")
    sys.exit(app.exec())


def cleanup_legacy_autostart() -> None:
    """删除早期版本注册的计划任务（它会开机弹 python 窗口）。

    只删除本应用自己的任务名，不动任何其他启动项。
    """
    try:
        out = subprocess.run(
            ["schtasks", "/delete", "/tn", "GameOrchestrator", "/f"],
            capture_output=True,
            timeout=15,
            stdin=subprocess.DEVNULL,
        )
        if out.returncode == 0:
            log("已删除旧的计划任务 GameOrchestrator")
    except Exception as exc:  # noqa: BLE001
        log(f"清理旧计划任务失败：{exc}")


def main() -> None:
    log("=== 应用启动 ===")
    if not acquire_single_instance():
        ctypes.windll.user32.MessageBoxW(
            None,
            "阿福代肝控制器已经在运行了。\n\n"
            "它没有关掉，只是窗口被最小化或在别的窗口后面。\n"
            "请按 Alt + Tab 切换过去，或看屏幕右下角托盘区（可能要点开 ^ 箭头）里的图标。\n\n"
            "如果你确实看不到它，可以打开任务管理器结束「阿福代肝控制器」进程后重新双击。",
            APP_TITLE,
            0x40,
        )
        return

    if is_admin():
        cleanup_legacy_autostart()

    skip_elevate = "--no-elevate" in sys.argv
    if not skip_elevate and not is_admin():
        if relaunch_as_admin():
            return  # 交给提权后的新实例
        ctypes.windll.user32.MessageBoxW(
            None,
            "需要管理员权限才能操作游戏（否则无法模拟键鼠）。\n请右键 → 以管理员身份运行。",
            APP_TITLE,
            0x30,
        )
        # 仍然允许以普通权限打开界面（只是任务可能失败）

    run_qt_window()


def _find_asset(name: str) -> Path | None:
    """找资源文件：源码运行找项目根，打包后找 _internal。"""
    base = Path(getattr(sys, "_MEIPASS", "")) if getattr(sys, "_MEIPASS", "") else None
    candidates = [
        ROOT / "assets" / "icons" / name,
        ROOT / "desktop" / name,
        Path(__file__).resolve().parent.parent / "assets" / "icons" / name,
        Path(__file__).resolve().parent / name,
    ]
    if base:
        candidates.insert(0, Path(base) / "assets" / "icons" / name)
        candidates.insert(1, Path(base) / name)
    for path in candidates:
        if path.is_file():
            return path
    return None


def _find_assets(names: list[str]) -> Path | None:
    """按顺序找第一个存在的资源。"""
    for name in names:
        hit = _find_asset(name)
        if hit is not None:
            return hit
    return None


if __name__ == "__main__":
    main()

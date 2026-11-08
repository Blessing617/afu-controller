"""电脑端后台数据采集：把「会卡住界面」的活全部挪出界面线程。

为什么需要这个模块
------------------
早先的 `qt_ui._poll_status()` 每 2 秒在**界面线程**上同步执行两件事：

1. `subprocess.run(["tailscale", "status", "--json"])` 和
   `subprocess.run(["tailscale", "funnel", "status"])`，每次超时上限 10 秒；
2. `socket.getaddrinfo()` + `gethostbyname_ex()` 枚举本机地址。

Tailscale 没装、没登录、或者要等 UAC 的时候，这两步会把界面线程整段堵住，
表现就是「窗口拖不动、按钮点不动」。这里把同样的事情放到一个常驻后台线程里，
按固定节拍采一次快照，再用信号把**数据**送回界面线程渲染。

设计取舍
--------
- 一个线程 + `threading.Event.wait(interval)` 做节拍就够，不引入线程池 / asyncio：
  只有一个周期任务，越简单越好排查。
- 快照是 `dataclass(frozen=True)`，界面侧用 `==` 比较即可判断「有没有变化」，
  数据没变就一行都不重绘。
- Tailscale 相关查询用「失败快照」缓存一段时间（`TAILSCALE_ERROR_BACKOFF`）：
  没装 Tailscale 时不必每 2 秒都去 `shutil.which` 白跑一趟。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

# 采集节拍（秒）。连接状态要求 15 秒内反映，5 秒留了三倍余量，
# 同时把空闲时的子进程调用次数降到原来的 40%（每次都要起 tailscale 查询）。
POLL_INTERVAL = 5.0

# 一次 tailscale 调用最多等多久。放短一点：界面反正不等它，但后台线程不该
# 被一个卡死的子进程拖住太久。
_TAILSCALE_TIMEOUT = 6

# 失败后多久再试一次 Tailscale（秒）。没装的时候没必要每轮都查。
TAILSCALE_ERROR_BACKOFF = 30.0

_NO_WINDOW = 0x08000000


# ---------------------------------------------------------------- 数据结构
@dataclass(frozen=True)
class AddressEntry:
    """一条可填到手机上的地址。"""

    address: str
    port: int
    kind: str  # tailscale / lan / other

    @property
    def text(self) -> str:
        return f"{self.address}:{self.port}"


@dataclass(frozen=True)
class TailscaleState:
    """「公网固定地址」这件事走到哪一步了。"""

    installed: bool = False
    logged_in: bool = False
    funnel_on: bool = False
    url: str = ""
    port: int = 0
    no_permission: bool = False


@dataclass(frozen=True)
class ConnectionSnapshot:
    """界面需要渲染的全部连接信息，一次性打包好。"""

    addresses: tuple[AddressEntry, ...] = ()
    tailscale: TailscaleState = field(default_factory=TailscaleState)
    pairing_code: str = ""
    paired: bool = False
    # 推荐给用户的地址：优先公网固定域名，其次局域网
    primary: str = ""
    primary_hint: str = ""


# ---------------------------------------------------------------- 采集器
class ConnectionCollector:
    """在后台线程里周期性地采集连接信息。

    用法：

        collector = ConnectionCollector(hwnd_owner, port, data_dir)
        collector.sig_snapshot.connect(window.apply_snapshot)
        collector.start()
        ...
        collector.stop()

    信号是延迟注入的（`attach_signal`）：本模块不 import PySide6，
    这样在没有 Qt 的环境（例如单元测试）里也能单独跑采集逻辑。
    """

    def __init__(self, port: int, data_dir: Path) -> None:
        self._port = port
        self._data_dir = Path(data_dir)
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_snapshot = ConnectionSnapshot()
        self._emit = None  # 由 attach_emitter 注入，签名为 Callable[[ConnectionSnapshot], None]

        # Tailscale 查询的退避状态
        self._ts_cached = TailscaleState()
        self._ts_retry_at = 0.0
        self._clock = 0.0

    # ---- 生命周期 ----
    def attach_emitter(self, emit) -> None:
        """注入「把快照交给界面」的回调（一般是 Qt 信号的 emit）。"""
        self._emit = emit

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._loop, name="conn-collector", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def refresh_now(self) -> None:
        """让下一轮采集立刻发生（用户点了「换一个配对码」之类）。"""
        self._wake.set()

    # ---- 主循环 ----
    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                snap = self.collect()
            except Exception:  # noqa: BLE001 —— 采集失败绝不能让线程死掉
                snap = self._last_snapshot
            if snap != self._last_snapshot:
                self._last_snapshot = snap
                if self._emit is not None:
                    try:
                        self._emit(snap)
                    except Exception:  # noqa: BLE001
                        pass
            self._wake.wait(POLL_INTERVAL)
            self._wake.clear()

    # ---- 采集 ----
    def collect(self) -> ConnectionSnapshot:
        self._clock += POLL_INTERVAL
        addresses = tuple(_local_addresses(self._port))
        ts = self._tailscale_state()
        code, paired = self._pairing_code()

        primary, hint = _pick_primary(addresses, ts)
        return ConnectionSnapshot(
            addresses=addresses,
            tailscale=ts,
            pairing_code=code,
            paired=paired,
            primary=primary,
            primary_hint=hint,
        )

    def _tailscale_state(self) -> TailscaleState:
        """查 Tailscale 的四步状态；失败时退避，避免每轮都白跑。"""
        import time

        if time.monotonic() < self._ts_retry_at:
            return self._ts_cached
        state = query_tailscale(self._port)
        self._ts_cached = state
        # 没装 / 没权限时不值得每 2 秒重试
        if not state.installed or state.no_permission:
            self._ts_retry_at = time.monotonic() + TAILSCALE_ERROR_BACKOFF
        else:
            self._ts_retry_at = 0.0
        return state

    def _pairing_code(self) -> tuple[str, bool]:
        path = self._data_dir / "pairing_code.txt"
        try:
            if not path.is_file():
                return "", True
            lines = path.read_text(encoding="utf-8").splitlines()
            return (lines[0].strip() if lines else ""), False
        except Exception:  # noqa: BLE001
            return "", False


# ---------------------------------------------------------------- 纯函数
def _local_addresses(port: int) -> list[AddressEntry]:
    """枚举本机可用于手机连接的地址，Tailscale → 局域网 → 其它。"""
    import socket

    found: list[str] = []

    def add(ip: str) -> None:
        if ip and not ip.startswith("127.") and ip not in found:
            found.append(ip)

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            add(info[4][0])
    except Exception:  # noqa: BLE001
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            add(ip)
    except Exception:  # noqa: BLE001
        pass

    def kind_of(ip: str) -> str:
        if ip.startswith("100."):
            return "tailscale"
        if ip.startswith(("192.168.", "10.")) or re.match(r"^172\.(1[6-9]|2\d|3[01])\.", ip):
            return "lan"
        return "other"

    rank = {"tailscale": 0, "lan": 1, "other": 2}
    entries = [AddressEntry(ip, port, kind_of(ip)) for ip in found]
    entries.sort(key=lambda e: rank[e.kind])
    return entries


def _pick_primary(
    addresses: tuple[AddressEntry, ...], ts: TailscaleState
) -> tuple[str, str]:
    """推荐给用户填哪个地址，以及一句说明。

    优先 Funnel 的固定域名（出门在家都能用、手机不用装东西），
    其次局域网地址（只在家能用）。Tailscale 的 100.x 不是首选，
    因为它要求手机也装 Tailscale。
    """
    if ts.url:
        return ts.url, "这是公网固定地址，出门在外也能用，手机不用装任何软件。复制后填到 APP 里。"
    lan = next((a for a in addresses if a.kind == "lan"), None)
    if lan is not None:
        return (
            lan.text,
            "这是局域网地址，只有手机和电脑连同一个 WiFi 时能用。"
            "想在出门时也能连，看下面「公网固定地址」这张卡片怎么开启。",
        )
    if addresses:
        return (
            addresses[0].text,
            "暂时只找到这一个地址；如果手机连不上，去下面「公网固定地址」看看怎么开。",
        )
    return "", ""


def _tailscale_exe() -> str | None:
    exe = shutil.which("tailscale") or shutil.which("tailscale.exe")
    if exe:
        return exe
    if sys.platform == "win32":
        for cand in (
            Path("C:/Program Files/Tailscale/tailscale.exe"),
            Path("C:/Program Files (x86)/Tailscale/tailscale.exe"),
        ):
            if cand.is_file():
                return str(cand)
    return None


def query_tailscale(port: int) -> TailscaleState:
    """摸清「公网固定地址」这件事走到哪一步了。

    地址不是本程序生成的，是用户做完下面几步后 Tailscale 给的：

      ① 注册账号（浏览器，用户自己）
      ② 电脑安装 Tailscale          ← 可检测
      ③ 登录同一账号（浏览器授权）    ← 可检测
      ④ 开启 Funnel（浏览器授权一次） ← 可检测
      ⑤ 地址才出现                   ← 可读取

    **注意：这个函数会起子进程、可能阻塞数秒，只能在后台线程里调用。**
    """
    out = TailscaleState()
    exe = _tailscale_exe()
    if not exe:
        return out
    out = TailscaleState(installed=True)

    def run(args: list[str]) -> tuple[int, str]:
        try:
            r = subprocess.run(
                [exe] + args,
                capture_output=True,
                text=True,
                timeout=_TAILSCALE_TIMEOUT,
                stdin=subprocess.DEVNULL,
                creationflags=_NO_WINDOW if sys.platform == "win32" else 0,
            )
            return r.returncode, (r.stdout or "") + (r.stderr or "")
        except Exception:  # noqa: BLE001
            return -1, ""

    logged_in = False
    url = ""
    no_permission = False

    # ② 登录状态 + ⑤ 域名（同一条命令）
    rc, text = run(["status", "--json"])
    if rc == 0 and text.strip().startswith("{"):
        try:
            data = json.loads(text)
            logged_in = data.get("BackendState") == "Running"
            dns = str((data.get("Self") or {}).get("DNSName") or "").rstrip(".")
            if dns.endswith(".ts.net"):
                url = f"https://{dns}"
        except Exception:  # noqa: BLE001
            pass
    elif "access is denied" in text.lower():
        no_permission = True

    # ④ Funnel 是否开启
    funnel_on = False
    funnel_port = 0
    fro, ftext = run(["funnel", "status"])
    if "access is denied" in ftext.lower():
        no_permission = True
    elif "Funnel on" in ftext:
        funnel_on = True
        m = re.search(r"https://([a-z0-9][a-z0-9.-]*\.ts\.net)", ftext, re.I)
        if m:
            url = f"https://{m.group(1)}"
        p = re.search(r"proxy\s+http://127\.0\.0\.1:(\d+)", ftext)
        if p:
            funnel_port = int(p.group(1))

    return TailscaleState(
        installed=True,
        logged_in=logged_in,
        funnel_on=funnel_on,
        url=url,
        port=funnel_port,
        no_permission=no_permission,
    )


def cached_public_url() -> str:
    """读配置里缓存的公网域名（没有管理员权限时的兜底显示）。"""
    try:
        from app.core.config import load_config

        return str(load_config().get("public_url") or "")
    except Exception:  # noqa: BLE001
        return ""

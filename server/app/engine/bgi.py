"""BetterGI（原神）适配器。

已验证的要点：
- 必须管理员权限（游戏以管理员启动，否则无法模拟点击）
- 重跑前必须结束残留的 BetterGI 进程：已在运行的实例不会因为再次
  `--startOneDragon` 而重跑一条龙（新进程只把命令转给旧实例）
- 窗口必须在前台，否则 BGI 一直判定「不在游戏主界面」
- 没有退出码语义，完成判定靠日志

完成标志（实测，2026-11-06 / 11-08）
------------------------------------
BetterGI 一条龙跑完打印的是 **「一条龙和配置组任务结束」**
（`OneDragonFlowViewModel`）。早先代码等的是 `一条龙.*完成` 与
`正在关闭游戏和软件`，两个都匹配不上——结果是每次跑完都被判成
「退出但未检测到完成标志」。这里保留后者作为兼容，主力判据换成前者。

判定只看**本次运行**读到的日志（`LogStream` 从启动时的字节偏移开始），
绝不用「最近 N 行」那种会跨运行取到上一次内容的窗口。
"""

from __future__ import annotations

import subprocess
import time
from datetime import date
from pathlib import Path

from ..core.logstream import LogStream
from ..core.progress import bettergi_progress
from ..core.stall import OK, StallWatch
from ..core.state import TaskRun, TaskRunner, TaskState
from ..core.supervisor import PollResult, supervise
from ..platform import proc
from ..platform.window import activate
from .bgi_probe import describe as describe_probe

TASK_TITLE = "原神·一条龙"
# 进程存活检测：每次都要起一个 tasklist 子进程，没必要太频繁
ALIVE_CHECK_SECONDS = 15
# 兜底上限（真正的判据是进展，这个只防「一直有日志却永不结束」）
HARD_CAP_SECONDS = 6 * 3600


def _today_log(exe: Path) -> Path:
    return exe.parent / "log" / f"better-genshin-impact{date.today():%Y%m%d}.log"


def _kill_bgi() -> bool:
    try:
        out = proc.run(
            ["taskkill", "/F", "/IM", "BetterGI.exe"],
            capture_output=True,
            timeout=20,
            stdin=subprocess.DEVNULL,
        )
        return out.returncode == 0
    except Exception:
        return False


def _bgi_alive() -> bool:
    try:
        out = proc.run(
            ["tasklist", "/FI", "IMAGENAME eq BetterGI.exe"],
            capture_output=True,
            timeout=8,
            stdin=subprocess.DEVNULL,
        )
        return b"BetterGI.exe" in out.stdout
    except Exception:
        return False


class BgiSession:
    """一次「一条龙」的会话。"""

    def __init__(self, exe: Path) -> None:
        self.exe = Path(exe)
        self._stream: LogStream | None = None
        self._stall = StallWatch()
        self._started = 0.0
        self._next_alive = 0.0
        self._alive = True
        self._start_notes: list[str] = []

    def start(self) -> None:
        if not self.exe.is_file():
            raise RuntimeError(f"未找到 BetterGI.exe：{self.exe}")

        # 结束残留实例（否则新实例只会转发命令、不重跑）
        if _bgi_alive():
            _kill_bgi()
            time.sleep(2)

        moved = activate("YuanShen.exe")
        self._note("原神窗口已前置" if moved else "原神当前未运行，将由 BetterGI 自行启动")

        # 新版 BetterGI 有对外健康接口；没有就说明按日志判断（这句话对排查很重要）
        self._note(describe_probe(self.exe))

        self._stream = LogStream(_today_log(self.exe))
        proc.spawn([str(self.exe), "--startOneDragon"], cwd=str(self.exe.parent))
        self._stall.progress()
        self._started = time.monotonic()
        self._next_alive = self._started + ALIVE_CHECK_SECONDS
        self._alive = True

    def _note(self, line: str) -> None:
        """启动阶段的说明：可能不止一条，攒起来一次性交给任务日志。"""
        self._start_notes.append(line)

    def poll(self) -> PollResult:
        if self._stream is None:
            return PollResult("failed", note="会话未启动")

        result = PollResult()
        # 跨零点时日志换文件，换一条流继续读
        current = _today_log(self.exe)
        if current != self._stream.path:
            self._stream = LogStream(current, from_start=True)

        lines = self._stream.read_new()
        result.lines = lines
        if lines:
            self._stall.progress()

        progress = bettergi_progress(self._stream.tail)
        result.markers = dict(progress.markers)

        if progress.terminal == "success":
            result.state = "success"
            result.note = progress.note
            return result
        if progress.terminal == "failed":
            result.state = "failed"
            result.note = progress.note or "BetterGI 进程级崩溃"
            return result

        now = time.monotonic()
        if now >= self._next_alive:
            self._alive = _bgi_alive()
            self._next_alive = now + ALIVE_CHECK_SECONDS

        if not self._alive:
            # 进程退出：只认本次运行读到的日志
            if progress.terminal == "success":
                result.state = "success"
                result.note = "BetterGI 已退出，本次日志里有完成标志"
            else:
                result.state = "failed"
                result.note = "BetterGI 退出但本次运行没有完成标志（可能中途失败，详见日志）"
            return result

        if now - self._started >= HARD_CAP_SECONDS:
            result.state = "timeout"
            result.note = f"运行超过 {HARD_CAP_SECONDS // 3600} 小时仍未结束"
            return result

        if self._stall.verdict() != OK:
            result.state = "stuck"
            result.note = self._stall.reason()
            return result

        return result

    def stop(self, reason: str = "") -> None:
        # BetterGI 没有停止命令，只能结束进程
        _kill_bgi()

    @property
    def start_notes(self) -> list[str]:
        return list(getattr(self, "_start_notes", []))


def run_onedragon(runner: TaskRunner, run: TaskRun, exe: Path) -> TaskState:
    session = BgiSession(exe)
    try:
        session.start()
    except Exception as exc:  # noqa: BLE001
        runner.finish(run, TaskState.FAILED, error=f"启动失败：{exc}")
        return TaskState.FAILED

    for note in session.start_notes:
        runner.append_log(run, note)
    runner.append_log(run, f"$ BetterGI.exe --startOneDragon")

    return supervise(runner, run, session)

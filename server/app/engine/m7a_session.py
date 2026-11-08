"""星铁（三月七小助手）的任务会话：启动、轮询、停止。

为什么不再用 `subprocess.run(capture_output=True, timeout=...)`
--------------------------------------------------------------
2026-11-08 那次实测：引擎 22 分钟就跑完了，我们的任务却挂了 4 小时。
原因是管道句柄被引擎派生的进程（它启动的 `StarRail.exe`）继承，父进程退出后管道不 EOF，
`timeout` 到期 kill 掉父进程后，Windows 上随后的 `communicate()` 没有超时保护，
只能等到那个孙进程退出。**任务结不结束绝不能挂在管道上。**

所以这里改成：
- 启动用 `--detach`，输出重定向到**临时文件**（不是管道），自己实现超时
- 结束判定只看 `logs/runs/<run_id>.json`
- 日志用 `LogStream` 增量读文件
- 停止用官方的 `--control <run_id> stop`

三条回退路径都只读文件或执行短命命令，任何一条都不会让我们的线程被句柄拖住。
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

from ..core.logstream import LogStream
from ..core.progress import starrail_progress
from ..core.stall import StallWatch, OK
from ..core.supervisor import PollResult

CREATE_NO_WINDOW = 0x08000000
# detach 应该秒回。给 3 分钟是留给 UAC 弹窗（用户可能不在电脑前，但也别无限等）
LAUNCH_TIMEOUT = 180
# --status 这种只读命令
STATUS_TIMEOUT = 25
# 停止指令
CONTROL_TIMEOUT = 30
# 等新运行记录出现的时间
RECORD_WAIT = 20

RUN_ID_RE = re.compile(r"\d{8}-\d{6}-[0-9a-f]{4}")

# 轮询结果里的终态取值。None 表示还在跑。
STATE_SUCCESS = "success"
STATE_FAILED = "failed"
STATE_STOPPED = "stopped"
STATE_STUCK = "stuck"


def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def run_and_capture(cmd: list[str], *, cwd: str | Path | None, timeout: float) -> tuple[int, str]:
    """执行一个短命命令并把输出接进**临时文件**。

    注意：这里刻意不用 `subprocess.run(capture_output=True, timeout=...)`。
    Windows 上如果被启动的进程又派生了常驻子进程，管道句柄会被继承，
    `timeout` 就不是真正的上限了（复现见 tests/test_task_lifecycle.py）。
    临时文件没有这个问题：随时可以读，不依赖对方关闭句柄。
    """
    with tempfile.TemporaryFile() as out:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=out,
            creationflags=CREATE_NO_WINDOW,
        )
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
            raise TimeoutError(f"{Path(cmd[0]).name} 超过 {int(timeout)} 秒未返回")
        out.seek(0)
        return code, _decode(out.read())


def _json_tail(text: str) -> dict:
    """从输出里抠出最后一个 JSON 对象（容忍前面混着别的行）。"""
    text = text.strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(text[start : end + 1])
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class M7aSession:
    """一次 m7a 任务的完整生命周期。一个实例只跑一个 task id。"""

    def __init__(self, exe: Path, task_id: str, *, stall: StallWatch | None = None) -> None:
        self.exe = Path(exe)
        self.task_id = task_id
        self.runs_dir = self.exe.parent / "logs" / "runs"
        self.run_id = ""
        self._log: LogStream | None = None
        self._stall = stall or StallWatch()
        self._record_seen = False

    # ---------------- 启动 ----------------
    def start(self) -> str:
        """启动任务并拿到 run_id。

        **不能等进程退出**：实测（2026-11-08 09:38）`--detach` 的启动器进程会一直
        守着任务、直到任务结束才退出。原先用 `proc.wait(180)` 等它，结果：
        任务其实已经在跑（run 记录都写出来了），我们却判「启动超时」并把它 kill 掉，
        整个任务被腰斩，run 记录停在 `running`。

        所以这里启动后只等**运行记录出现**，一出现就算启动成功，进程让它自己待着。
        """
        if not self.exe.is_file():
            raise RuntimeError(f"未找到 m7a.exe：{self.exe}")

        before = self._record_names()
        cmd = [str(self.exe), self.task_id, "--after-finish", "None", "--detach", "--json"]
        try:
            proc_obj = subprocess.Popen(
                cmd,
                cwd=str(self.exe.parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
            )
        except OSError as exc:
            raise RuntimeError(f"启动三月七失败：{exc}") from None

        deadline = time.monotonic() + LAUNCH_TIMEOUT
        run_id = ""
        while time.monotonic() < deadline:
            time.sleep(1)
            new = self._record_names() - before
            if new:
                run_id = sorted(new)[-1]
                break
            if proc_obj.poll() is not None:
                # 进程退了却没留下记录：再等一拍，然后按失败处理
                time.sleep(2)
                new = self._record_names() - before
                if new:
                    run_id = sorted(new)[-1]
                break

        if not run_id:
            active = self._active_run_from_status()
            # 如果 active 指向的是启动前就存在的记录，那是上一次的残留，不能当本次
            if active and active not in before:
                run_id = active

        if not run_id:
            code = proc_obj.poll()
            if proc_obj.poll() is None:
                proc_obj.kill()
            if code is not None and code != 0:
                raise RuntimeError(
                    f"三月七启动失败（退出码 {code}）：多半是已经有一个任务在跑"
                )
            raise RuntimeError(
                f"等待三月七启动超过 {LAUNCH_TIMEOUT // 60} 分钟"
                "（可能卡在 UAC 授权窗口，或者任务没能进入运行状态）"
            )

        self.attach(run_id)
        return run_id

    def attach(self, run_id: str) -> None:
        """绑定一个已知的 run_id（正常流程由 start 调用，回退路径也用它）。"""
        self.run_id = run_id
        self._log = LogStream(self.runs_dir / f"{run_id}.log", from_start=True)
        self._stall.progress()   # 启动成功本身算一次进展

    def _record_names(self) -> set[str]:
        if not self.runs_dir.is_dir():
            return set()
        return {p.stem for p in self.runs_dir.glob("*.json")}

    @staticmethod
    def _parse_run_id(text: str) -> str:
        data = _json_tail(text)
        for key in ("run_id", "runId", "id"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        m = RUN_ID_RE.search(text)
        return m.group(0) if m else ""

    def _wait_new_record(self, before: set[str]) -> str:
        deadline = time.monotonic() + RECORD_WAIT
        while time.monotonic() < deadline:
            new = self._record_names() - before
            if new:
                return sorted(new)[-1]
            time.sleep(1)
        return ""

    def _active_run_from_status(self) -> str:
        try:
            _code, text = run_and_capture(
                [str(self.exe), "--status", "--json"], cwd=self.exe.parent, timeout=STATUS_TIMEOUT
            )
        except Exception:
            return ""
        return self._parse_active_run(text)

    @staticmethod
    def _parse_active_run(text: str) -> str:
        """从 `--status --json` 的输出里取 active_run.run_id。"""
        active = _json_tail(text).get("active_run")
        if isinstance(active, dict):
            return str(active.get("run_id") or "")
        return ""

    # ---------------- 轮询 ----------------
    def poll(self) -> PollResult:
        result = PollResult()

        if self._log is not None:
            lines = self._log.read_new()
            result.lines = lines
            if lines:
                self._stall.progress()
            result.markers = starrail_progress(self._log.tail).markers

        record = self.read_record()
        if record is not None:
            if not self._record_seen:
                self._record_seen = True
                self._stall.progress()
            result.state, result.note = self._judge(record)
            return result

        verdict = self._stall.verdict()
        if verdict != OK:
            result.state = STATE_STUCK
            result.note = self._stall.reason()
        return result

    def read_record(self) -> dict | None:
        """读本次运行的记录；还没写出来时返回 None。"""
        if not self.run_id:
            return None
        path = self.runs_dir / f"{self.run_id}.json"
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _judge(record: dict) -> tuple[str | None, str]:
        """把运行记录翻译成终态。返回 None 表示**还在跑**。

        注意这里最容易错的一步：`status` 是 `running`（或者还没有状态）时
        绝不能当成功。2026-11-08 09:49 的故障就是——读到一条旧的 `running` 记录，
        兜底 return success，于是「链 2 秒就宣告成功」，互斥也跟着失效了。
        """
        status = str(record.get("status") or "").lower()
        code = record.get("exit_code")
        error = str(record.get("error") or "")

        if status == "stopped" or code == 6:
            return STATE_STOPPED, error or "任务被停止"
        if status in ("aborted", "cancelled", "canceled"):
            # 引擎记录到「运行被异常中止」（进程被外力结束时会这样），
            # 这不是成功，也不能一直等下去
            return STATE_FAILED, error or "任务被中止（运行进程被结束）"
        if status in ("failed", "error"):
            return STATE_FAILED, error or f"引擎报告失败（status={status}）"
        if status == "success" or code == 0:
            return STATE_SUCCESS, ""
        if isinstance(code, int) and code != 0:
            return STATE_FAILED, error or f"退出码 {code}"
        # running / queued / 空状态：还在跑，交给 StallWatch 判断是否卡死
        return None, ""

    # ---------------- 停止 ----------------
    def stop(self, reason: str = "") -> None:
        if not self.run_id:
            return
        try:
            run_and_capture(
                [str(self.exe), "--control", self.run_id, "stop"],
                cwd=self.exe.parent,
                timeout=CONTROL_TIMEOUT,
            )
        except Exception:
            # 停止指令发不出去时由上层决定是否强杀，这里不抛
            pass

    # ---------------- 辅助 ----------------
    @property
    def tail(self) -> list[str]:
        return self._log.tail if self._log else []

    def stall_snapshot(self) -> dict:
        return self._stall.snapshot().to_dict()

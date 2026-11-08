"""定时调度：到点自动「重置环境 → 从头跑整条链」。

为什么触发前要先重置
--------------------
用户的要求是「到点强制重置，全部软件进程关掉，然后从头开始」。这不是洁癖：
残留的游戏与模拟器会抢前台键鼠、占掉十几 GB 内存，不清理直接跑，
下一个引擎大概率起不来（2026-11-08 就出过 `OpenCV Insufficient memory`）。

代价是会关掉用户正在玩的游戏——这一点写在编排页的定时卡片上，开定时即视为接受。
"""

from __future__ import annotations

import threading
import time
from datetime import datetime

from .schedule import Schedule, load_schedule, save_schedule

# 检查节拍：分钟级精度足够，20 秒也不至于空转
TICK_SECONDS = 20.0
# 等正在跑的链收敛的上限
STOP_WAIT_SECONDS = 60.0
# 最近触发记录保留多少条
KEEP_RUNS = 20

# 最近触发记录（内存，服务重启即清空）：给接口展示「上次定时跑得怎么样」
RECENT_RUNS: list[dict] = []


def record_run(slot: str, *, killed: list[str], error: str = "") -> None:
    RECENT_RUNS.append(
        {
            "slot": slot,
            "at": datetime.now().isoformat(timespec="seconds"),
            "killed": list(killed),
            "error": error,
        }
    )
    del RECENT_RUNS[:-KEEP_RUNS]


def recent_runs() -> list[dict]:
    return list(RECENT_RUNS[-KEEP_RUNS:])


def reset_environment() -> tuple[list[str], str]:
    """停掉正在跑的链与任务，关闭所有游戏/工具进程。返回 (关闭的进程, 错误说明)。

    抽成独立函数是为了让「调度」和「具体怎么停」分开：
    调度只关心「到点该重置了」，不关心 MuMu 有几个进程。
    """
    from . import tasks as core_tasks
    from .orchestrator import ORCH
    from .state import RUNNER
    from ..engine.cleanup import cleanup_all

    error = ""

    # 1) 正在跑的链：请求停止并等它收敛
    if ORCH.is_running():
        ORCH.request_stop()
        deadline = time.monotonic() + STOP_WAIT_SECONDS
        while time.monotonic() < deadline and ORCH.is_running():
            time.sleep(0.5)

    # 2) 单步任务（若有）
    if RUNNER.current() is not None:
        try:
            core_tasks.stop_current()
        except LookupError:
            pass
        except Exception as exc:  # noqa: BLE001
            error = f"停止当前任务失败：{exc}"

    # 3) 关掉所有游戏与自动化工具
    try:
        killed = cleanup_all()
    except Exception as exc:  # noqa: BLE001
        killed = []
        error = (error + "；" if error else "") + f"清理进程失败：{exc}"

    return killed, error


def fire_chain(slot: str) -> dict:
    """到点动作：重置 → 启动整条链。返回一份可展示的结果。"""
    from .chain import load_chain
    from .orchestrator import ORCH

    killed, error = reset_environment()

    chain = load_chain()
    if chain.is_empty_for_run():
        record_run(slot, killed=killed, error="没有可执行的步骤，已跳过")
        return {"started": False, "reason": "没有可执行的步骤", "killed": killed}

    if ORCH.is_running():
        # 重置没能把链停下来（极端情况），不要再叠一条
        record_run(slot, killed=killed, error="上一条链仍未结束，本次跳过")
        return {"started": False, "reason": "上一条链仍未结束", "killed": killed}

    try:
        ORCH.start(chain)
    except RuntimeError as exc:
        record_run(slot, killed=killed, error=str(exc))
        return {"started": False, "reason": str(exc), "killed": killed}

    record_run(slot, killed=killed, error=error)
    return {"started": True, "reason": "", "killed": killed}


class Scheduler:
    """每 TICK_SECONDS 检查一次时间点。"""

    def __init__(
        self,
        *,
        tick: float = TICK_SECONDS,
        fire=fire_chain,
        load=load_schedule,
        save=save_schedule,
    ) -> None:
        self.tick = tick
        self._fire = fire
        self._load = load
        self._save = save
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    # ---------- 生命周期 ----------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="scheduler")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ---------- 检查 ----------
    def tick_once(self, now: datetime | None = None) -> list[str]:
        """检查一次，返回本次触发的时间点。抽出来是为了能单测。"""
        now = now or datetime.now()
        with self._lock:
            schedule = self._load()
            slots = schedule.due_slots(now)
            if not slots:
                return []
            fired: list[str] = []
            for slot in slots:
                # **先记 fired 再触发**：避免触发失败后同一分钟反复重试
                schedule.mark_fired(now, slot)
                self._save(schedule)
                try:
                    self._fire(slot)
                except Exception as exc:  # noqa: BLE001
                    record_run(slot, killed=[], error=f"触发异常：{exc}")
                fired.append(slot)
            return fired

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick_once()
            except Exception:  # noqa: BLE001 —— 调度线程不能因为一次异常就死
                pass
            self._stop.wait(self.tick)


SCHEDULER = Scheduler()

"""定时执行的接口。

- `GET  /api/schedule`         当前配置 + 下次运行时间 + 最近触发记录
- `PUT  /api/schedule`         保存配置（整份替换，自动备份）
- `POST /api/schedule/stop`    强制停止：停链 → 停任务 → 关掉所有游戏与工具

「关掉定时」本身只是 `PUT` 一个 `enabled: false`；如果那一刻正在跑，
手机端会额外调 `stop`，把电脑上正在跑的东西一起收掉。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException

from ..core.schedule import Schedule, ScheduleError, load_schedule, save_schedule
from ..core.scheduler import SCHEDULER, recent_runs, reset_environment

router = APIRouter(tags=["schedule"])


def _snapshot() -> dict:
    schedule = load_schedule()
    now = datetime.now()
    return {
        "enabled": schedule.enabled,
        "times": list(schedule.times),
        "weekdays": list(schedule.weekdays),
        "next_run": schedule.next_run(now),
        "scheduler_running": SCHEDULER.running,
        "last_runs": recent_runs(),
    }


@router.get("/api/schedule")
def get_schedule() -> dict:
    return _snapshot()


@router.put("/api/schedule")
def put_schedule(payload: dict) -> dict:
    try:
        schedule = Schedule.from_dict(payload)
    except ScheduleError as exc:
        raise HTTPException(
            status_code=400, detail={"error": "invalid_schedule", "message": str(exc)}
        ) from None

    # 保留已有的触发去重记录：改时间点不该让「今天已经跑过」失效
    previous = load_schedule()
    schedule.last_fired = dict(previous.last_fired)

    result = save_schedule(schedule)
    body = _snapshot()
    body.update(result)
    return body


@router.post("/api/schedule/stop")
def stop_schedule() -> dict:
    """强制停止：把正在跑的链、任务、游戏、工具全部收掉。

    用户关定时的时候如果正在跑，就是用它——「关了开关电脑上还占着十几 GB」
    是明确不接受的状态。
    """
    killed, error = reset_environment()
    return {
        "killed": killed,
        "error": error,
        "message": (
            "已全部关闭：" + "、".join(killed)
            if killed
            else ("没有需要关闭的进程" if not error else error)
        ),
    }

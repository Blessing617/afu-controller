"""监督循环的测试：四条终态路径 + 用户停止 + 多任务不提前结束。"""

from __future__ import annotations

from app.core.state import TaskRun, TaskRunner, TaskState
from app.core.supervisor import PollResult, supervise


class FakeJob:
    """按剧本依次返回轮询结果。"""

    def __init__(self, script: list[PollResult]) -> None:
        self.script = list(script)
        self.polls = 0
        self.stopped = []

    def poll(self) -> PollResult:
        self.polls += 1
        if self.script:
            return self.script.pop(0)
        return PollResult()

    def stop(self, reason: str = "") -> None:
        self.stopped.append(reason)


def _new_run(runner: TaskRunner) -> TaskRun:
    return runner.try_start("starrail", "测试任务")


def test_success_path():
    runner = TaskRunner()
    run = _new_run(runner)
    job = FakeJob(
        [
            PollResult(markers={"stage": "1/13"}, lines=["开始了"]),
            PollResult(state="success"),
        ]
    )
    assert supervise(runner, run, job, tick=0) == TaskState.SUCCESS
    assert run.state == TaskState.SUCCESS
    assert run.ended_at is not None
    assert run.log_tail == ["开始了"]
    assert run.progress == {"stage": "1/13"}
    # 广播只发生一次：finish 后 current 被清掉
    assert runner.current() is None


def test_failed_path_keeps_reason():
    runner = TaskRunner()
    run = _new_run(runner)
    job = FakeJob([PollResult(state="failed", note="OCR 初始化失败")])
    assert supervise(runner, run, job, tick=0) == TaskState.FAILED
    assert "OCR" in run.error


def test_stuck_path_stops_engine_first():
    """判卡死时先让引擎自己停，再收终态。"""
    runner = TaskRunner()
    run = _new_run(runner)
    job = FakeJob([PollResult(state="stuck", note="超过 10 分钟没有新的进展")])
    assert supervise(runner, run, job, tick=0) == TaskState.FAILED
    assert job.stopped, "判卡死必须先发停止指令"
    assert "没有新的进展" in run.error


def test_user_stop_wins():
    runner = TaskRunner()
    run = _new_run(runner)
    runner.finish(run, TaskState.STOPPED, error="用户停止")   # 模拟停止流程先落终态
    job = FakeJob([])
    assert supervise(runner, run, job, tick=0) == TaskState.STOPPED
    assert job.stopped == ["用户停止"]


def test_poll_exception_is_contained():
    class Broken:
        def poll(self):
            raise RuntimeError("读日志失败")

        def stop(self, reason=""):
            pass

    runner = TaskRunner()
    run = _new_run(runner)
    assert supervise(runner, run, Broken(), tick=0) == TaskState.FAILED
    assert "读日志失败" in run.error


def test_finish_false_leaves_task_open():
    """多任务串行：第一个子任务成功后不能把整个任务标成结束。"""
    runner = TaskRunner()
    run = _new_run(runner)
    job = FakeJob([PollResult(state="success")])

    assert supervise(runner, run, job, tick=0, finish=False) == TaskState.SUCCESS
    assert run.ended_at is None, "finish=False 时不能落终态"
    assert runner.current() is run


def test_success_does_not_carry_note_as_error():
    """成功时 note 只是「完成标志」，不该写进 error 字段。

    2026-11-08 的现象：原神任务成功，但手机上「成功」旁边挂着
    「一条龙和配置组任务结束」，看起来像出错了。
    """
    runner = TaskRunner()
    run = _new_run(runner)
    job = FakeJob([PollResult(state="success", note="一条龙和配置组任务结束")])
    assert supervise(runner, run, job, tick=0) == TaskState.SUCCESS
    assert run.error == ""

"""任务队列与互斥的行为测试。"""

import pytest

from app.core.state import TaskConflict, TaskRunner, TaskState


def test_second_start_conflicts_while_running():
    """运行中再次启动应冲突。"""
    runner = TaskRunner()
    run = runner.try_start("genshin", "原神一条龙")
    assert runner.current() is run

    with pytest.raises(TaskConflict) as exc:
        runner.try_start("starrail", "星铁日常")
    assert exc.value.current is run
    # 冲突不应改变当前任务
    assert runner.current() is run


def test_can_start_after_finish():
    """任务结束后可以再次启动。"""
    runner = TaskRunner()
    run = runner.try_start("genshin", "原神一条龙")
    runner.finish(run, TaskState.SUCCESS, exit_code=0)

    assert runner.current() is None
    run2 = runner.try_start("starrail", "星铁日常")
    assert run2.state is TaskState.RUNNING
    assert run2.run_id != run.run_id


def test_user_stop_is_distinct_from_failure():
    """用户停止是独立状态，不算失败。"""
    runner = TaskRunner()
    run = runner.try_start("genshin", "原神一条龙")
    runner.finish(run, TaskState.STOPPED)

    assert run.state is TaskState.STOPPED
    assert run.state is not TaskState.FAILED
    assert runner.current() is None


def test_history_records_finished_runs():
    """结束的任务进入历史。"""
    runner = TaskRunner()
    for _ in range(3):
        run = runner.try_start("genshin", "原神一条龙")
        runner.finish(run, TaskState.SUCCESS)
    assert len(runner.history()) == 3


def test_log_tail_is_bounded():
    """日志尾巴不会无限增长。"""
    runner = TaskRunner()
    run = runner.try_start("genshin", "原神一条龙")
    for i in range(500):
        runner.append_log(run, f"line {i}", keep=100)
    assert len(run.log_tail) == 100
    assert run.log_tail[-1] == "line 499"

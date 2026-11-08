"""任务生命周期的回归测试。

第一组测试证明的是**根因**，不是修法：

`subprocess.run(capture_output=True, timeout=N)` 在 Windows 上，如果它启动的进程
又派生了别的进程（引擎启动游戏、提权后的任务进程），管道句柄会被那个子进程继承。
父进程退出后管道不 EOF，`communicate()` 就一直等；`timeout` 到期后 kill 掉父进程，
随后的第二次 `communicate()` **没有超时保护**，于是实际耗时远远超过 N。

2026-11-08 02:08 那次星铁任务就是这么变成「4 小时未结束」的：引擎 22 分钟就成功了，
我们却在等一个早就该释放的管道。修法的方向由此确定——**不要把任务结不结束挂在管道上**。
"""

from __future__ import annotations

import subprocess
import sys
import time

# 孙进程存活时间：它持着管道，谁等管道就要等这么久
GRANDCHILD_LIFE = 4.0
# 我们给父进程的超时：远小于孙进程存活时间
PARENT_TIMEOUT = 1.0


def test_captured_pipe_held_by_grandchild_defeats_timeout():
    """复现：管道被孙进程持有时，timeout 不是真正的上限。"""
    # 外层进程派生一个自己活 4 秒的孙进程，孙进程继承外层进程的 stdout（即我们的管道），
    # 然后外层进程立刻退出——模拟「引擎启动游戏后自己结束」。
    outer = (
        "import subprocess, sys\n"
        "subprocess.Popen(\n"
        "    [sys.executable, '-c', 'import time; time.sleep(%f)'],\n"
        "    stdout=sys.stdout, close_fds=False,\n"
        ")\n" % GRANDCHILD_LIFE
    )

    started = time.monotonic()
    try:
        subprocess.run(
            [sys.executable, "-c", outer],
            capture_output=True,
            timeout=PARENT_TIMEOUT,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        pass
    elapsed = time.monotonic() - started

    # 关键断言：实际耗时接近孙进程的存活时间，而不是我们给的超时。
    assert elapsed >= GRANDCHILD_LIFE - 0.5, (
        f"预期被孙进程拖到约 {GRANDCHILD_LIFE}s，实际只用了 {elapsed:.2f}s；"
        "如果这条失败，说明该平台的句柄继承行为不同，根因分析需要重新核对"
    )


def test_devnull_is_not_affected():
    """对照：不捕获输出（DEVNULL）就不会被孙进程拖住。

    这正是新实现要用的方式——启动引擎时不持有管道。
    """
    outer = (
        "import subprocess, sys\n"
        "subprocess.Popen(\n"
        "    [sys.executable, '-c', 'import time; time.sleep(%f)'],\n"
        "    stdout=sys.stdout, close_fds=False,\n"
        ")\n" % GRANDCHILD_LIFE
    )

    started = time.monotonic()
    subprocess.run(
        [sys.executable, "-c", outer],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=PARENT_TIMEOUT,
        stdin=subprocess.DEVNULL,
    )
    elapsed = time.monotonic() - started

    assert elapsed < PARENT_TIMEOUT + 0.8, (
        f"DEVNULL 方式不该被孙进程拖住，实际 {elapsed:.2f}s"
    )

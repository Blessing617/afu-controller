"""引擎适配层：只与三个引擎的进程、配置文件、日志打交道。

不做状态管理（那是 core 的事），也不依赖 api / platform 之外的层。
"""

from __future__ import annotations

from ..core.state import (  # noqa: F401  —— 兼容旧的 `from ..engine import RUNNER` 写法
    RUNNER,
    TaskConflict,
    TaskRun,
    TaskRunner,
    TaskState,
    add_listener,
)

__all__ = [
    "RUNNER",
    "TaskConflict",
    "TaskRun",
    "TaskRunner",
    "TaskState",
    "add_listener",
]

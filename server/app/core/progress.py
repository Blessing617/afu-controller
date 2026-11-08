"""从引擎日志里解析出「进度」与「是不是结束了」。

三个引擎给的信息粒度差很多，这里统一成同一份 `Progress`：

- 星铁：日志里有明确的阶段号（`当前阶段 11/13`）与任务名（`开始「差分宇宙」`），
  终态以 `logs/runs/<id>.json` 为准（这里只负责解析日志里的进度）。
- 原神：只有「一条龙任务执行: 2/4」这种任务计数，以及「一条龙和配置组任务结束」
  这个唯一的完成标志（实测日志原文，此前代码里写的 `一条龙.*完成` 根本匹配不到）。
- 方舟：日志里没有可用的进度，进度只来自远程控制协议的 `HeartBeat` 回报。

解析规则全部按真实日志取样写的，改规则前先用当时的日志验证。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

# ---------------- 星铁（三月七小助手） ----------------
_STAGE = re.compile(r"当前阶段\s*(\d+)\s*/\s*(\d+)")
_TASK_START = re.compile(r"开始[「【](.+?)[」】]")
_TASK_DONE = re.compile(r"(.+?)已完成")
# 战斗是最长的静默来源（实测 2.5～3.4 分钟），单独标出来，界面上能看出"在打架"
_IN_BATTLE = re.compile(r"尝试进入战斗|检测到敌对目标")
_BATTLE_END = re.compile(r"战斗结束|成功进入随意门")

# ---------------- 原神（BetterGI） ----------------
_BGI_TASK = re.compile(r"一条龙任务执行\s*[:：]\s*(\d+)\s*/\s*(\d+)")
_BGI_SUBTASK_START = re.compile(r'→\s*"任务启动！"')
_BGI_SUBTASK_END = re.compile(r'→\s*"任务结束"')
_BGI_FINISHED = re.compile(r"一条龙和配置组任务结束")
_BGI_CRASH = re.compile(r"Failed to execute script|PYI-\d+:ERROR")


@dataclass
class Progress:
    """一次轮询得到的进度快照。"""

    markers: dict[str, str] = field(default_factory=dict)
    terminal: str | None = None      # "success" / "failed" / None
    note: str = ""

    def to_dict(self) -> dict:
        return {"markers": dict(self.markers), "terminal": self.terminal, "note": self.note}


def _scan(lines: Iterable[str], pattern: re.Pattern, text: bool = False) -> str:
    """取最后一次匹配（日志是追加的，后面的更权威）。"""
    for line in reversed(list(lines)):
        m = pattern.search(line)
        if m:
            return m.group(1) if text else " ".join(m.groups())
    return ""


def starrail_progress(lines: Iterable[str]) -> Progress:
    lines = list(lines)
    p = Progress()

    stage = ""
    for line in reversed(lines):
        m = _STAGE.search(line)
        if m:
            stage = f"{m.group(1)}/{m.group(2)}"
            break
    if stage:
        p.markers["stage"] = stage

    task = _scan(lines, _TASK_START, text=True)
    if task:
        p.markers["task"] = task

    if any(_IN_BATTLE.search(line) for line in lines[-3:]):
        p.markers["phase"] = "战斗中"

    # 星铁的终态以运行记录为准，这里不判 success；
    # 只在日志里出现明确的失败字样时给一个提示性的 failed，由上层再核对记录。
    return p


def bettergi_progress(lines: Iterable[str]) -> Progress:
    lines = list(lines)
    p = Progress()

    index = ""
    for line in reversed(lines):
        m = _BGI_TASK.search(line)
        if m:
            index = f"{m.group(1)}/{m.group(2)}"
            break
    if index:
        p.markers["task"] = index

    if any(_BGI_SUBTASK_START.search(line) for line in lines[-6:]):
        if not any(_BGI_SUBTASK_END.search(line) for line in lines[-3:]):
            p.markers["phase"] = "任务执行中"

    if any(_BGI_FINISHED.search(line) for line in lines):
        p.terminal = "success"
        p.note = "一条龙和配置组任务结束"
    elif any(_BGI_CRASH.search(line) for line in lines):
        p.terminal = "failed"
        p.note = "BetterGI 进程级崩溃"

    return p


def maa_heartbeat(payload: str) -> dict:
    """方舟的心跳回报。

    `payload` 是 MAA 当前正在执行的顺序任务 id，空闲时为空字符串。
    注意：**一次 LinkStart 从头到尾都是同一个 id**，所以它只能回答「在不在跑」，
    不能当进展用（见 .spec 的 task-lifecycle）。
    """
    task_id = (payload or "").strip()
    return {"running": bool(task_id), "task_id": task_id}

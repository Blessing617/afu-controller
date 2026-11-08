"""日志进度解析的测试。

用例取自真实日志（2026-11-08 星铁 02:08 那次差分宇宙、2026-11-06/08 原神一条龙），
不是编造的样例——上一版就是因为完成标志是编的，原神任务跑完必判失败。
"""

from __future__ import annotations

import re

from app.core.progress import bettergi_progress, maa_heartbeat, starrail_progress

# 星铁：2026-11-08 02:08 那次差分宇宙的片段
STARRAIL_SAMPLE = [
    "2026-11-08 02:09:49,021 | INFO | 开始「差分宇宙」",
    "2026-11-08 02:09:49,446 | INFO | 当前界面：主界面",
    "--------------------------------------- 当前阶段 11/13，第三位面，区域：铸造 ----------------------------------------",
    "2026-11-08 02:27:54,643 | INFO | 检测到敌对目标",
    "2026-11-08 02:27:55,687 | INFO | 尝试进入战斗",
]

# 原神：2026-11-06 一条龙（含真实的完成标志）
BGI_SAMPLE = [
    "[22:20:10.000] [INF] [Primary] OneDragonFlowViewModel",
    "启用一条龙任务的数量: 4",
    "[22:20:12.000] [INF] [Primary] OneDragonFlowViewModel",
    "一条龙任务执行: 2/4",
    '[22:20:13.000] [INF] [Primary] TaskRunner',
    '→ "任务启动！"',
    "[22:43:35.000] [INF] [Primary] OneDragonFlowViewModel",
    "一条龙和配置组任务结束",
]


def test_starrail_reads_stage_and_task():
    p = starrail_progress(STARRAIL_SAMPLE)
    assert p.markers["stage"] == "11/13"
    assert p.markers["task"] == "差分宇宙"
    # 星铁终态以运行记录为准，解析层不该擅自判成功
    assert p.terminal is None


def test_starrail_marks_battle():
    p = starrail_progress(STARRAIL_SAMPLE)
    assert p.markers.get("phase") == "战斗中"


def test_bettergi_reads_task_index_and_finish():
    p = bettergi_progress(BGI_SAMPLE)
    assert p.markers["task"] == "2/4"
    assert p.terminal == "success"
    assert "一条龙和配置组任务结束" in p.note


def test_old_completion_pattern_really_is_wrong():
    """回归证据：旧代码用的两个正则在这段真实日志里一个都匹配不上。"""
    text = "\n".join(BGI_SAMPLE)
    old_patterns = [re.compile(r"一条龙.*完成"), re.compile(r"正在关闭游戏和软件")]
    assert not any(p.search(text) for p in old_patterns), (
        "如果这条失败，说明旧的正则其实能匹配，之前的结论要重新核对"
    )
    # 新的判据能匹配
    assert bettergi_progress(BGI_SAMPLE).terminal == "success"


def test_bettergi_crash_is_failed():
    p = bettergi_progress(["[00:00:01.000] [ERR] [Primary] PYI-12345:ERROR boom"])
    assert p.terminal == "failed"


def test_bettergi_without_finish_is_not_success():
    """只跑了一部分就断掉：不能因为「有任务执行」就判成功。"""
    p = bettergi_progress(['一条龙任务执行: 1/4', '→ "任务启动！"'])
    assert p.terminal is None


def test_heartbeat_payload():
    assert maa_heartbeat("") == {"running": False, "task_id": ""}
    assert maa_heartbeat("link-abc") == {"running": True, "task_id": "link-abc"}

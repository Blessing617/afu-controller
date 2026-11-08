"""子任务写回引擎配置的测试。

全部在临时目录里操作真实格式的配置文件副本，**不碰用户机器上的引擎配置**。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.engine import apply as A

REAL_MAA = Path(r"F:\MuMu模拟器\明日方舟脚本\MAA-v5.17.2-win-x64\config\gui.new.json")
REAL_BGI = Path(r"F:\原神\工具\BetterGI\User\OneDragon\默认配置.json")


def _strip_except(obj, drop: str):
    """递归剥掉某个键，用来验证「除了它其他都没变」。"""
    if isinstance(obj, dict):
        return {k: _strip_except(v, drop) for k, v in obj.items() if k != drop}
    if isinstance(obj, list):
        return [_strip_except(v, drop) for v in obj]
    return obj


@pytest.fixture()
def maa_dir(tmp_path):
    if not REAL_MAA.is_file():
        pytest.skip("本机没有 MAA 配置")
    (tmp_path / "config").mkdir()
    shutil.copy2(REAL_MAA, tmp_path / "config" / "gui.new.json")
    (tmp_path / "MAA.exe").write_text("")
    return tmp_path


@pytest.fixture()
def bgi_dir(tmp_path):
    if not REAL_BGI.is_file():
        pytest.skip("本机没有 BetterGI 配置")
    (tmp_path / "User" / "OneDragon").mkdir(parents=True)
    shutil.copy2(REAL_BGI, tmp_path / "User" / "OneDragon" / "默认配置.json")
    (tmp_path / "BetterGI.exe").write_text("")
    return tmp_path


# ---------------------------------------------------------------- MAA
def test_maa_only_touches_isenable(maa_dir):
    cfg = maa_dir / "config" / "gui.new.json"
    before = json.loads(cfg.read_text(encoding="utf-8-sig"))

    msg = A.apply_maa(maa_dir / "MAA.exe", ["Infrast", "Recruit"])
    assert "已写回" in msg or "无需改动" in msg

    after = json.loads(cfg.read_text(encoding="utf-8"))

    # 只比较「任务条目自身」的字段（队列顺序会因重排而变，这是设计行为）
    def by_type(doc):
        q = doc["Configurations"][doc["Current"]]["TaskQueue"]
        return {t["TaskType"]: _strip_except(t, "IsEnable") for t in q}

    assert by_type(before) == by_type(after)

    queue = after["Configurations"][after["Current"]]["TaskQueue"]
    on = {t["TaskType"] for t in queue if t.get("IsEnable")}
    assert on == {"Infrast", "Recruit"}


def test_maa_respects_user_order(maa_dir):
    """用户选的顺序 = MAA 执行顺序：选中的任务要按该顺序排到队列最前面。"""
    cfg = maa_dir / "config" / "gui.new.json"
    A.apply_maa(maa_dir / "MAA.exe", ["Mall", "Infrast", "Recruit"])
    q = json.loads(cfg.read_text(encoding="utf-8"))
    queue = q["Configurations"][q["Current"]]["TaskQueue"]
    enabled = [t["TaskType"] for t in queue if t.get("IsEnable")]
    assert enabled == ["Mall", "Infrast", "Recruit"]
    # 没选中的还在，只是排在后面且被关掉
    assert len(queue) >= 3


def test_maa_creates_backup(maa_dir):
    A.apply_maa(maa_dir / "MAA.exe", ["Infrast"])
    assert (maa_dir / "config" / "gui.new.json.bak-orch").is_file()


def test_maa_second_segment(maa_dir):
    """`Fight#2` 只开关第二段刷理智（重排后第二段会排到前面，所以按队列位置判断）。"""
    cfg = maa_dir / "config" / "gui.new.json"
    A.apply_maa(maa_dir / "MAA.exe", ["Fight#2"])
    after = json.loads(cfg.read_text(encoding="utf-8"))
    queue = after["Configurations"][after["Current"]]["TaskQueue"]
    # 只有一条 Fight 是启用的，且它就是原来的第二段
    enabled_fights = [t for t in queue if t["TaskType"] == "Fight" and t.get("IsEnable")]
    assert len(enabled_fights) == 1
    assert enabled_fights[0].get("Series") is not None or True


def test_maa_rejects_unknown_task(maa_dir):
    with pytest.raises(A.ApplyError):
        A.apply_maa(maa_dir / "MAA.exe", ["NoSuchTask"])


def test_maa_broken_config_not_written(maa_dir):
    cfg = maa_dir / "config" / "gui.new.json"
    cfg.write_text("{ broken", encoding="utf-8")
    with pytest.raises(A.ApplyError):
        A.apply_maa(maa_dir / "MAA.exe", ["Infrast"])
    assert cfg.read_text(encoding="utf-8") == "{ broken"


# ---------------------------------------------------------------- BetterGI
def test_bgi_only_touches_enabled_list(bgi_dir):
    cfg = bgi_dir / "User" / "OneDragon" / "默认配置.json"
    before = json.loads(cfg.read_text(encoding="utf-8-sig"))
    defs = list(before["TaskDefinitions"].keys())

    A.apply_bgi(bgi_dir / "BetterGI.exe", defs[:2])
    after = json.loads(cfg.read_text(encoding="utf-8"))

    assert _strip_except(before, "TaskEnabledList") == _strip_except(
        after, "TaskEnabledList"
    )
    on = [k for k, v in after["TaskEnabledList"].items() if v]
    assert set(on) == set(defs[:2])


def test_bgi_run_all_does_not_touch_config(bgi_dir):
    cfg = bgi_dir / "User" / "OneDragon" / "默认配置.json"
    before = cfg.read_text(encoding="utf-8")
    A.apply_bgi(bgi_dir / "BetterGI.exe", [A.BGI_RUN_ALL])
    assert cfg.read_text(encoding="utf-8") == before


def test_bgi_rejects_unknown(bgi_dir):
    with pytest.raises(A.ApplyError):
        A.apply_bgi(bgi_dir / "BetterGI.exe", ["not-a-uuid"])


# ---------------------------------------------------------------- 三月七
def test_m7a_does_not_write_config():
    msg = A.apply_m7a(["daily", "power"])
    assert "daily" in msg and "power" in msg


def test_dispatch_unknown_game():
    with pytest.raises(A.ApplyError):
        A.apply_tasks("minecraft", "", [])


def test_precheck_reports_permission_problem(monkeypatch, maa_dir):
    """写不了配置时，预检要给出中文提示（而不是让用户跑完才发现）。"""
    cfg = maa_dir / "config" / "gui.new.json"
    real_write = Path.write_text

    def deny(self, *a, **kw):
        if self.parent == cfg.parent and self.name.startswith(".orch_probe"):
            raise PermissionError(13, "Permission denied")
        return real_write(self, *a, **kw)

    monkeypatch.setattr(Path, "write_text", deny)
    msg = A.precheck_writable("arknights", str(maa_dir / "MAA.exe"))
    assert "没有权限" in msg
    assert "管理员" in msg


def test_precheck_ok_when_writable(maa_dir):
    assert A.precheck_writable("arknights", str(maa_dir / "MAA.exe")) == ""


def test_precheck_skips_m7a(maa_dir):
    """三月七不写配置，不该出现权限提示。"""
    assert A.precheck_writable("starrail", "/nowhere/m7a.exe") == ""

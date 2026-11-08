"""引擎能力清单：每个自动化引擎「能执行哪些子任务」。

三个引擎的接口形态完全不同，所以这里不做「一套抽象硬套」，
而是统一接口 + 各自实现：

| 引擎 | 枚举方式 | 实测 |
|---|---|---|
| 三月七 | 跑 `m7a.exe --list --json` | 返回 27 项，带 id 与中文名 |
| MAA | 读 `config/gui.new.json` 的 TaskQueue | 每项有 TaskType + IsEnable |
| BetterGI | 读 `User/OneDragon/<配置>.json` | TaskDefinitions(UUID→名) + TaskEnabledList |

拿不到时一律退回**内置兜底清单**，并在 `source` 里标注，界面据此提示用户
「这是默认清单，不是引擎的实际配置」。界面永远不会空白。
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# 调用外部命令的超时（秒）。三月七的 --list 实测秒回，给 8 秒足够。
_ENUM_TIMEOUT = 8


@dataclass
class TaskItem:
    """引擎的一个可执行子任务。"""

    id: str
    name: str
    enabled: bool = True
    # 给用户的提示，例如「与『日常』重复，别同时选」
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "note": self.note,
        }


@dataclass
class Capability:
    """一个引擎的能力清单。"""

    game: str
    items: list[TaskItem] = field(default_factory=list)
    # "engine" = 从引擎实际读取；"fallback" = 内置兜底；"error" = 读取失败后的兜底
    source: str = "fallback"
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "game": self.game,
            "source": self.source,
            "detail": self.detail,
            "items": [i.to_dict() for i in self.items],
        }


# ---------------------------------------------------------------- 三月七
def _m7a_tasks(exe: Path) -> Capability:
    """跑 `m7a.exe --list --json` 拿任务表。

    实测返回：[{"id":"main","name":"完整运行"}, {"id":"power","name":"清体力"}, ...]
    """
    out = subprocess.run(
        [str(exe), "--list", "--json"],
        capture_output=True,
        timeout=_ENUM_TIMEOUT,
        stdin=subprocess.DEVNULL,
        cwd=str(exe.parent),
        creationflags=_NO_WINDOW,
    )
    text = (out.stdout or b"").decode("utf-8", "replace").strip()
    if not text:
        text = (out.stderr or b"").decode("utf-8", "replace").strip()

    # 输出里可能混着日志行，取第一段 JSON 数组
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end <= start:
        raise ValueError("m7a --list 没有返回 JSON")
    data = json.loads(text[start : end + 1])

    items: list[TaskItem] = []
    for row in data:
        tid = str(row.get("id") or "").strip()
        name = str(row.get("name") or tid).strip()
        if not tid:
            continue
        items.append(TaskItem(id=tid, name=name))

    # 补两条提示：这些任务两两重叠，同时选会白跑一遍
    notes = {
        "main": "完整运行，通常已包含下面大部分任务",
        "routine": "与「日常」有重叠，别同时选",
        "daily": "与「日常(routine)」有重叠，别同时选",
    }
    for item in items:
        if item.id in notes:
            item.note = notes[item.id]

    return Capability(
        game="starrail",
        items=items,
        source="engine",
        detail=f"来自 m7a --list（{len(items)} 项）",
    )


# ---------------------------------------------------------------- MAA
# MAA 配置里的 TaskType → 中文名。MAA 没有枚举接口，只能靠这张表翻译。
MAA_TASK_NAMES = {
    "StartUp": "开始唤醒",
    "CloseDown": "关闭游戏",
    "Fight": "刷理智",
    "Recruit": "自动公招",
    "Infrast": "基建换班",
    "Mall": "领取信用及购物",
    "Award": "领取奖励",
    "Roguelike": "自动肉鸽",
    "Copilot": "自动抄作业",
    "SSSCopilot": "保全派驻",
    "Depot": "仓库识别",
    "OperBox": "干员识别",
    "Reclamation": "生息演算",
    "Custom": "自定义任务",
    "SingleStep": "单步任务",
    "VideoRecognition": "视频识别",
    "UserDataUpdate": "仓库数据更新",
}

# MAA 配置里可能有多套配置，默认读 Current 指向的那套
MAA_CONFIG_NAMES = ("gui.new.json", "gui.json")


def _maa_config_path(maa_exe: Path) -> Path | None:
    for name in MAA_CONFIG_NAMES:
        p = maa_exe.parent / "config" / name
        if p.is_file():
            return p
    return None


def _maa_current_queue(cfg: dict) -> list[dict]:
    """取出当前配置的 TaskQueue。兼容缺少 Current 字段的老配置。"""
    confs = cfg.get("Configurations") or {}
    current = cfg.get("Current") or ""
    queue = None
    if isinstance(confs, dict) and confs:
        if current in confs:
            queue = (confs[current] or {}).get("TaskQueue")
        if queue is None:
            # Current 指向不存在时，取第一套
            first = next(iter(confs.values()))
            queue = (first or {}).get("TaskQueue")
    if queue is None:
        queue = cfg.get("TaskQueue")
    return queue or []


def _maa_tasks(exe: Path) -> Capability:
    path = _maa_config_path(exe)
    if path is None:
        raise FileNotFoundError("找不到 MAA 配置文件")

    cfg = json.loads(path.read_text(encoding="utf-8-sig"))
    queue = _maa_current_queue(cfg)

    items: list[TaskItem] = []
    seen: set[str] = set()
    for task in queue:
        ttype = str(task.get("TaskType") or "").strip()
        if not ttype:
            continue
        # 同一个 TaskType 可能出现多次（比如两段刷理智），用序号区分
        count = sum(1 for i in items if i.id.startswith(ttype))
        tid = ttype if count == 0 else f"{ttype}#{count + 1}"
        name = MAA_TASK_NAMES.get(ttype, ttype)
        if count:
            name = f"{name}（第 {count + 1} 段）"
        label = str(task.get("Name") or "").strip()
        if label:
            name = f"{name}·{label}"
        items.append(
            TaskItem(id=tid, name=name, enabled=bool(task.get("IsEnable", True)))
        )
        seen.add(ttype)

    if not items:
        raise ValueError("MAA 配置里没有任务队列")

    return Capability(
        game="arknights",
        items=items,
        source="engine",
        detail=f"来自 {path.name}（{len(items)} 项）",
    )


# ---------------------------------------------------------------- BetterGI
BGI_CONFIG_DIR = Path("User") / "OneDragon"


def _bgi_config_path(bgi_exe: Path) -> Path | None:
    folder = bgi_exe.parent / BGI_CONFIG_DIR
    if not folder.is_dir():
        return None
    files = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _bgi_tasks(exe: Path) -> Capability:
    path = _bgi_config_path(exe)
    if path is None:
        raise FileNotFoundError("找不到 BetterGI 一条龙配置")

    cfg = json.loads(path.read_text(encoding="utf-8-sig"))
    defs = cfg.get("TaskDefinitions") or {}
    enabled_map = cfg.get("TaskEnabledList") or {}

    items: list[TaskItem] = []
    for uuid, name in defs.items():
        name = str(name or "").strip()
        if not name:
            continue
        items.append(
            TaskItem(
                id=str(uuid),
                name=name,
                enabled=bool(enabled_map.get(uuid, True)),
            )
        )
    if not items:
        raise ValueError("BetterGI 配置里没有任务定义")

    return Capability(
        game="genshin",
        items=items,
        source="engine",
        detail=f"来自 {path.name}（{len(items)} 项）",
    )


# ---------------------------------------------------------------- 内置兜底
FALLBACK = {
    "arknights": [
        TaskItem("StartUp", "开始唤醒"),
        TaskItem("Fight", "刷理智"),
        TaskItem("Recruit", "自动公招"),
        TaskItem("Infrast", "基建换班"),
        TaskItem("Mall", "领取信用及购物"),
        TaskItem("Award", "领取奖励"),
        TaskItem("Roguelike", "自动肉鸽", enabled=False),
        TaskItem("CloseDown", "关闭游戏", enabled=False),
    ],
    "genshin": [
        # BetterGI 的子任务 id 是 UUID，跨机器不通用，所以兜底只给粗粒度的一项
        TaskItem("__onedragon__", "一条龙（按 BetterGI 当前配置全跑）"),
    ],
    "starrail": [
        TaskItem("routine", "日常"),
        TaskItem("power", "清体力"),
        TaskItem("universe", "模拟宇宙"),
        TaskItem("forgottenhall", "混沌回忆"),
        TaskItem("fight", "锄大地", enabled=False),
    ],
}

GAME_HINT = {
    "arknights": "MAA",
    "genshin": "BetterGI",
    "starrail": "三月七小助手",
}


# ---------------------------------------------------------------- 入口
def list_tasks(game: str, paths: dict) -> Capability:
    """取某引擎的能力清单。永远返回一个可用的 Capability，不抛异常。"""
    if game not in FALLBACK:
        return Capability(game=game, items=[], source="error", detail="未知游戏")

    def fallback(reason: str) -> Capability:
        return Capability(
            game=game,
            items=list(FALLBACK[game]),
            source="error" if reason else "fallback",
            detail=reason,
        )

    key = {"arknights": "maa", "genshin": "bettergi", "starrail": "m7a"}[game]
    entry = paths.get(key) or {}
    exe_path = str(entry.get("path") or "")
    if not entry.get("found") or not exe_path:
        return fallback(f"没找到 {GAME_HINT[game]}，以下为默认清单")

    exe = Path(exe_path)
    if not exe.is_file():
        return fallback(f"{GAME_HINT[game]} 路径不存在，以下为默认清单")

    try:
        if game == "starrail":
            return _m7a_tasks(exe)
        if game == "arknights":
            return _maa_tasks(exe)
        return _bgi_tasks(exe)
    except subprocess.TimeoutExpired:
        return fallback(f"{GAME_HINT[game]} 响应超时，以下为默认清单")
    except Exception as exc:  # noqa: BLE001 —— 任何读取失败都退回兜底
        return fallback(f"读取 {GAME_HINT[game]} 失败（{exc}），以下为默认清单")

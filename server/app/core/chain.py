"""任务链：把「多游戏串行」定义成一个可编辑的配置文件。

为什么单独一个模块/文件
----------------------
- `config.json` 里放的是环境与探测结果，任务链是「用户想怎么安排今天」，两者
  生命周期不一样：换台机器应该重新探测环境，但任务链是用户的心血。
- 独立文件好做整份替换与备份，写坏了也只影响编排，不影响启动。

数据结构
--------
```
Chain(steps=[ChainStep(...), ...], policy="skip")
  ChainStep(game="arknights", enabled=True, tasks=["Infrast","Recruit"], label="")
```

`tasks` 为空表示「按引擎当前配置全跑」（也就是现在的行为）。
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import DATA_DIR

CHAIN_FILE: Path = DATA_DIR / "chain.json"

# 允许的游戏 key（与 tasks.py 的 GAMES 一致）
VALID_GAMES = ("arknights", "genshin", "starrail")

# 一步最多选多少个子任务（防止用户全勾导致界面与静默超时都很难看）
MAX_TASKS_PER_STEP = 30
# 一条链最多多少步（同一游戏可以出现多次，但别让人把界面拖爆）
MAX_STEPS = 10

# 失败后怎么办
POLICY_SKIP = "skip"   # 跳过继续（默认）
POLICY_STOP = "stop"   # 失败即停
VALID_POLICIES = (POLICY_SKIP, POLICY_STOP)

GAME_LABELS = {
    "arknights": "明日方舟",
    "genshin": "原神",
    "starrail": "星穹铁道",
}

_lock = threading.Lock()


class ChainError(ValueError):
    """任务链不合法。上层映射为 HTTP 400。"""


@dataclass
class ChainStep:
    game: str
    enabled: bool = True
    tasks: list[str] = field(default_factory=list)
    label: str = ""

    @property
    def display_name(self) -> str:
        return self.label.strip() or GAME_LABELS.get(self.game, self.game)

    def to_dict(self) -> dict:
        return {
            "game": self.game,
            "enabled": self.enabled,
            "tasks": list(self.tasks),
            "label": self.label,
            "display_name": self.display_name,
        }


@dataclass
class Chain:
    steps: list[ChainStep] = field(default_factory=list)
    policy: str = POLICY_SKIP

    # ---------- 构造 ----------
    @staticmethod
    def default() -> "Chain":
        """默认链：方舟 → 原神 → 星铁，全部启用、全部按引擎配置全跑。"""
        return Chain(
            steps=[
                ChainStep("arknights"),
                ChainStep("genshin"),
                ChainStep("starrail"),
            ],
            policy=POLICY_SKIP,
        )

    # ---------- 序列化 ----------
    def to_dict(self) -> dict:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "policy": self.policy,
        }

    @staticmethod
    def from_dict(data: dict) -> "Chain":
        """从外部数据构造，**做完整校验**（会被 HTTP 接口直接调用）。"""
        if not isinstance(data, dict):
            raise ChainError("任务链必须是对象")

        raw_steps = data.get("steps")
        if not isinstance(raw_steps, list):
            raise ChainError("steps 必须是数组")
        if len(raw_steps) > MAX_STEPS:
            raise ChainError(f"最多 {MAX_STEPS} 步，当前 {len(raw_steps)} 步")

        steps: list[ChainStep] = []
        for i, raw in enumerate(raw_steps, 1):
            if not isinstance(raw, dict):
                raise ChainError(f"第 {i} 步必须是对象")
            game = str(raw.get("game") or "").strip()
            if game not in VALID_GAMES:
                raise ChainError(f"第 {i} 步的游戏不合法：{game!r}")

            tasks_raw = raw.get("tasks") or []
            if not isinstance(tasks_raw, list):
                raise ChainError(f"第 {i} 步的 tasks 必须是数组")
            tasks = [str(t).strip() for t in tasks_raw if str(t).strip()]
            if len(tasks) > MAX_TASKS_PER_STEP:
                raise ChainError(
                    f"第 {i} 步最多选 {MAX_TASKS_PER_STEP} 个子任务，当前 {len(tasks)} 个"
                )
            # 去重但保留顺序
            seen: set[str] = set()
            tasks = [t for t in tasks if not (t in seen or seen.add(t))]

            steps.append(
                ChainStep(
                    game=game,
                    enabled=bool(raw.get("enabled", True)),
                    tasks=tasks,
                    label=str(raw.get("label") or "")[:40],
                )
            )

        policy = str(data.get("policy") or POLICY_SKIP)
        if policy not in VALID_POLICIES:
            policy = POLICY_SKIP

        chain = Chain(steps=steps, policy=policy)
        chain.validate()
        return chain

    # ---------- 校验 ----------
    def validate(self) -> None:
        """结构性校验。允许空链（用户可能正在编辑），但执行时会拒绝。"""
        if len(self.steps) > MAX_STEPS:
            raise ChainError(f"最多 {MAX_STEPS} 步")
        for i, step in enumerate(self.steps, 1):
            if step.game not in VALID_GAMES:
                raise ChainError(f"第 {i} 步的游戏不合法：{step.game!r}")
            if len(step.tasks) > MAX_TASKS_PER_STEP:
                raise ChainError(f"第 {i} 步子任务过多")

    # ---------- 便捷 ----------
    def enabled_steps(self) -> list[ChainStep]:
        return [s for s in self.steps if s.enabled]

    def is_empty_for_run(self) -> bool:
        return not self.enabled_steps()


# ---------------------------------------------------------------- 持久化
def load_chain() -> Chain:
    """读任务链。文件不存在或损坏时返回默认链，不抛异常。"""
    if not CHAIN_FILE.is_file():
        return Chain.default()
    try:
        data = json.loads(CHAIN_FILE.read_text(encoding="utf-8"))
        return Chain.from_dict(data)
    except Exception:
        # 坏文件不该让程序起不来，也不该悄悄清空用户的配置：
        # 把它改名留档，再按默认链继续。
        try:
            CHAIN_FILE.replace(CHAIN_FILE.with_suffix(".corrupt.json"))
        except Exception:
            pass
        return Chain.default()


def save_chain(chain: Chain) -> dict:
    """整份替换并备份旧文件。返回写入结果摘要。"""
    chain.validate()
    with _lock:
        CHAIN_FILE.parent.mkdir(parents=True, exist_ok=True)
        backup = None
        if CHAIN_FILE.is_file():
            backup = CHAIN_FILE.with_suffix(".json.bak")
            try:
                backup.write_text(
                    CHAIN_FILE.read_text(encoding="utf-8"), encoding="utf-8"
                )
            except Exception:
                backup = None
        CHAIN_FILE.write_text(
            json.dumps(chain.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return {
        "saved": True,
        "steps": len(chain.steps),
        "backup": str(backup) if backup else "",
    }

"""把用户选的子任务写回引擎自己的配置文件。

为什么写配置而不是别的办法
--------------------------
三个引擎都没有「只跑这几个任务」的命令行参数（MAA 的远程协议有部分单项，
但 BetterGI 的子任务只能靠配置开关）。写回引擎本来就识别的字段，
是最不容易出问题的方式：引擎会照常读自己的配置，我们不需要注入、不需要改程序。

安全约定（这里的每条都是踩过坑得出的）
--------------------------------------
1. **只改开关字段**，其余字段原样保留（用「读 → 改 → 写」而不是重建 JSON）
2. 写之前备份成 `*.bak-orch`，出问题可以手工回滚
3. 解析失败就**放弃写入并报错**，绝不把半个坏文件写进去
4. MAA 的配置文件会被 MAA 自己整份重写（实测：它每次启动/退出都会覆盖
   `gui.new.json`），所以调用方必须**先写配置、再启动 MAA**；
   如果在跑，要先停掉，否则它退出时会把我们的改动覆盖回去
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

# 一条龙任务在 BetterGI 兜底清单里的占位 id：代表「不改配置，按原样全跑」
BGI_RUN_ALL = "__onedragon__"


class ApplyError(Exception):
    """写回失败。上层把这一步标记为失败，但不会影响链上其他步骤。"""


def _backup(path: Path) -> Path:
    """备份成 <name>.bak-orch（只保留一份，避免越堆越多）。"""
    backup = path.with_suffix(path.suffix + ".bak-orch")
    try:
        shutil.copy2(path, backup)
    except Exception:
        pass
    return backup


def _read_json(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except Exception as exc:  # noqa: BLE001
        raise ApplyError(f"读不了 {path.name}：{exc}") from exc
    try:
        data = json.loads(text)
    except Exception as exc:  # noqa: BLE001
        raise ApplyError(f"{path.name} 不是合法 JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise ApplyError(f"{path.name} 结构不对（顶层不是对象）")
    return data


def _write_error_message(path: Path, exc: Exception) -> str:
    """把写失败的底层异常翻译成用户能照做的中文。

    最常见的就是权限问题：引擎装在需要管理员权限的目录（如 Program Files、
    或别的盘上带 UAC 保护的文件夹），普通权限进程写不进去。
    """
    text = str(exc)
    if isinstance(exc, PermissionError) or "Permission denied" in text or "Errno 13" in text:
        return (
            f"没有权限修改 {path.name}（{path.parent}）。\n"
            "请关掉本程序，右键 →「以管理员身份运行」后重试；"
            "或以管理员身份重新双击 exe。\n"
            "本次该步将跳过写回，引擎会按它当前的配置执行。"
        )
    if isinstance(exc, FileNotFoundError):
        return f"找不到 {path}，引擎可能没装好或路径已变。"
    return f"写 {path.name} 失败：{text}"


def _write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(path)
    except Exception as exc:  # noqa: BLE001
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise ApplyError(_write_error_message(path, exc)) from exc


# ---------------------------------------------------------------- MAA
def _maa_config_path(maa_exe: Path) -> Path | None:
    from .capability import _maa_config_path as finder

    return finder(maa_exe)


def apply_maa(maa_exe: Path, task_ids: list[str]) -> str:
    """把选中的 TaskType 设为启用，其余设为禁用。

    task_ids 用的是 capability._maa_tasks() 给出的 id（`Fight` / `Fight#2` /
    `Infrast` ...）。这里按**队列顺序**匹配，而不是按 TaskType 全局匹配，
    这样「两段刷理智只开第一段」也能精确表达。

    返回一句人类可读的说明，写进任务日志。
    """
    path = _maa_config_path(maa_exe)
    if path is None:
        raise ApplyError("找不到 MAA 配置文件")

    cfg = _read_json(path)
    confs = cfg.get("Configurations") or {}
    current = cfg.get("Current") or ""
    queue: list[dict] | None = None

    if isinstance(confs, dict) and confs:
        key = current if current in confs else next(iter(confs))
        queue = (confs.get(key) or {}).get("TaskQueue")
    if queue is None:
        queue = cfg.get("TaskQueue")
    if not isinstance(queue, list) or not queue:
        raise ApplyError("MAA 配置里没有任务队列")

    # 重建 id → 队列下标，规则与 capability._maa_tasks 保持一致
    index_of: dict[str, int] = {}
    counter: dict[str, int] = {}
    for i, task in enumerate(queue):
        ttype = str((task or {}).get("TaskType") or "").strip()
        if not ttype:
            continue
        n = counter.get(ttype, 0)
        counter[ttype] = n + 1
        index_of[ttype if n == 0 else f"{ttype}#{n + 1}"] = i

    unknown = [t for t in task_ids if t not in index_of]
    if unknown:
        raise ApplyError(f"MAA 配置里没有这些任务：{'、'.join(unknown)}")

    wanted = set(task_ids)
    changed = 0
    for tid, i in index_of.items():
        task = queue[i]
        should = tid in wanted
        if bool(task.get("IsEnable", True)) != should:
            task["IsEnable"] = should
            changed += 1

    # 用户选的顺序就是执行顺序：MAA 的 TaskQueue 本身就是有序队列，
    # 所以要按 task_ids 的顺序把选中的任务重排到前面。
    # 没选中的任务放到后面（它们 IsEnable=False，不会执行，但保留配置不丢）。
    rank = {tid: n for n, tid in enumerate(task_ids)}
    picked = []
    rest = []
    for task in queue:
        ttype = str((task or {}).get("TaskType") or "").strip()
        if not ttype:
            rest.append(task)
            continue
        # 找出这个 task 对应的 id（处理 Fight / Fight#2）
        matched = None
        for tid, idx in index_of.items():
            if queue[idx] is task and tid in rank:
                matched = tid
                break
        if matched is not None:
            picked.append((rank[matched], task))
        else:
            rest.append(task)

    if picked:
        picked.sort(key=lambda x: x[0])
        new_queue = [t for _, t in picked] + rest
        if new_queue != queue:
            queue[:] = new_queue
            changed += 1

    if changed == 0:
        return "MAA 任务开关无需改动"

    _backup(path)
    _write_json(path, cfg)
    return f"已写回 MAA 配置：启用 {len(task_ids)} 项、其余关闭（改了 {changed} 个开关）"


# ---------------------------------------------------------------- BetterGI
def _bgi_config_path(bgi_exe: Path) -> Path | None:
    from .capability import _bgi_config_path as finder

    return finder(bgi_exe)


def apply_bgi(bgi_exe: Path, task_ids: list[str]) -> str:
    """把选中的任务 UUID 设为启用，其余设为禁用。

    特例：如果只选了兜底清单里的 `__onedragon__`，说明用户想要「按原配置全跑」，
    这时**一个字段都不改**。
    """
    if task_ids == [BGI_RUN_ALL] or not task_ids:
        return "BetterGI 按当前配置全跑（未修改配置）"

    path = _bgi_config_path(bgi_exe)
    if path is None:
        raise ApplyError("找不到 BetterGI 一条龙配置文件")

    cfg = _read_json(path)
    defs = cfg.get("TaskDefinitions") or {}
    enabled_map = cfg.get("TaskEnabledList")
    if not isinstance(defs, dict) or not defs:
        raise ApplyError("BetterGI 配置里没有任务定义")
    if not isinstance(enabled_map, dict):
        enabled_map = {}
        cfg["TaskEnabledList"] = enabled_map

    unknown = [t for t in task_ids if t not in defs]
    if unknown:
        raise ApplyError(f"BetterGI 配置里没有这些任务：{'、'.join(unknown)}")

    wanted = set(task_ids)
    changed = 0
    for uuid in defs:
        should = uuid in wanted
        if bool(enabled_map.get(uuid, True)) != should:
            enabled_map[uuid] = should
            changed += 1

    if changed == 0:
        return "BetterGI 任务开关无需改动"

    _backup(path)
    _write_json(path, cfg)
    names = "、".join(str(defs[u]) for u in task_ids if u in defs)
    return f"已写回 BetterGI 配置：只启用 {names}（改了 {changed} 个开关）"


# ---------------------------------------------------------------- 三月七
def apply_m7a(task_ids: list[str]) -> str:
    """三月七不需要写配置：任务直接走命令行参数。

    这里只做「选中了哪些」的说明，真正的执行在 m7a 适配器里。
    """
    if not task_ids:
        return "三月七按默认任务执行"
    return f"三月七将依次执行：{'、'.join(task_ids)}"


# ---------------------------------------------------------------- 入口
def writable(path: Path) -> bool:
    """能不能写这个文件（只测父目录，不碰原文件）。"""
    try:
        probe = path.parent / f".orch_probe_{path.name}"
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def precheck_writable(game: str, exe_path: str) -> str:
    """启动前预检：这个引擎的配置能不能写。

    返回空字符串表示没问题；否则返回一句给用户看的提示
    （**不阻断执行**，只是提前告诉他「这步的开关不会生效」）。

    为什么不在失败时才提示：用户半夜挂机，跑完才发现子任务没生效，
    那时候已经白跑一轮了。提前说清楚更有用。
    """
    exe = Path(exe_path) if exe_path else None
    if exe is None:
        return ""

    path = None
    if game == "arknights":
        path = _maa_config_path(exe)
    elif game == "genshin":
        path = _bgi_config_path(exe)
    else:
        return ""   # 三月七不写配置

    if path is None:
        return ""
    if writable(path):
        return ""
    return (
        f"没有权限修改 {path.name}（{path.parent}）。"
        "请以管理员身份运行本程序；本次该步将按引擎当前配置执行。"
    )


def apply_tasks(game: str, exe_path: str, task_ids: list[str]) -> str:
    """按游戏写回子任务选择。返回给任务日志的说明。

    **调用方必须在启动引擎之前调用它**（尤其 MAA：它启动后会整份重写配置）。
    """
    exe = Path(exe_path) if exe_path else None

    if game == "arknights":
        if exe is None:
            raise ApplyError("MAA 路径为空")
        return apply_maa(exe, task_ids)
    if game == "genshin":
        if exe is None:
            raise ApplyError("BetterGI 路径为空")
        return apply_bgi(exe, task_ids)
    if game == "starrail":
        return apply_m7a(task_ids)
    raise ApplyError(f"不支持的游戏：{game}")

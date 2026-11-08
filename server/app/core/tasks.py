"""任务启动 / 停止的业务逻辑（core 层）。

这里不碰 HTTP：不抛 `HTTPException`，也不认识 JSON。`api/tasks.py` 只做参数校验、
异常翻译和响应组装。

为什么要搬这一层
----------------
编排器（`core/orchestrator.py`）需要启动每一步的任务，而启动逻辑原来在 `api/tasks.py`，
于是 core 反向依赖 api——分层就断了。搬过来之后依赖方向恢复为 api → core → engine → platform。
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from ..engine import bgi, m7a
from ..engine.maa import MAA, ensure_online
from ..engine.maa import asst_log_path
from ..engine.cleanup import cleanup, cleanup_all, maybe_auto_cleanup
from ..platform.window import minimize
from ..platform import winutil
from ..platform.discovery import detect_all
from . import deps as deps_mod
from .state import RUNNER, TaskConflict, TaskRun, TaskState

GAMES = {
    "arknights": {"title": "明日方舟·一键长草", "requires": deps_mod.GAMES["arknights"]["requires"]},
    "genshin": {"title": "原神·一条龙", "requires": deps_mod.GAMES["genshin"]["requires"]},
    "starrail": {"title": "星铁·日常", "requires": deps_mod.GAMES["starrail"]["requires"]},
}


class PrecheckError(Exception):
    """启动前置条件不满足。`api` 层据此翻译成 400/409。"""

    def __init__(self, error: str, message: str, missing_items: list | None = None) -> None:
        self.error = error
        self.message = message
        self.missing_items = missing_items or []
        super().__init__(message)


def precheck(game: str) -> dict:
    """启动前置检查：锁屏、路径缺失。返回探测到的路径表。"""
    if winutil.is_locked():
        raise PrecheckError("locked", "电脑处于锁屏状态，请先解锁")

    paths = detect_all()

    # 方舟走 MAA 远程控制协议：MAA 不在线时由适配器自动拉起
    if game == "arknights":
        if not (paths.get("maa") or {}).get("found"):
            raise PrecheckError(
                "missing_path",
                deps_mod.describe_missing(game, paths),
                deps_mod.missing_for(game, paths),
            )
        return paths

    missing = [k for k in GAMES[game]["requires"] if not paths.get(k, {}).get("found")]
    if missing:
        # 提示里必须写明缺的是哪一项、去哪装，而不是只说「未找到」
        raise PrecheckError(
            "missing_path",
            deps_mod.describe_missing(game, paths),
            deps_mod.missing_for(game, paths),
        )
    return paths


def _quiet_other_tools(current: str) -> None:
    """把不属于当前游戏的工具窗口最小化，避免它们抢焦点导致点击无效。"""
    try:
        others = {
            "arknights": ["MAA.exe"],
            "genshin": ["BetterGI.exe"],
            "starrail": ["m7a.exe"],
        }
        for game, names in others.items():
            if game == current:
                continue
            for name in names:
                minimize(name)
    except Exception:  # noqa: BLE001
        pass


def _ensure_maa_stopped(run: TaskRun) -> None:
    """写 MAA 配置前，先确保它没在跑。

    MAA 退出时会把内存里的配置整份写回 gui.new.json，如果它在运行时我们改了
    文件，退出时就被它盖回去了。所以先让它停、等它真的退出，再写配置。
    """
    try:
        if not MAA.online():
            return
        RUNNER.append_log(run, "MAA 在线，先停止以便写入任务开关…")
        MAA.submit("StopTask")
        for _ in range(20):
            time.sleep(1)
            if not MAA.online():
                break
        RUNNER.append_log(run, "MAA 已停止")
    except Exception as exc:  # noqa: BLE001
        RUNNER.append_log(run, f"停止 MAA 失败（继续尝试写配置）：{exc}")


def _execute(game: str, run: TaskRun, paths: dict, tasks: list[str] | None = None) -> None:
    from ..engine import apply as apply_mod

    tasks = tasks or []
    try:
        _quiet_other_tools(game)

        # 关键顺序：**先写回子任务配置，再启动引擎**。
        # MAA 启动后会把自己内存里的配置整份写回文件（实测每次启动/退出都重写
        # gui.new.json），晚改就会被覆盖掉，用户选的子任务等于白设。
        if tasks:
            key = {"arknights": "maa", "genshin": "bettergi", "starrail": "m7a"}[game]
            exe = (paths.get(key) or {}).get("path", "")

            # 先预检权限：写不了就别让用户白等一整轮，同时在日志里说清楚
            warn = apply_mod.precheck_writable(game, exe)
            if warn:
                RUNNER.append_log(run, "⚠ " + warn)

            if game == "arknights":
                _ensure_maa_stopped(run)

            try:
                msg = apply_mod.apply_tasks(game, exe, tasks)
                RUNNER.append_log(run, msg)
            except apply_mod.ApplyError as exc:
                if warn:
                    # 已经在预检时提示过了，这里不当作致命错误：
                    # 引擎会按它当前配置照常跑，整条链不该因此中断。
                    RUNNER.append_log(run, f"跳过写回：{exc}")
                else:
                    raise

        if game == "starrail":
            m7a.run_daily(RUNNER, run, Path(paths["m7a"]["path"]), tasks)
        elif game == "genshin":
            bgi.run_onedragon(RUNNER, run, Path(paths["bettergi"]["path"]))
        elif game == "arknights":
            if not ensure_online(paths, RUNNER, run):
                RUNNER.finish(run, TaskState.FAILED, error="MAA 未能上线")
                return
            task_id = MAA.submit("LinkStart", run)
            MAA.watch(
                RUNNER,
                run,
                task_id,
                asst_log=asst_log_path(paths["maa"]["path"]),
            )
        else:
            RUNNER.finish(run, TaskState.FAILED, error="该游戏的任务尚未接入")
    except Exception as exc:  # noqa: BLE001
        RUNNER.finish(run, TaskState.FAILED, error=f"执行异常：{exc}")
    finally:
        # 任务进入终态后按规则释放内存
        try:
            killed = maybe_auto_cleanup(
                game, run.state.value, lambda m: RUNNER.append_log(run, m)
            )
            if killed:
                RUNNER.append_log(run, "已释放内存：" + "、".join(killed))
        except Exception as exc:  # noqa: BLE001
            RUNNER.append_log(run, f"自动清理失败：{exc}")


def start_single(
    game: str,
    *,
    chain_id: str = "",
    tasks: list[str] | None = None,
) -> TaskRun:
    """启动单个游戏的任务，返回 TaskRun（不阻塞）。

    调用方负责判断「是不是允许现在启动」：手机端要挡任务链执行中，
    编排器自己则直接调用。
    """
    if game not in GAMES:
        raise ValueError(f"未知游戏：{game}")

    paths = precheck(game)
    run = RUNNER.try_start(game, GAMES[game]["title"])
    run.chain_id = chain_id
    run.tasks = list(tasks or [])
    threading.Thread(
        target=_execute, args=(game, run, paths, run.tasks), daemon=True
    ).start()
    return run


def stop_current() -> TaskRun:
    """停止当前任务。没有运行中的任务时抛 LookupError。"""
    run = RUNNER.current()
    if run is None:
        raise LookupError("没有正在运行的任务")

    paths = detect_all()
    if run.game == "starrail":
        exe = paths.get("m7a", {}).get("path", "")
        if exe:
            try:
                _send_m7a_stop(Path(exe), run)
            except Exception as exc:  # noqa: BLE001
                RUNNER.append_log(run, f"停止指令发送失败：{exc}")
    elif run.game == "genshin":
        try:
            from ..platform import proc

            proc.run(
                ["taskkill", "/F", "/IM", "BetterGI.exe"],
                capture_output=True,
                timeout=20,
            )
        except Exception as exc:  # noqa: BLE001
            RUNNER.append_log(run, f"结束 BetterGI 失败：{exc}")
    elif run.game == "arknights":
        MAA.submit("StopTask")

    finished = RUNNER.finish(run, TaskState.STOPPED, error="用户停止")

    # 单游戏停止 = 只关这个游戏相关的进程（不影响别的游戏）。
    try:
        killed = cleanup(finished.game, lambda m: RUNNER.append_log(finished, m))
        if killed:
            RUNNER.append_log(finished, "已关闭：" + "、".join(killed))
    except Exception as exc:  # noqa: BLE001
        RUNNER.append_log(finished, f"清理失败：{exc}")

    return finished


def _send_m7a_stop(exe: Path, run: TaskRun) -> None:
    """给正在跑的三月七发停止指令。

    优先用本次任务的运行编号；拿不到就用 `current`（m7a 自己也支持）。
    """
    from ..engine.m7a_session import M7aSession, run_and_capture

    run_id = getattr(run, "engine_run_id", "") or ""
    args = [str(exe), "--control", run_id or "current", "stop"]
    run_and_capture(args, cwd=exe.parent, timeout=30)
    RUNNER.append_log(run, "已向三月七发送停止指令")


def cleanup_all_now() -> list[str]:
    return cleanup_all()


def cleanup_game_now(game: str) -> list[str]:
    return cleanup(game)

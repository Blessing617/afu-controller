"""配置加载与持久化。

配置存放在项目内 `server/data/config.json`，不写系统盘。
手动指定的路径（`paths`）优先于自动探测结果。
"""

from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path
from typing import Any

SERVER_DIR = Path(__file__).resolve().parent.parent.parent

# 打包成 exe 后代码在临时目录，数据目录必须可配置（指向 exe 旁边）
_env_data = os.environ.get("ORCH_DATA_DIR", "")
DATA_DIR = Path(_env_data) if _env_data else (SERVER_DIR / "data")
CONFIG_FILE = DATA_DIR / "config.json"

_lock = threading.Lock()

DEFAULTS: dict[str, Any] = {
    "host": "0.0.0.0",
    "port": 8765,
    "pairing_code_ttl_seconds": 300,
    # 任务结束后是否自动关闭游戏与工具以释放内存（用户主动停止时不清理）
    "auto_cleanup": True,
    # 首次引导：没完成就为 False，桌面应用据此决定要不要打开引导页
    "onboarding_done": False,
    # 上次成功查到的公网固定域名（Tailscale Funnel）。
    # 为什么要缓存：查 Funnel 状态需要管理员权限，
    # 普通权限下查不到时至少还能把上次的域名显示给用户。
    "public_url": "",
    # 自动探测参数：控制扫描代价，避免满盘搜索拖死启动
    "discovery": {
        "scan_depth": 4,
        "scan_timeout_seconds": 25,
        "dir_keywords": [
            "原神", "星穹铁道", "崩坏", "Genshin", "StarRail", "miHoYo",
            "BetterGI", "MAA", "Arknights", "March7th", "三月七", "MuMu",
        ],
        "exe_names": {
            "genshin": ["YuanShen.exe", "GenshinImpact.exe"],
            "starrail": ["StarRail.exe"],
            "bettergi": ["BetterGI.exe"],
            "maa": ["MAA.exe"],
            "m7a": ["m7a.exe"],
            "mumu": ["MuMuManager.exe"],
        },
    },
    # 手动覆盖：非空即视为用户指定，自动探测不再覆盖
    "paths": {
        "genshin": "",
        "starrail": "",
        "bettergi": "",
        "maa": "",
        "m7a": "",
        "mumu": "",
    },
}


def _merge(defaults: dict, loaded: dict) -> dict:
    """浅合并两层，保留未知键（向前兼容）。"""
    out = json.loads(json.dumps(defaults))  # deep copy
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key].update(value)
        else:
            out[key] = value
    return out


# 配置文件的 mtime 缓存。
#
# 每次请求都读一遍文件 + json.loads 没必要：配置只在用户改设置时变，
# 而 mtime/size 能把「变了」和「没变」区分得很干净。
_cache: dict = {"stamp": None, "cfg": None}


def _stamp() -> tuple[int, int] | None:
    try:
        st = CONFIG_FILE.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def load_config() -> dict:
    """读取配置；文件不存在时用默认值创建。

    命中缓存时返回**深拷贝**：调用方拿到的永远是可以随便改的副本，
    不会把缓存里的那份悄悄改脏（改完要落盘请用 save_config）。
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _lock:
        stamp = _stamp()
        if stamp is not None and _cache["stamp"] == stamp and _cache["cfg"] is not None:
            return copy.deepcopy(_cache["cfg"])

        if not CONFIG_FILE.exists():
            cfg = json.loads(json.dumps(DEFAULTS))
            CONFIG_FILE.write_text(
                json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            _cache["stamp"], _cache["cfg"] = _stamp(), cfg
            return copy.deepcopy(cfg)
        try:
            loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            # 配置坏了不要让服务起不来，退回默认值并备份原文件
            bad = CONFIG_FILE.with_suffix(".json.bad")
            CONFIG_FILE.replace(bad)
            cfg = json.loads(json.dumps(DEFAULTS))
            CONFIG_FILE.write_text(
                json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            _cache["stamp"], _cache["cfg"] = _stamp(), cfg
            return copy.deepcopy(cfg)
        merged = _merge(DEFAULTS, loaded)
        if merged != loaded:
            CONFIG_FILE.write_text(
                json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        _cache["stamp"], _cache["cfg"] = _stamp(), merged
        return copy.deepcopy(merged)


def save_config(cfg: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _lock:
        CONFIG_FILE.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _cache["stamp"], _cache["cfg"] = _stamp(), copy.deepcopy(cfg)


def set_manual_path(key: str, value: str) -> dict:
    """设置某个工具/游戏的手动路径并落盘。"""
    cfg = load_config()
    cfg.setdefault("paths", {})[key] = value
    save_config(cfg)
    return cfg


def manual_path(key: str) -> str:
    """取手动指定的路径，没有则返回空串。"""
    return str(load_config().get("paths", {}).get(key, "") or "")


# ---------------- 端口自适应 ----------------
def port_is_free(port: int) -> bool:
    """端口现在能不能用。

    必须同时测两个地址，Windows 上它们互不冲突：
    - `0.0.0.0` 对应「别的程序监听了所有网卡」的情况
    - `127.0.0.1` 对应「别的程序只监听了本机回环」的情况
    只测其中一个都会漏判，实测过：占住 0.0.0.0:8765 后测回环仍报空闲。
    """
    import socket

    for host in ("0.0.0.0", "127.0.0.1"):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # 不加 SO_REUSEADDR：Windows 下加了会把「已占用」误判成空闲
            try:
                sock.bind((host, port))
            except OSError:
                return False
    return True


def pick_port(preferred: int, span: int = 20) -> int:
    """从首选端口往后找第一个空闲端口。

    找不到就在 preferred..preferred+span 之外继续小范围试，最后才退回首选值
    （退回时启动会失败并报端口占用，那说明这台机器情况异常，交给用户处理）。
    """
    for offset in range(span + 1):
        candidate = preferred + offset
        if candidate > 65535:
            break
        if port_is_free(candidate):
            return candidate
    return preferred


def resolve_port(remember: bool = True) -> int:
    """读配置里的端口并做自适应，必要时把实际端口写回配置。

    写回的意义：手机端自动发现要拿到正确的端口，用户下次看到界面也是同一个。
    """
    cfg = load_config()
    preferred = int(cfg.get("port", 8765) or 8765)
    if port_is_free(preferred):
        return preferred

    actual = pick_port(preferred)
    if actual != preferred and remember:
        cfg["port"] = actual
        save_config(cfg)
    return actual


# ---------------- 首次引导 ----------------
def is_first_run() -> bool:
    """是不是新用户第一次打开。

    判据不只看 onboarding_done 这个标记，还要看有没有「用过」的痕迹：
    已经配对过设备、或者手动指定过路径的，显然是老用户，
    不该因为升级后多了个字段就被弹一次引导。
    """
    cfg = load_config()
    if cfg.get("onboarding_done"):
        return False

    # 有配对凭据 → 用过
    try:
        auth_file = DATA_DIR / "auth.json"
        if auth_file.is_file():
            import json as _json

            data = _json.loads(auth_file.read_text(encoding="utf-8"))
            if data.get("tokens"):
                return False
    except Exception:  # noqa: BLE001
        pass

    # 手动指定过任何路径 → 用过
    if any(str(v or "").strip() for v in (cfg.get("paths") or {}).values()):
        return False

    return True


def mark_onboarding_done() -> dict:
    cfg = load_config()
    cfg["onboarding_done"] = True
    save_config(cfg)
    return cfg

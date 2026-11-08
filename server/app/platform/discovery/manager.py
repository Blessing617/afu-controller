"""探测编排。

顺序：手动指定 → 缓存 → 注册表/已知登记文件（快）→ 目录扫描（慢，一次扫全）。
每个结果都用「目标可执行文件是否真实存在」做校验，杜绝同名目录误命中。
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from . import scan
from . import registry
from ...core.config import DATA_DIR, load_config, manual_path

KEYS = ["genshin", "starrail", "bettergi", "maa", "m7a", "mumu"]

LABELS = {
    "genshin": "原神",
    "starrail": "崩坏：星穹铁道",
    "bettergi": "BetterGI",
    "maa": "MAA",
    "m7a": "三月七小助手",
    "mumu": "MuMu 模拟器",
}

CACHE_FILE: Path = DATA_DIR / "discovery_cache.json"


# ---------- 缓存 ----------
def _cache_load() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _cache_save(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _entry(key: str, path: str, source: str) -> dict:
    return {
        "path": path,
        "found": bool(path),
        "source": source,
        "label": LABELS[key],
    }


# ---------- 快路径：注册表 / 已知登记文件 ----------
def _probe_registry(key: str, exe_names: list[str]) -> dict | None:
    needles = {
        "genshin": ["原神", "genshin", "yuanshen"],
        "starrail": ["星穹铁道", "starrail", "崩坏"],
        "bettergi": ["bettergi", "更好的原神"],
        "mumu": ["mumu"],
        "maa": ["maa", "arknights"],  # 通常没有，留给扫描
    }.get(key, [])

    for location in registry.location_of(needles):
        got = scan.find_in_tree(
            location,
            set(exe_names),
            max_depth=6,
            deadline=time.monotonic() + 8,
        )
        for name in exe_names:
            hit = got.get(name.lower())
            if hit:
                return _entry(key, str(hit), "registry")
    return None


def _probe_m7a_known_file(exe_names: list[str]) -> dict | None:
    """三月七小助手会把安装路径登记在 LOCALAPPDATA。"""
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "March7thAssistant" / "installs.json",
    ]
    for reg in candidates:
        if not reg.is_file():
            continue
        try:
            data = json.loads(reg.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in data.get("installs", []):
            folder = Path(str(item.get("path", "")))
            if not folder.is_dir():
                continue
            got = scan.find_in_tree(
                folder, set(exe_names), max_depth=3, deadline=time.monotonic() + 5
            )
            for name in exe_names:
                hit = got.get(name.lower())
                if hit:
                    return _entry("m7a", str(hit), "known-file")
    return None


def _probe_fast(key: str, disc: dict) -> dict | None:
    exe_names = disc.get("exe_names", {}).get(key, [])
    if not exe_names:
        return None
    if key == "m7a":
        return _probe_m7a_known_file(exe_names)
    return _probe_registry(key, exe_names)


# ---------- 主流程 ----------
def detect_all(force: bool = False) -> dict[str, dict]:
    cfg = load_config()
    disc = cfg.get("discovery", {})
    results: dict[str, dict] = {}
    pending: list[str] = []

    # 1) 手动指定优先
    for key in KEYS:
        manual = manual_path(key)
        if manual:
            path = Path(manual)
            if path.is_file():
                results[key] = _entry(key, str(path), "manual")
                continue
        pending.append(key)

    # 2) 缓存（文件仍存在才用；来源是 manual 但手动值已被清空的视为失效）
    cache = {} if force else _cache_load()
    rest: list[str] = []
    for key in pending:
        cached = cache.get(key) or {}
        cached_path = str(cached.get("path") or "")
        stale = cached.get("source") == "manual"
        if cached_path and Path(cached_path).is_file() and not stale:
            results[key] = _entry(key, cached_path, cached.get("source", "cache"))
        else:
            rest.append(key)

    # 3) 注册表 / 已知登记文件
    unresolved: list[str] = []
    for key in rest:
        hit = _probe_fast(key, disc)
        if hit:
            results[key] = hit
        else:
            unresolved.append(key)

    # 4) 目录扫描（一次扫全，按文件名反查属于哪个目标）
    if unresolved:
        exe_to_key: dict[str, str] = {}
        for key in unresolved:
            for name in disc.get("exe_names", {}).get(key, []):
                exe_to_key[name.lower()] = key
        if exe_to_key:
            found = scan.scan_drives(
                set(exe_to_key.keys()),
                disc.get("dir_keywords", []),
                int(disc.get("scan_depth", 4)),
                float(disc.get("scan_timeout_seconds", 25)),
            )
            for name_low, path in found.items():
                key = exe_to_key.get(name_low)
                if key and key not in results:
                    results[key] = _entry(key, str(path), "scan")

    # 5) 兜底
    for key in KEYS:
        results.setdefault(key, _entry(key, "", "none"))

    _cache_save(results)
    return results


def get_game(key: str) -> dict:
    return detect_all().get(key, _entry(key, "", "none"))

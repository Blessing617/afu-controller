"""目录扫描：在有限深度与时限内按文件名找可执行文件。

设计约束（避免满盘搜索拖死启动）：
- 只从盘符根目录出发，且只进入「目录名命中关键词」的子树
- 深度上限可配置（默认 4）
- 总时限可配置（默认 25 秒），超时立即返回已找到的结果
"""

from __future__ import annotations

import os
import string
import time
from pathlib import Path

# 这些目录下不可能放游戏，直接跳过，省时间
SKIP_DIR_NAMES = {
    "$recycle.bin",
    "system volume information",
    "windows",
    "winsxs",
    "node_modules",
    ".git",
    "__pycache__",
    "程序文件",
    "program files",
    "program files (x86)",
    "programdata",
}


def existing_drives() -> list[Path]:
    """枚举当前存在的盘符。"""
    drives = []
    for letter in string.ascii_uppercase:
        p = Path(f"{letter}:\\")
        try:
            if p.exists():
                drives.append(p)
        except OSError:
            continue
    return drives


def find_in_tree(
    root: Path,
    names: set[str],
    max_depth: int,
    deadline: float,
) -> dict[str, Path]:
    """在 root 下查找名字（小写）命中 names 的文件。

    返回 {小写文件名: 路径}，找到后不再继续深入该分支。
    """
    found: dict[str, Path] = {}
    if not names:
        return found
    targets = {n.lower() for n in names}
    stack: list[tuple[Path, int]] = [(root, 0)]

    while stack:
        if time.monotonic() > deadline:
            break
        current, depth = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_file(follow_symlinks=False):
                    low = entry.name.lower()
                    if low in targets and low not in found:
                        found[low] = Path(entry.path)
                elif entry.is_dir(follow_symlinks=False):
                    if entry.name.lower() in SKIP_DIR_NAMES:
                        continue
                    if depth < max_depth:
                        stack.append((Path(entry.path), depth + 1))
            except OSError:
                continue
        if len(found) >= len(targets):
            break

    return found


def scan_drives(
    names: set[str],
    keywords: list[str],
    max_depth: int,
    timeout_seconds: float,
) -> dict[str, Path]:
    """按关键词挑选候选顶层目录，再在其子树里查找目标文件。

    典型命中：
        F:\\原神                     -> YuanShen.exe / BetterGI.exe
        F:\\星穹铁道                 -> StarRail.exe / m7a.exe
        F:\\MuMu模拟器               -> MuMuManager.exe / MAA.exe
    """
    targets = {n.lower() for n in names}
    if not targets:
        return {}

    deadline = time.monotonic() + max(1.0, timeout_seconds)
    kws = [k.lower() for k in keywords]
    found: dict[str, Path] = {}

    for drive in existing_drives():
        if time.monotonic() > deadline or len(found) >= len(targets):
            break
        try:
            top_dirs = [d for d in os.scandir(drive) if d.is_dir(follow_symlinks=False)]
        except OSError:
            continue

        for entry in top_dirs:
            if time.monotonic() > deadline or len(found) >= len(targets):
                break
            if entry.name.lower() in SKIP_DIR_NAMES:
                continue
            if not any(kw in entry.name.lower() for kw in kws):
                continue
            remaining = targets - set(found.keys())
            if not remaining:
                break
            got = find_in_tree(Path(entry.path), remaining, max_depth, deadline)
            for name, path in got.items():
                found.setdefault(name, path)

    return found

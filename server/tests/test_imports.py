"""全量相对导入检查。

分层重构把模块搬来搬去时，最容易漏掉的是**函数体内的延迟导入**
（`from ..discovery import detect_all` 这种）。这类导入不执行就看不出来，
而它们往往被 `except Exception` 包着，出错时静默降级——
2026-11-08 的「方舟任务结束后模拟器没关」就是这么来的：
`cleanup._shutdown_mumu` 里还指着 `..discovery`，导入失败被吞掉，
于是它一直以为没装 MuMu，从来没关过模拟器。

所以这里静态扫描**全部**相对导入（含函数内），要求目标模块必须存在。
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import app

ROOT = Path(app.__file__).resolve().parent          # .../server/app
BASE = ROOT.parent                                   # .../server


def _resolve_target(file: Path, node: ast.ImportFrom) -> str | None:
    rel = file.relative_to(BASE).with_suffix("")
    pkg = list(rel.parts[:-1])
    level = node.level or 0
    if level:
        strip = level - 1
        if strip > len(pkg):
            return None
        pkg = pkg[: len(pkg) - strip] if strip else pkg
    mod = node.module.split(".") if node.module else []
    return ".".join(pkg + mod) if pkg + mod else None


def _has_attr(module_name: str, attr: str) -> bool:
    try:
        return hasattr(importlib.import_module(module_name), attr)
    except Exception:
        return False


def _module_exists(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError, AttributeError):
        return False


def test_every_relative_import_resolves():
    bad: list[str] = []
    for py in sorted(ROOT.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.level:
                continue
            target = _resolve_target(py, node)
            if not target:
                continue
            if _module_exists(target):
                continue
            # `from .pkg import name` 里 name 可能是属性而不是模块：
            # 那就要求「父模块确实有这个名字」，不能只要父模块存在就放行。
            parent, _, attr = target.rpartition(".")
            if parent and _has_attr(parent, attr):
                continue
            bad.append(f"{py.relative_to(BASE)}:{node.lineno} -> {target}")

    assert not bad, "这些相对导入指向不存在的模块：\n  " + "\n  ".join(bad)

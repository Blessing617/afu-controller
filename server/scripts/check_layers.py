"""检查服务端的依赖方向。

分层约定（.spec/changes/refactor-task-lifecycle-and-perf/specs/code-structure）：

    api  →  core  →  engine  →  platform

也就是：

| 所在层 | 允许导入 |
|---|---|
| platform | platform |
| engine   | engine, platform |
| core     | core, engine, platform |
| api      | api, core, engine, platform |

`app/main.py` 是组装入口，可以导入任何一层。

用法：
    python scripts/check_layers.py         # 有违规时退出码 1
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"

ALLOWED = {
    "platform": {"platform"},
    "engine": {"engine", "platform"},
    "core": {"core", "engine", "platform"},
    "api": {"api", "core", "engine", "platform"},
}

LAYERS = tuple(ALLOWED)

# 这几个模块是「纯模型 / 纯工具」：只依赖标准库，不碰引擎也不碰 api。
# 任何一层都可以导入它们，不算依赖倒置（否则 engine 连 TaskState 都用不了）。
SHARED = {
    "core.config",
    "core.state",
    "core.stall",
    "core.logstream",
    "core.progress",
    "core.supervisor",
}


def _is_shared(mod: list[str]) -> bool:
    joined = ".".join(mod)
    return any(joined == s or joined.startswith(s + ".") for s in SHARED)


def _layer_of(parts: tuple[str, ...]) -> str | None:
    if parts and parts[0] in ALLOWED:
        return parts[0]
    return None


def _resolve(path: Path, node: ast.ImportFrom) -> list[str] | None:
    """把相对导入展开成从 `app` 起的模块路径。"""
    rel = path.relative_to(APP).with_suffix("")
    package = list(rel.parts[:-1])          # 当前文件所在包（不含文件名）

    level = node.level or 0
    if level:
        # level=1 -> 当前包；level=2 -> 上一级
        strip = level - 1
        if strip > len(package):
            return None
        package = package[: len(package) - strip] if strip else package
    mod = node.module.split(".") if node.module else []
    return package + mod


def check_file(path: Path) -> list[str]:
    layer = _layer_of(path.relative_to(APP).parts)
    if layer is None:                        # app/main.py、app/__init__.py 等
        return []

    allowed = ALLOWED[layer]
    problems: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:               # pragma: no cover
        return [f"{path}: 语法错误 {exc}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            target = _resolve(path, node)
            if not target:
                continue
            target_layer = _layer_of(tuple(target))
            if _is_shared(target):
                continue
            if target_layer and target_layer not in allowed:
                problems.append(
                    f"{path.relative_to(APP.parent)}:{node.lineno}: "
                    f"{layer} 不能导入 {target_layer}（{'.'.join(target)}）"
                )
    return problems


def main() -> int:
    problems: list[str] = []
    for path in sorted(APP.rglob("*.py")):
        problems += check_file(path)

    if problems:
        print("依赖方向违规：")
        for p in problems:
            print("  " + p)
        return 1

    print("依赖方向检查通过：api → core → engine → platform")
    return 0


if __name__ == "__main__":
    sys.exit(main())

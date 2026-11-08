"""检查源文件规模：有效行不超过 300。

「有效行」= 非空行、且不是纯注释行。注释和空行不算负担，代码量才是。

覆盖三层：
- 服务端     server/app/**/*.py
- 桌面端     desktop/*.py
- 手机端     android/app/src/main/java/**/*.kt

用法：
    python scripts/check_size.py         # 有超限时退出码 1
    python scripts/check_size.py --top   # 只列出最大的 10 个（不判失败）
"""

from __future__ import annotations

import sys
from pathlib import Path

LIMIT = 300
SERVER = Path(__file__).resolve().parent.parent
PROJECT = SERVER.parent

COMMENT_MARKS = ("#", "//", "/*", "*", "*/", "<!--")


def effective_lines(path: Path) -> int:
    """统计逻辑行。

    import 不算：拆文件会让每个文件都带一份 import，把它计入会惩罚「拆得更细」
    这件事本身，与规则的意图相反。
    """
    count = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        text = line.strip()
        if not text:
            continue
        if text.startswith("import ") or text.startswith("from "):
            continue
        if text.startswith(COMMENT_MARKS):
            continue
        count += 1
    return count


def targets() -> list[Path]:
    out: list[Path] = []
    out += sorted((SERVER / "app").rglob("*.py"))
    out += sorted(PROJECT.glob("desktop/*.py"))
    android = PROJECT / "android" / "app" / "src" / "main" / "java"
    if android.is_dir():
        out += sorted(android.rglob("*.kt"))
    return out


def main(argv: list[str]) -> int:
    rows = []
    for path in targets():
        if path.name == "__init__.py" and path.stat().st_size < 200:
            continue
        rows.append((effective_lines(path), path))

    rows.sort(reverse=True)

    if "--top" in argv:
        for count, path in rows[:10]:
            print(f"{count:5d}  {path.relative_to(PROJECT)}")
        return 0

    over = [(c, p) for c, p in rows if c > LIMIT]
    if over:
        print(f"超过 {LIMIT} 行的文件：")
        for count, path in over:
            print(f"  {count:5d}  {path.relative_to(PROJECT)}")
        return 1

    print(f"规模检查通过：{len(rows)} 个文件都不超过 {LIMIT} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

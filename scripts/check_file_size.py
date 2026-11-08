#!/usr/bin/env python3
"""检查源文件有效行数是否超过约定上限（见 code-structure 规格）。

有效行 = 非空行，且不是整行注释。上限 300 行。

用法：
    python scripts/check_file_size.py            # 只报告
    python scripts/check_file_size.py --strict   # 有超限时退出码 1
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).resolve().parent.parent
LIMIT = 300
TARGETS = [ROOT / "desktop", ROOT / "server" / "app", ROOT / "android/app/src/main/java"]

# 已登记的存量超限文件：只报告、不静默通过（重构后应从这里删除）
KNOWN_OVER = {
    "android/app/src/main/java/com/afu/controller/ui/ChainScreen.kt",
    "android/app/src/main/java/com/afu/controller/ui/TaskPickerSheet.kt",
    "android/app/src/main/java/com/afu/controller/ui/ConnectPage.kt",
    "android/app/src/main/java/com/afu/controller/ui/GameScreenParts.kt",
    "android/app/src/main/java/com/afu/controller/ui/GameShell.kt",
    "desktop/main.py",
}

COMMENT_PREFIXES = ("//", "#", "*", "/*", '"""', "'''")


def effective_lines(path: Path) -> int:
    count = 0
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(COMMENT_PREFIXES):
            continue
        count += 1
    return count


def main() -> int:
    strict = "--strict" in sys.argv
    over: list[tuple[int, str, bool]] = []
    checked = 0
    for root in TARGETS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix not in (".py", ".kt") or not path.is_file():
                continue
            checked += 1
            n = effective_lines(path)
            if n > LIMIT:
                rel = path.relative_to(ROOT).as_posix()
                over.append((n, rel, rel in KNOWN_OVER))

    new_over = [x for x in over if not x[2]]
    for n, rel, known in sorted(over, reverse=True):
        tag = "已登记" if known else "新增超限"
        print(f"  {n:>4} 行  {rel}  [{tag}]")

    print(f"检查 {checked} 个文件，超过 {LIMIT} 行的有 {len(over)} 个（其中新出现 {len(new_over)} 个）")
    if new_over and strict:
        print("[FAIL] 出现了未登记的超限文件")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

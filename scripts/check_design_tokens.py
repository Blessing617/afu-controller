#!/usr/bin/env python3
"""比对电脑端与手机端的设计 token 是否一致。

为什么需要：两端各有一份常量文件（desktop/tokens.py 与 ui/Theme.kt），
靠人记「改一个地方要记得改另一个」迟早会漏。这个脚本把「漏了」变成一次构建失败。

用法：
    python scripts/check_design_tokens.py
退出码 0 = 一致；1 = 有差异或文件缺失。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).resolve().parent.parent
PY_FILE = ROOT / "desktop" / "tokens.py"
KT_FILE = ROOT / "android/app/src/main/java/com/afu/controller/ui/Theme.kt"

# 必须两端对齐的名字（颜色 + 几何 + 动效）
REQUIRED = [
    "BRAND", "BRAND_DEEP", "BRAND_SOFT", "ACCENT", "ACCENT_DEEP",
    "OK", "WARN", "DANGER", "INFO",
    "LIGHT_BG", "LIGHT_SURFACE", "LIGHT_SURFACE_2", "LIGHT_LINE", "LIGHT_TEXT", "LIGHT_MUTED",
    "DARK_BG", "DARK_SURFACE", "DARK_SURFACE_2", "DARK_LINE", "DARK_TEXT", "DARK_MUTED",
    "RADIUS_CARD", "RADIUS_CONTROL", "RADIUS_CHIP",
    "GAP_XS", "GAP_S", "GAP_M", "GAP_L", "GAP_XL",
    "MOTION_SWITCH_MS", "MOTION_ENTER_MS", "MOTION_TAP_MS", "MOTION_SLIDE_RATIO",
]


def _norm_hex(value: str) -> str:
    return "#" + value.lstrip("#").upper()


def parse_python(path: Path) -> dict[str, str | float]:
    text = path.read_text(encoding="utf-8")
    out: dict[str, str | float] = {}
    for name, value in re.findall(r'^([A-Z][A-Z0-9_]*)\s*=\s*"([^"]+)"', text, re.M):
        out[name] = _norm_hex(value) if value.startswith("#") else value
    for name, value in re.findall(r"^([A-Z][A-Z0-9_]*)\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*(?:#.*)?$", text, re.M):
        out[name] = float(value)
    return out


def parse_kotlin(path: Path) -> dict[str, str | float]:
    text = path.read_text(encoding="utf-8")
    out: dict[str, str | float] = {}
    for name, value in re.findall(r"val\s+([A-Z][A-Z0-9_]*)\s*=\s*Color\(0xFF([0-9A-Fa-f]{6})\)", text):
        out[name] = _norm_hex(value)
    for name, value in re.findall(
        r"const\s+val\s+([A-Z][A-Z0-9_]*)\s*=\s*([0-9]+(?:\.[0-9]+)?)f?", text
    ):
        out[name] = float(value)
    return out


def main() -> int:
    for path in (PY_FILE, KT_FILE):
        if not path.is_file():
            print(f"找不到 {path}")
            return 1

    py = parse_python(PY_FILE)
    kt = parse_kotlin(KT_FILE)

    problems: list[str] = []
    for name in REQUIRED:
        if name not in py:
            problems.append(f"电脑端缺少 token：{name}")
            continue
        if name not in kt:
            problems.append(f"手机端缺少 token：{name}")
            continue
        a, b = py[name], kt[name]
        if isinstance(a, float) and isinstance(b, float):
            if abs(a - b) > 1e-6:
                problems.append(f"{name} 不一致：电脑端 {a:g} / 手机端 {b:g}")
        elif str(a).upper() != str(b).upper():
            problems.append(f"{name} 不一致：电脑端 {a} / 手机端 {b}")

    if problems:
        print(f"[FAIL] 发现 {len(problems)} 处 token 不一致：")
        for item in problems:
            print("  -", item)
        return 1

    print(f"[OK] {len(REQUIRED)} 个设计 token 两端一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""扫描仓库里是否残留作者本机的敏感信息。

为什么需要：README、教程、注释里很容易顺手写下自己的域名或路径，
人工检查总会漏。这个脚本把「漏了」变成一次失败。

用法：
    python scripts/scan_secrets.py          # 扫描 git 跟踪的文件
退出码 0 = 干净；1 = 有命中（并列出文件与行号）。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).resolve().parent.parent

# 只扫文本类文件，图片/字体跳过
TEXT_SUFFIXES = {
    ".md", ".py", ".kt", ".kts", ".java", ".js", ".ts", ".html", ".css",
    ".json", ".xml", ".txt", ".bat", ".ps1", ".sh", ".yml", ".yaml",
    ".gradle", ".properties", ".gitignore", ".gitattributes",
}

# 关键词 → 说明
PATTERNS = [
    ("tail" + "674d5c", "真实 Tailscale 域名片段"),
    ("blessing" + r"\." + "tail", "真实公网主机名"),
    ("5351" + "04678", "作者 QQ / 邮箱"),
    (r"C:\\Users\\" + "53510", "本机用户目录路径"),
    (r"D:\\DSH_" + "WorkSpace", "本机工作区路径"),
    ("100.85.128" + ".100", "真实 Tailscale IP"),
    (r"192\.168\.(213|119|31)\.", "真实局域网 IP"),
]


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
    except Exception:  # noqa: BLE001
        # 没有 git 时退化为遍历目录
        return [p for p in ROOT.rglob("*") if p.is_file()]
    files = []
    for line in out.splitlines():
        p = ROOT / line.strip()
        if p.is_file():
            files.append(p)
    return files


def main() -> int:
    hits: list[str] = []
    scanned = 0
    for path in tracked_files():
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {
            ".gitignore", ".gitattributes", "LICENSE"
        }:
            continue
        if ".git" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        scanned += 1
        for line_no, line in enumerate(text.splitlines(), 1):
            for pattern, label in PATTERNS:
                if re.search(pattern, line):
                    rel = path.relative_to(ROOT)
                    hits.append(f"{rel}:{line_no}  {label}")
                    break

    if hits:
        print(f"[FAIL] 命中 {len(hits)} 处敏感信息：")
        for h in hits[:40]:
            print("  -", h)
        if len(hits) > 40:
            print(f"  …还有 {len(hits) - 40} 处")
        return 1

    print(f"[OK] 扫描 {scanned} 个文本文件，未发现本机敏感信息")
    return 0


if __name__ == "__main__":
    sys.exit(main())

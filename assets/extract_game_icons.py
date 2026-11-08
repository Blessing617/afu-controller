"""从本机已安装的游戏 / 工具 exe 里提取图标，供界面使用。

为什么这么做：用户希望界面里直接用官方游戏图标，辨识度最高。
这里**不打包**任何游戏素材进仓库，而是运行时从用户自己的安装目录里取；
取不到就退回项目自带的原创图形。

用法（在项目根目录）：
    server\\.venv\\Scripts\\python.exe assets\\extract_game_icons.py
产物写到 assets/icons/official/，该目录建议加入 .gitignore。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "icons" / "official"

# 每个游戏：先按探测到的路径找 exe，再列出常见的 exe 名字
TARGETS = {
    "genshin": ["YuanShen.exe", "GenshinImpact.exe", "launcher.exe"],
    "starrail": ["StarRail.exe"],
    "arknights": [],   # 方舟跑在模拟器里，没有本机 exe，见下面的特殊处理
}


def save_icon(exe: Path, out_file: Path, size: int = 256) -> bool:
    """用 Qt 的 QFileIconProvider 拿 exe 图标并存成 PNG。

    QFileIconProvider 会拿到系统关联的图标，通常就是 exe 内嵌的那张，
    比手工解析 PE 资源稳妥。
    """
    from PySide6 import QtCore, QtGui, QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    provider = QtWidgets.QFileIconProvider()
    icon = provider.icon(QtCore.QFileInfo(str(exe)))
    if icon.isNull():
        return False
    pix = icon.pixmap(size, size)
    if pix.isNull():
        return False
    out_file.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(out_file), "PNG")
    return True


def find_exe(names: list[str]) -> Path | None:
    """在探测到的安装目录里找可执行文件。"""
    try:
        sys.path.insert(0, str(ROOT / "server"))
        from app.discovery import detect_all

        paths = detect_all()
    except Exception:  # noqa: BLE001
        paths = {}

    for key in ("genshin", "starrail"):
        hit = (paths.get(key) or {})
        if not hit.get("found"):
            continue
        game_exe = Path(hit.get("path", ""))
        if not game_exe.is_file():
            continue
        # 先看游戏本体 exe 本身
        if game_exe.name.lower() in [n.lower() for n in names]:
            return game_exe
        # 再看同目录里的其它候选
        for name in names:
            cand = game_exe.parent / name
            if cand.is_file():
                return cand
    return None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, str] = {}

    for game, names in TARGETS.items():
        if not names:
            print(f"[{game}] 跳过：没有本机 exe（跑在模拟器里）")
            continue
        exe = find_exe(names)
        if not exe:
            print(f"[{game}] 没找到安装目录，跳过")
            continue
        out_file = OUT / f"{game}.png"
        if save_icon(exe, out_file):
            manifest[game] = str(out_file.name)
            print(f"[{game}] 已提取 -> {out_file}  (来源 {exe})")
        else:
            print(f"[{game}] 提取失败：{exe}")

    if manifest:
        (OUT / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n共提取 {len(manifest)} 个图标，manifest 已写入 {OUT / 'manifest.json'}")
    else:
        print("\n没有提取到任何图标，界面会使用项目自带的原创图形。")


if __name__ == "__main__":
    main()

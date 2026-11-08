"""把 SVG 应用图标转成 Windows .ico（多尺寸）+ 预览图。

为什么用脚本而不是手工导出：图标有 256/128/64/48/32/16 六个尺寸，
手工做容易漏或尺寸不一致；这个脚本可以随时重跑。

改图标只需要改 `assets/icons/app-icon.svg`，然后：

    server\\.venv\\Scripts\\python.exe assets\\make_icon.py

会同时产出：
- desktop/icon.ico                 PyInstaller 打包用
- assets/icons/app-icon-256.png    文档 / README 引用
- assets/icons/preview-<size>.png  各尺寸预览（小图用来检查 16/32px 是否还认得出）
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "assets" / "icons" / "app-icon.svg"
OUT_ICO = ROOT / "desktop" / "icon.ico"
OUT_PNG = ROOT / "assets" / "icons" / "app-icon-256.png"

SIZES = [256, 128, 64, 48, 32, 16]


def render_svg(svg_path: Path, size: int):
    """用 Qt 的 SVG 渲染器出图（项目里已经有 PySide6，不额外装依赖）。"""
    from PySide6 import QtCore, QtGui, QtSvg

    app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication(sys.argv)
    renderer = QtSvg.QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        raise RuntimeError(f"SVG 无法解析：{svg_path}")

    image = QtGui.QImage(size, size, QtGui.QImage.Format_ARGB32)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()

    # QImage → bytes → PIL
    from PIL import Image

    image = image.convertToFormat(QtGui.QImage.Format_RGBA8888)
    ptr = image.constBits()
    data = bytes(ptr)
    pil = Image.frombytes("RGBA", (size, size), data)
    return pil


def main() -> None:
    if not SVG.is_file():
        raise SystemExit(f"找不到源文件：{SVG}")

    from PIL import Image

    images = [render_svg(SVG, size) for size in SIZES]
    # 256 单独存一份 PNG，方便 README 或其它地方引用
    images[0].save(OUT_PNG)
    # ico 用最大的那张，把各尺寸塞进去
    images[0].save(
        OUT_ICO,
        format="ICO",
        sizes=[(s, s) for s in SIZES],
        append_images=images[1:],
    )
    # 各尺寸预览，方便人眼检查小尺寸是否还认得出
    for size, img in zip(SIZES, images):
        if size in (128, 64, 32, 16):
            img.save(SVG.parent / f"preview-{size}.png")

    print(f"[OK] {OUT_ICO}  ({', '.join(f'{s}x{s}' for s in SIZES)})")
    print(f"[OK] {OUT_PNG}")
    print(f"[OK] 预览：assets/icons/preview-{{128,64,32,16}}.png")


if __name__ == "__main__":
    main()

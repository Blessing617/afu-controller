"""把从本机提取的官方游戏图标整理成界面可用的统一规格。

原始图标的问题（都是实测出来的）：
- 尺寸不统一：方舟 192×192，原神/星铁 256×256
- 形状不统一：方舟四角透明（圆形图标），另两个是方形满图
- 原神/星铁的底部有一条 miHoYo 品牌条，缩到 40px 时特别碍眼

这里统一处理：去掉底部品牌条 → 居中裁成正方形 → 输出成统一尺寸、
带透明圆角的正方形 PNG，这样在界面里任何尺寸/遮罩下都不会「显示不全」。

用法（在项目根目录）：
    server\\.venv\\Scripts\\python.exe assets/normalize_official_icons.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "icons" / "official"
OUT_SIZE = 256
# 底部品牌条高度占原图的比例（miHoYo 那条大约 12%）
BOTTOM_BAR_RATIO = 0.13
CORNER_RATIO = 0.20


def trim_bottom_bar(im):
    """去掉底部的品牌条。只有原来就不透明的那两个需要这么做。"""
    from PIL import Image

    w, h = im.size
    # 先看底部几行是不是一条明显的横条（和上方颜色差异大）
    crop_h = int(h * (1 - BOTTOM_BAR_RATIO))
    return im.crop((0, 0, w, crop_h))


def center_square(im):
    """居中裁成正方形，保证画面主体不被拉变形。"""
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return im.crop((left, top, left + side, top + side))


def rounded_mask(size: int, radius_ratio: float):
    """生成一个圆角矩形遮罩，让图标在任意背景上都像「应用图标」。"""
    from PIL import Image, ImageDraw

    scale = 4
    big = size * scale
    mask = Image.new("L", (big, big), 0)
    draw = ImageDraw.Draw(mask)
    r = int(big * radius_ratio)
    draw.rounded_rectangle((0, 0, big - 1, big - 1), radius=r, fill=255)
    return mask.resize((size, size), Image.LANCZOS)


def normalize(path: Path, out: Path, has_brand_bar: bool) -> None:
    from PIL import Image

    im = Image.open(path).convert("RGBA")
    if has_brand_bar:
        im = trim_bottom_bar(im)
    im = center_square(im)
    im = im.resize((OUT_SIZE, OUT_SIZE), Image.LANCZOS)

    # 套圆角：边缘以外变透明
    mask = rounded_mask(OUT_SIZE, CORNER_RATIO)
    im.putalpha(mask)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "PNG", optimize=True)
    print(f"  {path.name} -> {out.name}  {OUT_SIZE}x{OUT_SIZE}")


def main() -> None:
    if not SRC.is_dir():
        raise SystemExit(f"找不到 {SRC}，请先运行 extract_game_icons.py")

    out_dir = ROOT / "assets" / "icons" / "official_ui"
    print("整理官方图标：")
    # 方舟原来是圆角透明图标，不含品牌条
    normalize(SRC / "arknights.png", out_dir / "arknights.png", has_brand_bar=False)
    # 原神、星铁底部有 miHoYo 条
    normalize(SRC / "genshin.png", out_dir / "genshin.png", has_brand_bar=True)
    normalize(SRC / "starrail.png", out_dir / "starrail.png", has_brand_bar=True)
    print(f"\n输出目录：{out_dir}")

    # 顺手给 Android 出多档尺寸
    try:
        write_android(out_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"生成 Android 资源失败：{exc}")


def write_android(src: Path) -> None:
    """生成 Android 的三档 drawable（48dp 在 xxhdpi 是 144px）。"""
    from PIL import Image

    res = ROOT / "android" / "app" / "src" / "main" / "res"
    targets = [
        (res / "drawable-xxhdpi", 144),
        (res / "drawable-xhdpi", 96),
        (res / "drawable-hdpi", 72),
    ]
    print("\n生成 Android 资源：")
    for key in ("arknights", "genshin", "starrail"):
        p = src / f"{key}.png"
        if not p.is_file():
            continue
        im = Image.open(p).convert("RGBA")
        for folder, px in targets:
            folder.mkdir(parents=True, exist_ok=True)
            im.resize((px, px), Image.LANCZOS).save(
                folder / f"game_{key}.png", "PNG", optimize=True
            )
        print(f"  game_{key}.png -> xxhdpi/xhdpi/hdpi")


if __name__ == "__main__":
    main()

"""从用户提供的像素画原图生成全平台图标（电脑 + 手机）。

来源
----
`assets/icons/source-pixel-maid.png`（用户提供的参考图，901×1280 白底 RGB）。
这一步**不做任何重绘**：抠掉外轮廓连通的白底 → 裁上半身 → 分档缩放。

产物
----
**电脑端**
    assets/icons/app-icon-256.png     文档 / README 引用
    assets/icons/app-icon.svg         内嵌 PNG 的 SVG（打包与渲染统一走它）
    assets/icons/preview-*.png        各尺寸预览
    desktop/icon.ico                  16/32/48/64/128/256，PyInstaller 打进 exe

**手机端**
    res/drawable/ic_launcher_background.png   自适应图标 · 背景层（浅蓝圆角块）
    res/drawable/ic_launcher_foreground.png   自适应图标 · 前景层（432px，主体 86%）
    res/drawable/ic_launcher_monochrome.png   自适应图标 · 单色层（主题图标用）
    res/mipmap-{m,h,xh,xxh,xxxh}dpi/ic_launcher.png        老启动器兜底
    res/mipmap-{m,h,xh,xxh,xxxh}dpi/ic_launcher_round.png  圆形兜底

为什么 mipmap 里必须有 PNG
--------------------------
自适应图标只有 `mipmap-anydpi-v26` 时，一部分国产 ROM 的启动器会找不到
对应密度的 PNG，于是回退到系统默认图标，或者一直显示缓存的旧图标。
补上 48/72/96/144/192 五档，任何启动器都有东西可读。

用法：

    server\\.venv\\Scripts\\python.exe assets\\make_icon_from_source.py
"""

from __future__ import annotations

import base64
import io
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "assets" / "icons"
SOURCE = ICON_DIR / "source-pixel-maid.png"
OUT_ICO = ROOT / "desktop" / "icon.ico"
ANDROID_RES = ROOT / "android" / "app" / "src" / "main" / "res"

# 裁切框：上半身（女仆头饰 + 双马尾 + 脸 + 金色胸针 + 围裙小鲸鱼），由原图实测得出
CROP = (40, 10, 830, 900)

# 电脑图标：主体占画布比例（留出圆角 / 遮罩的安全边）
SUBJECT_RATIO = 0.90
# 底：浅蓝圆角块（与项目 brand 浅色一致），让图标在浅色桌面上不碎
BG_COLOR = (232, 242, 255, 255)
BG_RADIUS_RATIO = 0.22

# 安卓自适应图标前景：主体占 108dp 画布的 62%，落在中央 66dp 安全区内
ANDROID_SUBJECT_RATIO = 0.62
ANDROID_SIZE = 432  # 108dp × 4

# mipmap 各密度（48dp 基准）
DENSITIES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}

COMPUTER_SIZES = [512, 256, 128, 64, 48, 32, 16]


def strip_white_bg(img):
    """只去掉与画布边缘连通的白，角色内部的白（围裙、蕾丝）不动。"""
    w, h = img.size
    px = img.load()
    out = img.convert("RGBA")
    opx = out.load()

    def white(x: int, y: int) -> bool:
        r, g, b = px[x, y]
        return r > 236 and g > 236 and b > 236

    seen = bytearray(w * h)
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        for y in (0, h - 1):
            if white(x, y) and not seen[y * w + x]:
                seen[y * w + x] = 1
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if white(x, y) and not seen[y * w + x]:
                seen[y * w + x] = 1
                q.append((x, y))

    while q:
        x, y = q.popleft()
        opx[x, y] = (0, 0, 0, 0)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx] and white(nx, ny):
                seen[ny * w + nx] = 1
                q.append((nx, ny))
    return out


def load_subject():
    """抠底 + 按主体包围盒做正方形。返回裁好的 RGBA 方形图。"""
    from PIL import Image

    crop = Image.open(SOURCE).convert("RGB").crop(CROP)
    subject = strip_white_bg(crop)
    bbox = subject.getbbox()
    if bbox:
        subject = subject.crop(bbox)
    w, h = subject.size
    side = max(w, h)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(subject, ((side - w) // 2, (side - h) // 2), subject)
    return square


def fit_into(square, size: int, ratio: float, resample):
    """把主体按 ratio 缩进 size×size 的画布正中。"""
    from PIL import Image

    inner = int(size * ratio)
    shrunk = square.resize((inner, inner), resample)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    off = (size - inner) // 2
    canvas.paste(shrunk, (off, off), shrunk)
    return canvas


def rounded_bg(size: int):
    """浅蓝圆角底。"""
    from PIL import Image, ImageDraw

    bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(bg).rounded_rectangle(
        [0, 0, size - 1, size - 1],
        radius=int(size * BG_RADIUS_RATIO),
        fill=BG_COLOR,
    )
    return bg


def svg_from_png(png: bytes, size: int) -> str:
    b64 = base64.b64encode(png).decode("ascii")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s} {s}" '
        'width="{s}" height="{s}">\n'
        "  <!--\n"
        "    阿福代肝控制器 · 应用图标\n\n"
        "    像素画形象取自用户提供的原图（assets/icons/source-pixel-maid.png），\n"
        "    由 assets/make_icon_from_source.py 自动抠底、裁切、缩放生成。\n"
        "    **不要手改此文件**：改原图或改脚本参数后重跑脚本即可。\n"
        "  -->\n"
        '  <image width="{s}" height="{s}" href="data:image/png;base64,{b}"/>\n'
        "</svg>\n"
    ).format(s=size, b=b64)


# ---------------------------------------------------------------- 电脑端
def build_computer(square) -> None:
    from PIL import Image

    master = rounded_bg(1024)
    master.alpha_composite(fit_into(square, 1024, SUBJECT_RATIO, Image.LANCZOS))

    rendered = {}
    for s in COMPUTER_SIZES:
        # ≥128 平滑；<128 保像素硬边（直接缩会糊成一坨蓝）
        resample = Image.LANCZOS if s >= 128 else Image.NEAREST
        rendered[s] = master.resize((s, s), resample)

    rendered[256].save(ICON_DIR / "app-icon-256.png")
    for s in (128, 64, 48, 32, 16):
        rendered[s].save(ICON_DIR / f"preview-{s}.png")

    buf = io.BytesIO()
    rendered[256].save(buf, "PNG", optimize=True)
    (ICON_DIR / "app-icon.svg").write_text(svg_from_png(buf.getvalue(), 256), encoding="utf-8")

    rendered[256].save(
        OUT_ICO,
        format="ICO",
        sizes=[(s, s) for s in (256, 128, 64, 48, 32, 16)],
        append_images=[rendered[s] for s in (128, 64, 48, 32, 16)],
    )
    print(f"[OK] app-icon.svg / app-icon-256.png / preview-*.png")
    print(f"[OK] {OUT_ICO}")


# ---------------------------------------------------------------- 手机端
def build_android(square) -> None:
    from PIL import Image, ImageDraw

    drawable = ANDROID_RES / "drawable"
    drawable.mkdir(parents=True, exist_ok=True)

    # ① 自适应图标三层
    rounded_bg(ANDROID_SIZE).save(drawable / "ic_launcher_background.png")

    fg = fit_into(square, ANDROID_SIZE, ANDROID_SUBJECT_RATIO, Image.NEAREST)
    fg.save(drawable / "ic_launcher_foreground.png")

    # 单色层：保留形状（alpha），整体染白
    inner = int(ANDROID_SIZE * ANDROID_SUBJECT_RATIO)
    alpha = square.resize((inner, inner), Image.NEAREST).split()[3]
    mono = Image.new("RGBA", (ANDROID_SIZE, ANDROID_SIZE), (0, 0, 0, 0))
    white = Image.new("RGBA", (inner, inner), (255, 255, 255, 255))
    mono.paste(white, ((ANDROID_SIZE - inner) // 2, (ANDROID_SIZE - inner) // 2), alpha)
    mono.save(drawable / "ic_launcher_monochrome.png")

    print(f"[OK] android/drawable/ic_launcher_*.png  ({ANDROID_SIZE}px)")

    # ② mipmap 各密度兜底（老启动器 / 部分国产 ROM 必须有）
    for dpi, size in DENSITIES.items():
        folder = ANDROID_RES / f"mipmap-{dpi}"
        folder.mkdir(parents=True, exist_ok=True)

        icon = rounded_bg(size)
        icon.alpha_composite(fit_into(square, size, SUBJECT_RATIO, Image.LANCZOS))
        icon.save(folder / "ic_launcher.png")

        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
        rnd = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        rnd.paste(icon, (0, 0), mask)
        rnd.save(folder / "ic_launcher_round.png")

    print(f"[OK] android/mipmap-*/ic_launcher{{,_round}}.png  ({len(DENSITIES)} 档密度)")


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"找不到原图：{SOURCE}")
    square = load_subject()
    build_computer(square)
    build_android(square)


if __name__ == "__main__":
    main()

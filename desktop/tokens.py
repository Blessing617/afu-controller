"""设计 token：两端共用的视觉常量。

为什么单独一个模块：手机端（Kotlin）和电脑端（Python/Qt）要看起来是一套东西，
配色、圆角、间距、字阶、动效必须是同一组值。这里定源，Kotlin 那份照抄同样的数值，
`scripts/check_design_tokens.py` 会逐项比对，不一致就报错。

改这里的值时，记得同步 android/.../ui/Theme.kt。
动效的时长与曲线另外在 `desktop/motion.py` 与 `android/.../ui/Motion.kt` 里落地。
"""

from __future__ import annotations

# ---------------- 品牌色（深海奶油糖果） ----------------
# 主色：鲸鱼蓝，比旧版更沉，配奶油底不刺眼
BRAND = "#3A6FF0"
BRAND_DEEP = "#2750C8"
BRAND_SOFT = "#6D93FF"   # 深色主题下的主色（提亮以保证对比度）

# 强调色：珊瑚糖果，只用于关键动作（复制、确定、开始）
ACCENT = "#FF7E6B"
ACCENT_DEEP = "#F0604B"

# ---------------- 状态色 ----------------
# 三个状态除了色相不同，还有亮度差，色觉障碍用户也能靠明暗分辨
OK = "#3BA55D"
WARN = "#E0A030"
DANGER = "#E5484D"
INFO = "#3E9EF0"

# ---------------- 浅色：深海奶油糖果 ----------------
LIGHT_BG = "#FFF6EA"        # 奶油暖白底
LIGHT_SURFACE = "#FFFFFF"   # 卡片面
LIGHT_SURFACE_2 = "#FFF1E0"  # 卡内次级块 / 输入框
LIGHT_LINE = "#F2DFC6"      # 极淡的分隔线
LIGHT_TEXT = "#1B2436"
LIGHT_MUTED = "#6B7488"

# ---------------- 深色：深夜海沟 ----------------
DARK_BG = "#0D1526"
DARK_SURFACE = "#16213A"
DARK_SURFACE_2 = "#1D2A47"
DARK_LINE = "#25334F"
DARK_TEXT = "#EDF2FF"
DARK_MUTED = "#94A3BF"

# ---------------- 形状 ----------------
RADIUS_CARD = 22      # 卡片圆角
RADIUS_CONTROL = 999  # 按钮 / 输入框：胶囊（Qt 会自动夹到半高）
RADIUS_CHIP = 12      # 小标签

# ---------------- 字体 ----------------
# 标题、数字、时间用随包分发的圆体；正文用系统字体（圆体正文可读性差）
FONT_TITLE = "ZCOOL KuaiLe"
FONT_FAMILY = "Microsoft YaHei UI"
FONT_MONO = "Consolas"
FONT_FILE = "assets/fonts/zcool-kuaile/ZCOOLKuaiLe-Regular.ttf"

# ---------------- 字号（像素） ----------------
SIZE_TITLE = 23
SIZE_HEADING = 16
SIZE_BODY = 13.5
SIZE_SMALL = 12.5
SIZE_CODE = 32        # 配对码

# ---------------- 间距 ----------------
GAP_XS = 4
GAP_S = 8
GAP_M = 12
GAP_L = 20
GAP_XL = 28

# 布局专用
CARD_PAD = 20        # 卡片内边距
CARD_GAP = 16        # 卡片间距
PAGE_BOTTOM = 24     # 滚动区底部安全距（避免最后一张卡被切）
SIDEBAR_W = 228      # 侧边栏宽度

# ---------------- 窗口 ----------------
# 参考 MAA 的量级：内容不多时窗口别撑得太大，960×700 一屏能看完首屏主要信息
WIN_W = 960
WIN_H = 700
MIN_W = 860
MIN_H = 600

# ---------------- 动效（与 motion.py / Motion.kt 保持一致） ----------------
# 时长单位毫秒。页面切换 220ms；按压 140ms；位移不超过内容宽度的 6%
MOTION_SWITCH_MS = 220
MOTION_ENTER_MS = 220
MOTION_TAP_MS = 140
MOTION_SLIDE_RATIO = 0.06

# ---------------- 三个游戏的配色与图标标识 ----------------
# 每个游戏有独立的主色，配合不同的图形，色相+形状双重区分。
GAME_STYLE = {
    "arknights": {
        "label": "明日方舟",
        "short": "方舟",
        "color": "#4A9E8F",   # 青绿：罗德岛的冷色调
        "accent": "#7FD1C1",
    },
    "genshin": {
        "label": "原神",
        "short": "原神",
        "color": "#E0A030",   # 金：风元素的暖色
        "accent": "#F5CE7A",
    },
    "starrail": {
        "label": "崩坏：星穹铁道",
        "short": "星铁",
        "color": "#7B5CFF",   # 紫：星空的颜色
        "accent": "#A78BFF",
    },
}

GAME_ORDER = ["arknights", "genshin", "starrail"]


def is_dark_default() -> bool:
    """电脑端默认跟随系统；系统读不到时按深色（截图更好看，也更省电）。"""
    return True

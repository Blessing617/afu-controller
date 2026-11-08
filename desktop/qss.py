"""电脑端 QSS：深海奶油糖果主题。

只生成样式表，不碰控件。调色板由 theme.palette() 提供，
数值来源是 tokens.py（与手机端 Theme.kt 一致）。
"""

from __future__ import annotations

from tokens import (
    ACCENT,
    BRAND,
    FONT_FAMILY,
    FONT_MONO,
    FONT_TITLE,
    RADIUS_CARD,
    RADIUS_CHIP,
    RADIUS_CONTROL,
    SIZE_BODY,
    SIZE_HEADING,
    SIZE_SMALL,
)


def build_qss(p: dict[str, str]) -> str:
    """p 是 theme.palette() 的结果（含 bg/surface/surface2/line/text/muted/brand/...）。"""
    return f"""
    * {{
        font-family: "{FONT_FAMILY}";
        font-size: {SIZE_BODY}px;
        outline: none;
    }}
    QWidget#Root, QWidget#PageBody {{
        background: {p['bg']};
        color: {p['text']};
    }}
    QStackedWidget {{
        background: {p['bg']};
    }}
    QScrollArea, QScrollArea > QWidget > QWidget {{
        background: {p['bg']};
        border: none;
    }}

    /* ---------- 侧边栏 ---------- */
    QWidget#Sidebar {{
        background: {p['sidebar']};
        border-right: 1px solid {p['line']};
    }}
    QLabel#Brand {{
        font-family: "{FONT_TITLE}";
        color: {p['text']};
        font-size: 16px;
    }}
    QLabel#BrandSub {{
        color: {p['muted']};
        font-size: 11px;
    }}
    QLabel#SideFoot {{
        color: {p['muted']};
        font-size: 11px;
    }}
    QPushButton#NavItem {{
        text-align: left;
        padding: 11px 14px;
        border: none;
        border-radius: 21px;
        color: {p['muted']};
        background: transparent;
        font-size: 14px;
    }}
    QPushButton#NavItem:hover {{
        background: {p['surface2']};
        color: {p['text']};
    }}
    QPushButton#NavItem:checked {{
        background: {p['nav_active_bg']};
        color: {p['nav_active_fg']};
        border: 1px solid {p['nav_active_line']};
        font-weight: bold;
    }}

    /* ---------- 页头 ---------- */
    QLabel#PageTitle {{
        font-family: "{FONT_TITLE}";
        color: {p['text']};
        font-size: 23px;
    }}
    QLabel#PageSub {{
        color: {p['muted']};
        font-size: {SIZE_SMALL}px;
    }}

    /* ---------- 卡片 ---------- */
    QFrame#Card {{
        background: {p['surface']};
        border: 1px solid {p['card_line']};
        border-radius: {RADIUS_CARD}px;
    }}
    QLabel#CardTitle {{
        font-family: "{FONT_TITLE}";
        color: {p['text']};
        font-size: {SIZE_HEADING}px;
    }}
    QLabel {{
        color: {p['text']};
    }}
    QLabel#Muted {{
        color: {p['muted']};
        font-size: {SIZE_SMALL}px;
    }}
    QLabel#Mono {{
        font-family: "{FONT_MONO}";
        color: {p['text']};
    }}
    QLabel#Addr {{
        font-family: "{FONT_MONO}";
        color: {p['text']};
        font-size: 19px;
    }}
    QLabel#Divider {{
        background: {p['line']};
        border: none;
    }}

    /* ---------- 按钮 ---------- */
    QPushButton {{
        background: {p['surface2']};
        color: {p['text']};
        border: 1px solid transparent;
        border-radius: {RADIUS_CONTROL}px;
        padding: 8px 16px;
        font-size: {SIZE_BODY}px;
    }}
    QPushButton:hover {{
        background: {p['surface2_hover']};
    }}
    QPushButton:pressed {{
        background: {p['line']};
    }}
    QPushButton:disabled {{
        color: {p['muted']};
        background: transparent;
        border-color: {p['line']};
    }}
    QPushButton#Primary {{
        background: {p['brand']};
        color: #ffffff;
        font-weight: bold;
        padding: 9px 20px;
    }}
    QPushButton#Primary:hover {{
        background: {p['brand_hover']};
    }}
    QPushButton#Accent {{
        background: {ACCENT};
        color: #ffffff;
        font-weight: bold;
    }}
    QPushButton#Danger {{
        background: transparent;
        color: {p['danger']};
        border: 1px solid {p['danger']};
    }}
    QPushButton#Danger:hover {{
        background: {p['danger']};
        color: #ffffff;
    }}
    QPushButton#Ghost {{
        background: transparent;
        color: {p['muted']};
        border: 1px dashed {p['line']};
    }}
    QPushButton#Chip {{
        background: {p['chip_bg']};
        color: {p['chip_fg']};
        border-radius: {RADIUS_CHIP}px;
        padding: 5px 11px;
        font-size: {SIZE_SMALL}px;
    }}

    /* ---------- 输入框 ---------- */
    QLineEdit {{
        background: {p['surface2']};
        color: {p['text']};
        border: 1px solid {p['line']};
        border-radius: {RADIUS_CONTROL}px;
        padding: 8px 14px;
        selection-background-color: {p['brand']};
    }}
    QLineEdit:focus {{
        border-color: {p['brand']};
    }}

    /* ---------- 滚动条 ---------- */
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {p['scroll']};
        border-radius: 5px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {p['muted']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}

    /* ---------- 其它 ---------- */
    QToolTip {{
        background: {p['surface']};
        color: {p['text']};
        border: 1px solid {p['line']};
        padding: 6px 10px;
        border-radius: 10px;
    }}
    QCheckBox {{
        color: {p['text']};
        spacing: 8px;
    }}
    """

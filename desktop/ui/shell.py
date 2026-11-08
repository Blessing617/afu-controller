"""电脑端主窗口：侧边栏导航 + 卡片式页面。

页面本身拆在 ui/overview.py、ui/deps.py、ui/settings.py，
图标资源在 ui/assets.py，通用控件在 ui/widgets.py。这里只留窗口骨架、
页面切换、信号接线与生命周期。

性能约定（见 .spec/specs/performance）：界面线程上不做任何阻塞调用，
Tailscale 查询与地址枚举都交给 backend 的后台线程。"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

import backend
from motion import PageSwitcher
from tokens import (
    CARD_GAP,
    CARD_PAD,
    FONT_MONO,
    GAME_ORDER,
    GAME_STYLE,
    GAP_L,
    GAP_M,
    GAP_S,
    GAP_XL,
    MIN_H,
    MIN_W,
    PAGE_BOTTOM,
    RADIUS_CARD,
    SIDEBAR_W,
    SIZE_CODE,
    WIN_H,
    WIN_W,
)
from theme import build_qss, palette, system_is_dark
from ui.candy import CandyFoldRow, CandyPill
from ui.widgets import StatusPill, _card, _clear_layout, _dot


from ui.assets import AssetsMixin, _is_admin, _log
from ui.deps import DepsPageMixin
from ui.overview import OverviewPageMixin
from ui.settings import SettingsPageMixin

NAV_ITEMS = [
    ("overview", "总览", "nav-overview"),
    ("deps", "依赖清单", "nav-deps"),
    ("settings", "设置", "nav-settings"),
]

class MainWindow(OverviewPageMixin, DepsPageMixin, SettingsPageMixin, AssetsMixin, QtWidgets.QMainWindow):
    """主窗口。页面方法由各个 mixin 提供。"""

    # 后台线程往界面线程传消息用（Qt 要求跨线程更新界面必须走信号）
    sig_service_state = QtCore.Signal(bool, str)
    sig_ready = QtCore.Signal(bool)
    sig_paths = QtCore.Signal(dict)
    sig_deps = QtCore.Signal(list)
    sig_deps_error = QtCore.Signal(str)
    # 请主线程去发起依赖检查（后台线程不能直接碰控件）
    sig_start_deps = QtCore.Signal()
    sig_redetect_done = QtCore.Signal()
    sig_code_refreshed = QtCore.Signal()
    # 连接信息快照（backend.ConnectionSnapshot），由后台采集线程发出
    sig_snapshot = QtCore.Signal(object)



    def __init__(self, host, data_dir: Path, fallback: bool, port_default: int) -> None:
        super().__init__()
        self.host = host
        self.data_dir = data_dir
        self.data_fallback = fallback
        self.port_default = port_default
        self._pages: dict[str, QtWidgets.QWidget] = {}
        self._nav_buttons: dict[str, QtWidgets.QPushButton] = {}
        self._nav_order: list[str] = [key for key, _, _ in NAV_ITEMS]
        self._current_page = "overview"
        self._busy = False
        self._running = False
        # 上一次渲染过的快照：数据没变就一行都不动，避免每 2 秒无谓重绘
        self._last_snapshot: backend.ConnectionSnapshot | None = None
        self._funnel_rendered = False

        self.setWindowTitle("阿福代肝控制器")
        # 窗口尺寸参考 MAA 的量级：内容不多时别撑满屏，
        # 960×700 刚好一屏看完首屏的服务、连接、游戏三张卡。
        self.resize(WIN_W, WIN_H)
        self.setMinimumSize(MIN_W, MIN_H)

        self._build_ui()
        self._apply_theme()

        # 后台采集器：起得早，界面不用等它。
        # 注意必须在 _wire_signals 之前建好——信号里要连接它的 refresh_now。
        self._collector = backend.ConnectionCollector(self.host.port, self.data_dir)
        self._collector.attach_emitter(self.sig_snapshot.emit)

        self._wire_signals()
        self._collector.start()

    def _build_ui(self) -> None:
        root = QtWidgets.QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)

        layout = QtWidgets.QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- 侧边栏：品牌 / 导航 / 底部三段，填满高度 ---
        side = QtWidgets.QWidget()
        side.setObjectName("Sidebar")
        side.setFixedWidth(SIDEBAR_W)
        side_layout = QtWidgets.QVBoxLayout(side)
        side_layout.setContentsMargins(14, 18, 14, 14)
        side_layout.setSpacing(6)

        brand_row = QtWidgets.QHBoxLayout()
        brand_row.setSpacing(10)
        logo = QtWidgets.QLabel()
        logo.setFixedSize(40, 40)
        self._logo_label = logo
        brand_col = QtWidgets.QVBoxLayout()
        brand_col.setSpacing(1)
        title = QtWidgets.QLabel("阿福代肝控制器")
        title.setObjectName("Brand")
        sub = QtWidgets.QLabel("手机一点，电脑全自动")
        sub.setObjectName("BrandSub")
        brand_col.addWidget(title)
        brand_col.addWidget(sub)
        brand_row.addWidget(logo)
        brand_row.addLayout(brand_col, 1)
        side_layout.addLayout(brand_row)
        side_layout.addSpacing(16)

        nav_wrap = QtWidgets.QVBoxLayout()
        nav_wrap.setSpacing(4)
        for key, label, icon_name in NAV_ITEMS:
            btn = QtWidgets.QPushButton(f"  {label}")
            btn.setObjectName("NavItem")
            btn.setCheckable(True)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setMinimumHeight(42)
            btn.setIconSize(QtCore.QSize(18, 18))
            btn.clicked.connect(lambda _=False, k=key: self.show_page(k))
            nav_wrap.addWidget(btn)
            self._nav_buttons[key] = btn
        side_layout.addLayout(nav_wrap)

        side_layout.addStretch(1)

        divider = QtWidgets.QLabel()
        divider.setObjectName("Divider")
        divider.setFixedHeight(1)
        side_layout.addWidget(divider)
        side_layout.addSpacing(8)

        self.version_label = QtWidgets.QLabel("v0.1.0 · 本地服务")
        self.version_label.setObjectName("SideFoot")
        self.version_label.setWordWrap(True)
        side_layout.addWidget(self.version_label)

        self.side_pill = CandyPill("正在检查地址", "#E0A030")
        side_layout.addWidget(self.side_pill)

        # 底部水波装饰：让侧边栏不是一块死白的板，同时不影响任何交互
        decor = QtWidgets.QLabel()
        decor.setFixedHeight(26)
        decor.setPixmap(self._decor_pixmap("decor-wave", SIDEBAR_W - 28, 26))
        side_layout.addWidget(decor)
        side_layout.addSpacing(2)

        layout.addWidget(side)

        # --- 内容区 ---
        self.stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.stack, 1)
        self._switcher = PageSwitcher(self.stack, self)

        # 页面懒构建：首屏只建总览，其余等用户真的点进去再建。
        # 启动时间与常驻内存都受益，切页也只是多几十毫秒的构建。
        self._page_builders = {
            "overview": self._build_overview,
            "deps": self._build_deps,
            "settings": self._build_settings,
        }
        self._ensure_page("overview")
        self.stack.setCurrentWidget(self._pages["overview"])
        self._nav_buttons["overview"].setChecked(True)

    def _ensure_page(self, key: str):
        """取页面；没建过就现在建，建过就直接返回。"""
        page = self._pages.get(key)
        if page is not None:
            return page
        builder = self._page_builders.get(key)
        if builder is None:
            return None
        page = builder()
        self._pages[key] = page
        self.stack.addWidget(page)
        return page

    def show_page(self, key: str) -> None:
        page = self._ensure_page(key)
        if page is None:
            return
        # 方向：新页在当前位置右侧就从右边进来，反之从左边进来
        try:
            old = self._nav_order.index(self._current_page)
            new = self._nav_order.index(key)
        except ValueError:
            old, new = 0, 0
        self._switcher.show(page, direction=1 if new >= old else -1)
        self._current_page = key
        for nav_key, btn in self._nav_buttons.items():
            btn.setChecked(nav_key == key)
        self._refresh_nav_icons()
        if key == "deps":
            self._load_deps_async()

    def _refresh_nav_icons(self) -> None:
        """导航图标要跟着主题与选中态换颜色，QSS 管不了 QIcon 的颜色。"""
        p = palette(self.dark)
        for key, label, icon_name in NAV_ITEMS:
            btn = self._nav_buttons.get(key)
            if btn is None:
                continue
            color = p["nav_active_fg"] if btn.isChecked() else p["muted"]
            btn.setIcon(self._nav_icon(icon_name, color, 18))

    def set_side_source(self, text: str, color: str) -> None:
        """侧边栏底部的地址来源徽标（公网固定 / 局域网 / 未就绪）。"""
        pill = getattr(self, "side_pill", None)
        if pill is not None:
            pill.set_state(text, color)

    def _scroll_page(self, title: str, subtitle: str):
        page = QtWidgets.QWidget()
        outer = QtWidgets.QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        # 不出现横向滚动条：内容要跟着窗口宽度走，
        # 否则窄窗口下右侧的标签/按钮会被推出可视区。
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        inner = QtWidgets.QWidget()
        body = QtWidgets.QVBoxLayout(inner)
        body.setContentsMargins(GAP_XL, GAP_L + 2, GAP_XL, PAGE_BOTTOM)
        body.setSpacing(CARD_GAP)

        head = QtWidgets.QWidget()
        head_layout = QtWidgets.QVBoxLayout(head)
        head_layout.setContentsMargins(0, 0, 0, 0)
        head_layout.setSpacing(3)
        heading = QtWidgets.QLabel(title)
        heading.setObjectName("PageTitle")
        head_layout.addWidget(heading)
        sub = QtWidgets.QLabel(subtitle)
        sub.setObjectName("PageSub")
        sub.setWordWrap(True)
        head_layout.addWidget(sub)
        body.addWidget(head)
        body.addSpacing(2)

        scroll.setWidget(inner)
        outer.addWidget(scroll)
        # 这里**不能**加 stretch：各页面是在本函数返回后才往 body 里 addWidget，
        # 先加 stretch 会让所有卡片被推到页面底部、上方留一大片空白。
        return page, body

    def _apply_theme(self) -> None:
        # 跟随系统主题；读不到就当深色
        self.dark = system_is_dark()
        self.setStyleSheet(build_qss(self.dark))
        if hasattr(self, "_logo_label"):
            self._logo_label.setPixmap(self._make_logo_pixmap(40))
        self._refresh_nav_icons()

    def _wire_signals(self) -> None:
        self.sig_service_state.connect(self._on_service_state)
        self.sig_ready.connect(self._on_ready)
        self.sig_paths.connect(self._apply_paths)
        self.sig_deps.connect(self._render_deps)
        self.sig_deps_error.connect(self._render_deps_error)
        self.sig_start_deps.connect(self._load_deps_async)
        self.sig_redetect_done.connect(self._on_redetect_done)
        self.sig_code_refreshed.connect(self._collector.refresh_now)
        self.sig_snapshot.connect(self._apply_snapshot)

        if hasattr(self, "btn_toggle"):
            self.btn_toggle.clicked.connect(self._on_toggle_service)
        if hasattr(self, "btn_check_deps"):
            self.btn_check_deps.clicked.connect(lambda: self._load_deps_async(force=True))
        if hasattr(self, "btn_redetect"):
            self.btn_redetect.clicked.connect(self._on_redetect)
        if hasattr(self, "btn_open_web"):
            self.btn_open_web.clicked.connect(self._on_open_web)
        if hasattr(self, "btn_open_help"):
            self.btn_open_help.clicked.connect(self._on_open_help)
        if hasattr(self, "btn_open_data"):
            self.btn_open_data.clicked.connect(self._on_open_data)
        if hasattr(self, "btn_refresh_code"):
            self.btn_refresh_code.clicked.connect(self._on_refresh_code)
        if hasattr(self, "btn_copy_addr"):
            self.btn_copy_addr.clicked.connect(self._on_copy_addr)

    def start_bootstrap(self) -> None:
        threading.Thread(target=self._bootstrap_worker, daemon=True).start()

    def _bootstrap_worker(self) -> None:
        ok = self.host.start()
        self.sig_ready.emit(ok)
        if not ok:
            return
        # 程序正常以管理员身份启动，这时能直接读到 Tailscale 的固定域名。
        # 先存下来，之后即使某些调用拿不到权限，界面也能显示正确地址。
        self._cache_funnel_domain()
        self.refresh_all()
        # 关键：这里在后台线程，不能直接调 _load_deps_async（它会改控件）。
        # 早先就是直接调，结果 Qt 在非主线程上改控件静默失败，
        # 总览页永远停在「正在检查外部软件…」（2026-11-08 复现）。
        self.sig_start_deps.emit()

    def refresh_all(self) -> None:
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self) -> None:
        try:
            from app.platform.discovery import detect_all

            paths = detect_all()
        except Exception as exc:  # noqa: BLE001
            paths = {}
            _log(f"探测失败：{exc}")
        self.sig_paths.emit(paths)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        # 有任务在跑时先问一句
        try:
            from app.core.state import RUNNER

            if RUNNER.current() is not None:
                ret = QtWidgets.QMessageBox.question(
                    self,
                    "阿福代肝控制器",
                    "有任务正在运行，确定要退出吗？",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                )
                if ret != QtWidgets.QMessageBox.Yes:
                    event.ignore()
                    return
        except Exception:  # noqa: BLE001
            pass
        try:
            self._collector.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.host.stop()
        except Exception:  # noqa: BLE001
            pass
        event.accept()

"""设置页：自动清理、重新探测、打开数据目录、关于。"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

import backend
from motion import PageSwitcher
from tokens import (
    FONT_MONO,
    GAME_ORDER,
    GAME_STYLE,
    GAP_L,
    GAP_M,
    GAP_S,
    RADIUS_CARD,
    SIZE_CODE,
)
from theme import build_qss, palette, system_is_dark
from ui.widgets import StatusPill, _card, _clear_layout, _dot


class SettingsPageMixin:
    """设置页：自动清理、重新探测、打开数据目录、关于。"""

    def _build_settings(self) -> QtWidgets.QWidget:
        page, body = self._scroll_page("设置", "常用操作与排查入口。")

        card, box = _card("工具")
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        self.btn_redetect = QtWidgets.QPushButton("重新探测游戏与工具")
        self.btn_redetect.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_open_web = QtWidgets.QPushButton("打开网页控制台")
        self.btn_open_web.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_open_help = QtWidgets.QPushButton("首次使用引导")
        self.btn_open_help.setCursor(QtCore.Qt.PointingHandCursor)
        row.addWidget(self.btn_redetect)
        row.addWidget(self.btn_open_web)
        row.addWidget(self.btn_open_help)
        row.addStretch(1)
        box.addLayout(row)
        body.addWidget(card)

        card, box = _card("数据")
        self.data_label = QtWidgets.QLabel(str(self.data_dir))
        self.data_label.setObjectName("Muted")
        self.data_label.setWordWrap(True)
        self.data_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        box.addWidget(self.data_label)
        if self.data_fallback:
            warn = QtWidgets.QLabel("程序目录不可写，数据已改存到上面的位置。")
            warn.setWordWrap(True)
            box.addWidget(warn)
        row = QtWidgets.QHBoxLayout()
        self.btn_open_data = QtWidgets.QPushButton("打开数据目录")
        self.btn_open_data.setCursor(QtCore.Qt.PointingHandCursor)
        row.addWidget(self.btn_open_data)
        row.addStretch(1)
        box.addLayout(row)
        body.addWidget(card)

        card, box = _card("关于")
        about = QtWidgets.QLabel(
            "阿福代肝控制器 · 把手机上的操作转给电脑上的自动化工具。\n"
            "本项目不修改游戏文件，风险请自行判断。"
        )
        about.setObjectName("Muted")
        about.setWordWrap(True)
        box.addWidget(about)
        body.addWidget(card)
        body.addStretch(1)
        return page

    def _on_ready(self, ok: bool) -> None:
        self._running = bool(ok)
        if ok:
            self.overview_service.set("服务运行中", palette(self.dark)["ok"])
            note = (
                "管理员权限：已获得" if _is_admin()
                else "管理员权限：未获得（任务可能无法操作游戏）"
            )
            if self.data_fallback:
                note += "　·　数据目录已改到用户目录"
            self.overview_note.setText(note)
        else:
            self.overview_service.set("启动失败", palette(self.dark)["danger"])
            self.overview_note.setText(getattr(self.host, "error", "") or "未知错误")

    def _on_service_state(self, running: bool, text: str) -> None:
        p = palette(self.dark)
        self.overview_service.set(text, p["ok"] if running else p["danger"])
        self.btn_toggle.setText("停止服务" if running else "启动服务")

    def _on_toggle_service(self) -> None:
        # 用显式状态位判断，别去猜 host.server 是否为 None：
        # 复用已有实例时 host.server 本来就是 None，但那不代表服务没在跑。
        if getattr(self, "_running", False):
            self.host.stop()
            self._running = False
            self._on_service_state(False, "服务已停止")
        else:
            threading.Thread(target=self._restart_worker, daemon=True).start()

    def _restart_worker(self) -> None:
        if self.host.start():
            self.sig_service_state.emit(True, "服务运行中")

    def _on_redetect(self) -> None:
        self.btn_redetect.setEnabled(False)
        self.btn_redetect.setText("正在探测…")

        def work() -> None:
            # 真正扫盘（慢），完成后用信号通知主线程恢复按钮
            self._refresh_worker()
            self.sig_redetect_done.emit()

        threading.Thread(target=work, daemon=True).start()

    def _on_redetect_done(self) -> None:
        self._load_deps_async(force=True)
        self.btn_redetect.setEnabled(True)
        self.btn_redetect.setText("重新探测游戏与工具")

    def _on_open_web(self) -> None:
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl(f"http://127.0.0.1:{self.host.port}/")
        )

    def _on_open_help(self) -> None:
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl(f"http://127.0.0.1:{self.host.port}/welcome")
        )

    def _on_open_data(self) -> None:
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self.data_dir)))

    def _on_copy_cmd(self) -> None:
        """复制 tailscale funnel 命令，省得用户手打。"""
        text = f"tailscale funnel --bg {self.host.port}"
        QtWidgets.QApplication.clipboard().setText(text)
        self.btn_copy_cmd.setText("已复制 ✓")
        QtCore.QTimer.singleShot(1500, lambda: self.btn_copy_cmd.setText("复制命令"))

    def _on_open_admin_ps(self) -> None:
        """打开一个**管理员身份**的 PowerShell 窗口，并把命令提示打出来。

        用 ShellExecuteW 的 runas 触发 UAC。用户点「是」之后弹出的窗口
        就是提权的，可以直接粘命令执行。
        """
        import ctypes

        cmd = f"tailscale funnel --bg {self.host.port}"
        inner = (
            "Write-Host '把下面这条命令粘贴进来，回车执行：' -ForegroundColor Cyan; "
            f"Write-Host '{cmd}' -ForegroundColor Yellow"
        )
        try:
            rc = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                "powershell.exe",
                f'-NoExit -Command "{inner}"',
                None,
                1,
            )
            if rc <= 32:
                # 用户取消了 UAC，或者系统不允许
                _log(f"打开管理员 PowerShell 失败（rc={rc}）")
        except Exception as exc:  # noqa: BLE001
            _log(f"打开管理员 PowerShell 异常：{exc}")

    def _on_copy_addr(self) -> None:
        """复制推荐地址到剪贴板，并给个「已复制」的即时反馈。

        为什么要这个按钮：地址是一长串字符，让用户手抄到手机上
        几乎必然出错（尤其是 https:// 和大小写）。
        """
        text = self.primary_addr.text()
        if not text or text in ("—", "正在获取…"):
            return
        QtWidgets.QApplication.clipboard().setText(text)
        self.btn_copy_addr.setText("已复制 ✓")
        QtCore.QTimer.singleShot(1500, lambda: self.btn_copy_addr.setText("复制地址"))

    def _on_refresh_code(self) -> None:
        """让服务端再生成一个配对码。

        注意：`/api/pair/refresh` 是需要 token 的（防止任意人换码），
        而桌面界面本身不持有 token。但服务端在「还没有任何设备配对」时
        会在每次 `/api/health` 里自动补发配对码，
        所以这里请求一次 health 就能拿到新码。

        修（2026-11）：这一段以前复制粘贴出两个一模一样的 `threading.Thread(...)`，
        每次点「换一个」会并发发两次请求。
        """
        self.btn_refresh_code.setEnabled(False)
        self.btn_refresh_code.setText("请求中…")

        def work() -> None:
            try:
                import urllib.request

                with urllib.request.urlopen(
                    f"http://127.0.0.1:{self.host.port}/api/health", timeout=5
                ):
                    pass
            except Exception:  # noqa: BLE001
                pass
            self.sig_code_refreshed.emit()

        threading.Thread(target=work, daemon=True).start()
        QtCore.QTimer.singleShot(600, self._reset_refresh_button)

    def _reset_refresh_button(self) -> None:
        self.btn_refresh_code.setEnabled(True)
        self.btn_refresh_code.setText("换一个")

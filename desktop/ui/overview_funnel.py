"""总览页的「公网固定地址」卡片：四步检查表 + 结果。

这一步用户最容易卡住，所以检查表要能指着「哪一步没做、去点哪儿」。
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

import backend
from theme import body_font, mono_font, palette
from tokens import GAP_S
from ui.candy import CandyButton, CandyPill
from ui.widgets import _card


class FunnelCardMixin:
    """公网固定地址卡。"""

    def _build_funnel_card(self) -> QtWidgets.QWidget:
        card, box = _card("公网固定地址（出门在外用这个）")
        p = palette(getattr(self, "dark", False))

        explain = QtWidgets.QLabel(
            "这个网址不是你编的，是做完下面四步后 Tailscale 给你的。"
            "做完之后它会自动显示在下面，手机直接填它就行。"
        )
        explain.setObjectName("Muted")
        explain.setWordWrap(True)
        box.addWidget(explain)
        box.addSpacing(GAP_S)

        self.step_reg = CandyPill("", "#888888")
        self.step_install = CandyPill("", "#888888")
        self.step_login = CandyPill("", "#888888")
        self.step_funnel = CandyPill("", "#888888")
        steps = QtWidgets.QVBoxLayout()
        steps.setSpacing(6)
        for pill in (self.step_reg, self.step_install, self.step_login, self.step_funnel):
            steps.addWidget(pill, 0, QtCore.Qt.AlignLeft)
        box.addLayout(steps)

        # ---- 怎么操作 ----
        box.addSpacing(GAP_S)
        guide = QtWidgets.QLabel("怎么操作")
        guide.setFont(body_font(13, bold=True))
        box.addWidget(guide)

        t1 = QtWidgets.QLabel(
            '① 注册账号：<a href="https://login.tailscale.com/start" '
            f'style="color:{p["brand"]};">打开注册页</a>'
            "（Google / GitHub / 微软账号直接登录）"
        )
        t1.setOpenExternalLinks(True)
        t1.setWordWrap(True)
        box.addWidget(t1)

        t2 = QtWidgets.QLabel(
            '② 下载安装：<a href="https://tailscale.com/download/windows" '
            f'style="color:{p["brand"]};">下载 Windows 版</a>（双击安装即可）'
        )
        t2.setOpenExternalLinks(True)
        t2.setWordWrap(True)
        box.addWidget(t2)

        t3 = QtWidgets.QLabel(
            "③ 登录：装完后看屏幕<b>右下角托盘区</b>（可能要点开 ^ 箭头）→ "
            "找到 Tailscale 图标 → 点它 →「<b>Log in</b>」→ 浏览器里点授权"
        )
        t3.setWordWrap(True)
        box.addWidget(t3)

        box.addSpacing(4)
        t4 = QtWidgets.QLabel(
            "④ 开启 Funnel：用<b>管理员身份</b>打开 PowerShell，粘贴执行下面这行"
        )
        t4.setWordWrap(True)
        box.addWidget(t4)

        cmd = QtWidgets.QLabel(f"tailscale funnel --bg {self.host.port}")
        cmd.setFont(mono_font(13))
        cmd.setWordWrap(True)
        cmd.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        # 注意：必须同时设 background 和 color。
        # 只设背景会让文字保持默认黑色，在深色卡片上完全看不见。
        cmd.setStyleSheet(
            f"background:{p['surface2']}; color:{p['text']};"
            "padding:9px 12px;border-radius:12px;"
        )
        box.addWidget(cmd)

        btn_row4 = QtWidgets.QHBoxLayout()
        btn_row4.setSpacing(10)
        self.btn_copy_cmd = CandyButton("复制命令", "soft")
        self.btn_copy_cmd.clicked.connect(self._on_copy_cmd)
        self.btn_admin_ps = CandyButton("打开管理员 PowerShell", "ghost")
        self.btn_admin_ps.clicked.connect(self._on_open_admin_ps)
        btn_row4.addWidget(self.btn_copy_cmd, 0)
        btn_row4.addWidget(self.btn_admin_ps, 0)
        btn_row4.addStretch(1)
        box.addLayout(btn_row4)

        tip4 = QtWidgets.QLabel(
            "执行时会弹浏览器让你<b>点一次授权</b>。完成后这个卡片会自动显示你的网址。"
        )
        tip4.setObjectName("Muted")
        tip4.setWordWrap(True)
        box.addWidget(tip4)

        box.addSpacing(GAP_S)
        self.funnel_state = CandyPill("检查中…", "#E0A030")
        state_row = QtWidgets.QHBoxLayout()
        state_row.addWidget(self.funnel_state, 0)
        state_row.addStretch(1)
        box.addLayout(state_row)

        self.funnel_url = QtWidgets.QLabel("—")
        self.funnel_url.setFont(mono_font(15, bold=True))
        self.funnel_url.setWordWrap(True)
        self.funnel_url.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        box.addWidget(self.funnel_url)

        self.funnel_note = QtWidgets.QLabel("")
        self.funnel_note.setObjectName("Muted")
        self.funnel_note.setWordWrap(True)
        box.addWidget(self.funnel_note)

        return card

    def _render_funnel(self, ts: backend.TailscaleState) -> None:
        p = palette(self.dark)
        ok, warn, bad, muted = p["ok"], p["warn"], p["danger"], p["muted"]

        # ① 注册账号：程序没法代劳，但要把链接直接给出来
        if ts.logged_in:
            self.step_reg.set("① 已注册并登录 Tailscale", ok)
        else:
            self.step_reg.set("① 注册 Tailscale 账号（免费，浏览器里做）", warn)

        # ② 安装
        if ts.installed:
            self.step_install.set("② 电脑已安装 Tailscale", ok)
        else:
            self.step_install.set("② 电脑还没装 Tailscale", bad)

        # ③ 登录
        if ts.logged_in:
            self.step_login.set("③ 已登录 Tailscale 账号", ok)
        elif ts.installed:
            self.step_login.set("③ 还没登录：点托盘图标 →「Log in」→ 浏览器里授权", bad)
        else:
            self.step_login.set("③ 登录（装好之后再登录）", muted)

        # ④ 开启 Funnel
        if ts.funnel_on:
            self.step_funnel.set("④ Funnel 已开启", ok)
        elif ts.no_permission:
            self.step_funnel.set("④ Funnel 状态读取需要管理员权限（当前不是）", warn)
        elif ts.installed and ts.logged_in:
            self.step_funnel.set(
                "④ 还没开启 Funnel：用管理员 PowerShell 执行一次 "
                f"tailscale funnel --bg {self.host.port}",
                bad,
            )
        else:
            self.step_funnel.set("④ 开启 Funnel（登录之后再做）", muted)

        # 结果区
        if ts.url:
            self.funnel_state.set("你的固定地址", ok)
            self.funnel_url.setText(ts.url)
            note = "这个地址固定不变，手机上填它就行，手机端不用装任何软件。"
            if ts.port and ts.port != self.host.port:
                note = (
                    f"注意：Funnel 转发到 {ts.port}，但本程序服务在 "
                    f"{self.host.port}。请在管理员 PowerShell 里执行："
                    f"tailscale funnel reset 然后 "
                    f"tailscale funnel --bg {self.host.port}"
                )
            self.funnel_note.setText(note)
            return

        self.funnel_url.setText("—")
        if not ts.installed:
            self.funnel_state.set("还没装 Tailscale，暂时拿不到固定地址", muted)
            self.funnel_note.setText(
                "下载地址：https://tailscale.com/download/windows\n"
                "装好、登录、再开启一次 Funnel，这个卡片就会显示你的网址。"
            )
        elif not ts.logged_in:
            self.funnel_state.set("还没登录 Tailscale", warn)
            self.funnel_note.setText(
                "点屏幕右下角托盘里的 Tailscale 图标 →「Log in」，"
                "浏览器里用你注册的账号授权。登录完这里会自动刷新。"
            )
        elif ts.no_permission:
            self.funnel_state.set("看不到 Funnel 地址（需要管理员权限）", warn)
            self.funnel_note.setText(
                "本程序以管理员身份运行时才能读到。"
                "请关掉它，右键 exe →「以管理员身份运行」。"
            )
        else:
            self.funnel_state.set("还没开启 Funnel，所以还没有地址", warn)
            self.funnel_note.setText(
                "在管理员 PowerShell 里执行一次（只需一次，之后一直有效）：\n"
                f"tailscale funnel --bg {self.host.port}\n"
                "执行时浏览器会让你点一次授权，完成后这里会显示你的网址。"
            )

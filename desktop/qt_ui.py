"""电脑端主窗口（PySide6 / Qt）—— 兼容入口。

实现已按职责拆到 `ui/` 包：

- `ui/shell.py`      窗口骨架、导航、页面切换、信号接线
- `ui/overview.py`   总览页（服务状态 / 手机连接信息 / 游戏可用性）
- `ui/deps.py`       依赖清单页
- `ui/settings.py`   设置页
- `ui/assets.py`     图标与资源
- `ui/widgets.py`    通用控件（卡片、状态点、状态胶囊）

保留这个名字是因为 main.py 与打包配置都按 `qt_ui.MainWindow` 引用。
"""

from __future__ import annotations

from ui.shell import MainWindow

__all__ = ["MainWindow"]

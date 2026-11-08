# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置。

注意：这里**不能写绝对路径**——换台机器、换个目录就打包失败，
而本项目是要开源的。所有路径都基于本 spec 文件所在位置推算。
"""
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = Path(SPEC_FILE_DIR := os.path.dirname(os.path.abspath(SPEC))).resolve()
PROJECT_ROOT = SPEC_DIR.parent          # desktop/ 的上一级
SERVER_DIR = PROJECT_ROOT / "server"
STATIC_DIR = SERVER_DIR / "app" / "static"


def _existing(*paths: Path) -> list[tuple[str, str]]:
    """只带上真实存在的文件，缺了也不让打包直接失败（会给出提示）。"""
    out = []
    for path in paths:
        if path.is_file():
            out.append((str(path), "."))
        else:
            print(f"[spec] 警告：找不到 {path}，已跳过")
    return out


hiddenimports = []
hiddenimports += collect_submodules('app')
# PIL 只用到这几块：截图（Image/frombuffer）、缩放、JPEG 编码。
# 早先是 collect_submodules('PIL') 全量带入（约 13MB，含一堆用不到的格式插件）。
hiddenimports += [
    'PIL.Image',
    'PIL.ImageFile',
    'PIL.ImageMode',
    'PIL.ImagePalette',
    'PIL.JpegImagePlugin',
    'PIL._imaging',
]
# 界面层（后台采集器 backend 与切页动效 motion 也在这一层）
hiddenimports += ['qt_ui', 'theme', 'tokens', 'backend', 'motion']
# 界面按职责拆成了 ui 包（shell / overview / deps / settings / assets / widgets）
hiddenimports += collect_submodules('ui')
# 网页控制台与引导页要用到静态文件服务
hiddenimports += ['uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto']
# Qt 渲染 SVG 图标需要 QtSvg（在 PySide6-Addons 里，不是 Essentials）
hiddenimports += ['PySide6.QtSvg']

datas = []
# 公网访问只用 Tailscale Funnel（固定地址），不再打包 cloudflared。
# 早先集成过 cloudflared 临时隧道，但地址每次重启都变，会把用户带偏，已整体移除。
# 网页控制台 / 引导页（离线自包含，必须随包）
if STATIC_DIR.is_dir():
    datas.append((str(STATIC_DIR), "app/static"))
else:
    print(f"[spec] 警告：找不到静态目录 {STATIC_DIR}，网页控制台将不可用")

# swagger 文档的本地资源（不装就是 CDN，国内会白屏）
try:
    import swagger_ui_bundle

    datas.append((str(swagger_ui_bundle.swagger_ui_path), "swagger_ui_bundle/vendor/swagger-ui"))
except Exception:
    print("[spec] 警告：未安装 swagger_ui_bundle，文档页将退回 CDN 地址")

# 启动画面/图标：有就用，没有用默认
icon_file = SPEC_DIR / "icon.ico"
if icon_file.is_file():
    datas.append((str(icon_file), "."))

# 界面里渲染游戏图标要用到 SVG 源文件（与手机端同一套）
assets_fonts = PROJECT_ROOT / "assets" / "fonts"
if assets_fonts.is_dir():
    datas.append((str(assets_fonts), "assets/fonts"))
else:
    print(f"[spec] 警告：找不到 {assets_fonts}，标题会退回系统字体")

assets_icons = PROJECT_ROOT / "assets" / "icons"
if assets_icons.is_dir():
    datas.append((str(assets_icons), "assets/icons"))
else:
    print(f"[spec] 警告：找不到 {assets_icons}，界面里的游戏图标会退化成文字")


a = Analysis(
    [str(SPEC_DIR / "main.py")],
    pathex=[str(SERVER_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 界面已改用 Qt：tkinter 相关全部不要（能省下 4MB 左右的 tcl/tk 数据）
    # PySide6 里与本项目无关的大块也一并排除。
    excludes=[
        'tkinter',
        # PIL 里用不到的部分（ImageTk/ImageQt 需要 GUI 绑定，ImageShow 是调试用的）
        'PIL.ImageTk',
        'PIL.ImageQt',
        'PIL.ImageShow',
        'PIL.ImageGrab',
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtQuick3D',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DRender',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtMultimedia',
        'PySide6.QtCharts',
        'PySide6.QtDataVisualization',
        'PySide6.QtBluetooth',
        'PySide6.QtNfc',
        'PySide6.QtPositioning',
        'PySide6.QtSerialPort',
        'PySide6.QtDesigner',
        'PySide6.QtHelp',
        'PySide6.QtTest',
        'PySide6.QtDBus',
        'PySide6.QtSql',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# Qt 的 binaries 过滤：
# - opengl32sw.dll 是软件 OpenGL 兜底（约 20MB），本项目只用 QWidget 绘制，不需要
# - Quick / Qml / Pdf 等模块在 excludes 里挡住了 Python 绑定，但它们的 DLL 仍会被 hook 带进来
_UNUSED_QT = (
    'opengl32sw.dll',
    'qt6quick', 'qt6qml', 'qt6pdf', 'qt6virtualkeyboard',
    'qt6network', 'qt6sql', 'qt6test', 'qt6dbus', 'qt6designer',
    'qt6opengl', 'qt6charts', 'qt6datavisualization', 'qt6multimedia',
    'qt6positioning', 'qt6bluetooth', 'qt6nfc', 'qt6serialport',
    'qt6websockets', 'qt6webengine', 'qt6texttospeech',
)
a.binaries = [
    item for item in a.binaries
    if not any(tag in item[0].lower() for tag in _UNUSED_QT)
]
a.datas = [
    item for item in a.datas
    if not any(tag in item[0].lower() for tag in _UNUSED_QT)
]

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='阿福代肝控制器',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    # 直接在清单里声明「需要管理员」：Windows 启动时就弹一次 UAC，
    # 不再走「先普通启动、再 runas 重启自己」那条路（那条路会弹两次提示）。
    uac_admin=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_file) if icon_file.is_file() else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='阿福代肝控制器',
)

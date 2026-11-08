"""Win32 GDI 取屏：把屏幕上一块区域读成 PIL 图像。

只做「读像素」这一件事，不做缩放、不做编码、不决定截哪儿——
那些在 `capture.py`。这样拆是因为 ctypes 的声明又长又机械，
和业务流程混在一起会让人以为它们是同一件事。

实测：1920×1080 区域 BitBlt + GetDIBits 约 20ms 量级。
注意不用 `PIL.ImageGrab.grab(bbox=...)`：它会先把整个屏幕抓下来再裁剪，
同样的区域要 300ms。
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import NamedTuple

from PIL import Image

SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0

# 整屏像素缓冲复用：2560×1600 的一张图是 16MB，每张都新建既慢又会让内存来回跳。
# 只在需要更大时才重新分配，取用期间由 _BUF_LOCK 串行化。
_BUF_LOCK = threading.Lock()
_BUF: ctypes.Array | None = None


def _scratch(size: int):
    global _BUF
    if _BUF is None or len(_BUF) < size:
        _BUF = ctypes.create_string_buffer(size)
    return _BUF

_user32 = ctypes.windll.user32
_gdi32 = ctypes.windll.gdi32

_user32.GetDC.argtypes = [wintypes.HWND]
_user32.GetDC.restype = wintypes.HDC
_user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
_user32.ReleaseDC.restype = ctypes.c_int

_gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
_gdi32.CreateCompatibleDC.restype = wintypes.HDC
_gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
_gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
_gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
_gdi32.SelectObject.restype = wintypes.HGDIOBJ
_gdi32.BitBlt.argtypes = [
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.DWORD,
]
_gdi32.BitBlt.restype = wintypes.BOOL
_gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
_gdi32.DeleteObject.restype = wintypes.BOOL
_gdi32.DeleteDC.argtypes = [wintypes.HDC]
_gdi32.DeleteDC.restype = wintypes.BOOL
_gdi32.GetDIBits.argtypes = [
    wintypes.HDC,
    wintypes.HBITMAP,
    wintypes.UINT,
    wintypes.UINT,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.UINT,
]
_gdi32.GetDIBits.restype = ctypes.c_int
_gdi32.GetDeviceCaps.argtypes = [wintypes.HDC, ctypes.c_int]
_gdi32.GetDeviceCaps.restype = ctypes.c_int


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class CaptureError(Exception):
    """截图失败：带错误码与人话文案，接口层直接转成 JSON。"""

    def __init__(self, code: str, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


class CaptureResult(NamedTuple):
    data: bytes
    width: int
    height: int
    quality: int
    elapsed_ms: float
    captured_at: str


def grab_screen_rect(left: int, top: int, width: int, height: int) -> Image.Image:
    """直接截屏幕上指定的区域（GDI BitBlt），不做整屏截取。"""
    screen_dc = _user32.GetDC(None)
    if not screen_dc:
        raise CaptureError("capture_failed", "无法获取屏幕画面句柄", 500)

    mem_dc = _gdi32.CreateCompatibleDC(screen_dc)
    if not mem_dc:
        _user32.ReleaseDC(None, screen_dc)
        raise CaptureError("capture_failed", "创建截图缓冲区失败", 500)

    bitmap = _gdi32.CreateCompatibleBitmap(screen_dc, width, height)
    if not bitmap:
        _gdi32.DeleteDC(mem_dc)
        _user32.ReleaseDC(None, screen_dc)
        raise CaptureError("capture_failed", "创建截图位图失败", 500)

    old = _gdi32.SelectObject(mem_dc, bitmap)
    try:
        if not _gdi32.BitBlt(mem_dc, 0, 0, width, height, screen_dc, left, top, SRCCOPY):
            raise CaptureError("capture_failed", "屏幕截图失败（BitBlt）", 500)

        header = _BITMAPINFOHEADER()
        header.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        header.biWidth = width
        header.biHeight = -height          # 负数 = 自上而下，省一次翻转
        header.biPlanes = 1
        header.biBitCount = 32
        header.biCompression = 0           # BI_RGB

        info = _BITMAPINFO()
        info.bmiHeader = header

        stride = width * 4
        with _BUF_LOCK:
            buf = _scratch(stride * height)
            if not _gdi32.GetDIBits(
                mem_dc, bitmap, 0, height, buf, ctypes.byref(info), DIB_RGB_COLORS
            ):
                raise CaptureError("capture_failed", "读取屏幕像素失败", 500)
            # frombuffer 拿到的是缓冲视图，convert("RGB") 在这一步拷贝出新图，
            # 之后复用同一块缓冲不会影响已经返回的图像。
            return Image.frombuffer(
                "RGBA", (width, height), buf.raw, "raw", "BGRA", stride, 1
            ).convert("RGB")
    finally:
        _gdi32.SelectObject(mem_dc, old)
        _gdi32.DeleteObject(bitmap)
        _gdi32.DeleteDC(mem_dc)
        _user32.ReleaseDC(None, screen_dc)


def desktop_size() -> tuple[int, int]:
    """物理分辨率（不乘 DPI 缩放，直接问系统要真实像素）。"""
    hdc = _user32.GetDC(None)
    if not hdc:
        return (1920, 1080)
    try:
        width = _gdi32.GetDeviceCaps(hdc, 118)   # DESKTOPHORZRES
        height = _gdi32.GetDeviceCaps(hdc, 117)  # DESKTOPVERTRES
        if width > 0 and height > 0:
            return (int(width), int(height))
    finally:
        _user32.ReleaseDC(None, hdc)
    return (1920, 1080)


def grab_fullscreen() -> Image.Image:
    """直接截整个屏幕。

    不猜窗口位置、不算 DPI、不裁标题栏——「屏幕上显示什么就截什么」，
    不会出现白屏、截错窗口、只截到一半这类问题。
    """
    width, height = desktop_size()
    return grab_screen_rect(0, 0, width, height)

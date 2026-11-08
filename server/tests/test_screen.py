"""画面接口的行为测试。

窗口相关的东西全部用 monkeypatch 假造：这些测试要能在没有游戏运行的机器上通过，
真实的 BitBlt 由 `_tmp` 压力脚本在真窗口上验证。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.platform import capture as cap
from app.platform import window as win
from app.platform.window import GameWindow


@pytest.fixture()
def client(monkeypatch):
    """已配对状态下的客户端（跳过 token 校验）。"""
    from app.core import auth
    from app.main import app

    monkeypatch.setattr(auth, "token_valid", lambda token: True)
    return TestClient(app)


@pytest.fixture()
def fake_window(monkeypatch):
    """假装游戏窗口存在（未最小化）。"""

    def _install(width: int = 800, height: int = 600, minimized: bool = False):
        monkeypatch.setattr(
            win,
            "find_game_window",
            lambda game: GameWindow(
                hwnd=1,
                title="fake",
                left=0,
                top=0,
                width=width,
                height=height,
                minimized=minimized,
            ),
        )

    return _install


@pytest.fixture()
def fake_grab(monkeypatch):
    """假装抓图成功，返回一张指定颜色的图。"""

    def _install(color=(40, 80, 120)):
        monkeypatch.setattr(
            cap,
            "grab_fullscreen",
            lambda: Image.new("RGB", (1920, 1080), color),
        )

    return _install


def test_unknown_game_returns_404(client):
    resp = client.get("/api/screen/minecraft")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "unknown_game"
    assert "minecraft" in body["message"]
    # 顶层结构：不能是 FastAPI 默认的 {"detail": {...}}，否则 APP 拿不到 message
    assert "detail" not in body




def test_success_returns_jpeg_with_metadata(client, fake_window, fake_grab):
    fake_window(width=1920, height=1080)
    fake_grab(color=(200, 60, 40))
    resp = client.get("/api/screen/genshin")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.headers["cache-control"] == "no-store"

    # 1080p 缩到 1280 宽（等比，1080×1280/1920 = 720）
    assert resp.headers["x-image-width"] == "960"
    assert resp.headers["x-image-height"] == "540"
    assert float(resp.headers["x-capture-ms"]) >= 0
    assert "T" in resp.headers["x-captured-at"]

    image = Image.open(__import__("io").BytesIO(resp.content))
    assert image.format == "JPEG"
    assert image.size == (960, 540)



def test_quality_is_clamped(client, fake_window, fake_grab):
    fake_window(width=640, height=480)
    fake_grab()
    for value, expected in ((0, 30), (999, 90), (70, 70), (-5, 30)):
        assert cap.clamp_quality(value) == expected
    # 越界也不报错，仍然返回图片
    assert client.get("/api/screen/genshin?quality=999").status_code == 200
    assert client.get("/api/screen/genshin?quality=0").status_code == 200


def test_non_integer_quality_is_rejected(client, fake_window, fake_grab):
    fake_window()
    fake_grab()
    assert client.get("/api/screen/genshin?quality=abc").status_code == 422


def test_unpaired_request_is_401(monkeypatch):
    from app.main import app

    monkeypatch.setattr(__import__("app.core.auth", fromlist=["x"]), "token_valid", lambda token: False)
    client = TestClient(app)
    resp = client.get("/api/screen/genshin")
    assert resp.status_code == 401
    assert resp.headers["content-type"] == "application/json"
    assert b"\xff\xd8" not in resp.content  # 不能泄露任何图像字节


def test_capture_failure_is_wrapped(client, fake_window, monkeypatch):
    fake_window()

    def _boom():
        raise RuntimeError("gdi 炸了")

    monkeypatch.setattr(cap, "grab_fullscreen", _boom)
    resp = client.get("/api/screen/genshin")
    assert resp.status_code == 500
    assert resp.json()["error"] == "capture_failed"





def test_black_capture_is_rejected(client, fake_window, fake_grab):
    fake_window()
    fake_grab(color=(0, 0, 0))
    resp = client.get("/api/screen/genshin")
    assert resp.status_code == 409
    assert resp.json()["error"] == "capture_black"




# ---------------- 三个游戏走同一路径（2026-11 变更） ----------------
def test_arknights_uses_same_capture_path(client, fake_grab, monkeypatch):
    """方舟不再走 ADB：给它和原神同一张假图，产物必须逐字节一致。"""
    fake_grab(color=(90, 160, 220))
    a = client.get("/api/screen/arknights")
    b = client.get("/api/screen/genshin")
    assert a.status_code == 200 and b.status_code == 200
    assert a.content == b.content
    assert a.headers["x-image-width"] == b.headers["x-image-width"]


def test_capture_module_has_no_adb_branch():
    """实现层不允许再退回外部通道。"""
    for name in ("_find_adb", "_adb_serial", "_grab_via_adb", "_ADB_SERIAL_CACHE"):
        assert not hasattr(cap, name), f"capture 里还残留 {name}"
    source = open(cap.__file__, encoding="utf-8").read()
    assert "import subprocess" not in source

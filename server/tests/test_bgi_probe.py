"""原神外部访问服务的探测测试。

关键约束：**探测失败必须静默**，不能因为对方版本旧就报错或拖慢启动。
"""

from __future__ import annotations

import json
from pathlib import Path

from app.engine.bgi_probe import describe, probe


def _make_install(tmp_path: Path, access: dict | None) -> Path:
    exe = tmp_path / "BetterGI.exe"
    exe.write_bytes(b"")
    user = tmp_path / "User"
    user.mkdir()
    config = {} if access is None else {"ExternalAccessConfig": access}
    (user / "config.json").write_text(json.dumps(config), encoding="utf-8")
    return exe


def test_old_version_has_no_service(tmp_path: Path):
    """0.66.0 的实际情况：config 里根本没有 ExternalAccessConfig。"""
    exe = _make_install(tmp_path, None)
    assert probe(exe) is None
    assert "没有状态接口" in describe(exe)


def test_disabled_service_is_skipped(tmp_path: Path):
    exe = _make_install(tmp_path, {"HttpApiEnabled": False, "WebSocketEnabled": False})
    assert probe(exe) is None


def test_enabled_but_unreachable_is_silent(tmp_path: Path):
    """开关打开但端口没起来（比如服务还没启动）：同样返回 None，不抛异常。"""
    exe = _make_install(
        tmp_path, {"HttpApiEnabled": True, "Port": 1, "AccessToken": "x"}
    )
    assert probe(exe) is None
    assert "没有状态接口" in describe(exe)


def test_missing_config_is_not_an_error(tmp_path: Path):
    exe = tmp_path / "BetterGI.exe"
    exe.write_bytes(b"")
    assert probe(exe) is None

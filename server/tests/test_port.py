"""端口自适应测试。

背景：旧代码把 8765 写死，端口被占就直接「服务启动超时」，换台机器就起不来。
"""

import socket

import pytest

from app.core import config


@pytest.fixture
def hold_port():
    """占住一个端口，退出测试时自动释放。"""
    held = []

    def _hold(port: int, host: str = "0.0.0.0"):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((host, port))
        sock.listen(1)
        held.append(sock)
        return sock

    yield _hold
    for sock in held:
        sock.close()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("0.0.0.0", 0))
        return sock.getsockname()[1]


def test_空闲端口可以绑定():
    port = _free_port()
    assert config.port_is_free(port) is True


def test_被占用时识别为不可用(hold_port):
    port = _free_port()
    hold_port(port)
    assert config.port_is_free(port) is False


def test_只监听回环的占用也要识别(hold_port):
    """回归：Windows 上 0.0.0.0 与 127.0.0.1 互不冲突，只测一个会漏判。"""
    port = _free_port()
    hold_port(port, host="127.0.0.1")
    assert config.port_is_free(port) is False


def test_首选端口被占时自动往后找一个(hold_port):
    port = _free_port()
    hold_port(port)
    picked = config.pick_port(port)
    assert picked != port
    assert picked > port
    assert config.port_is_free(picked)


def test_首选空闲时保持原样():
    port = _free_port()
    assert config.pick_port(port) == port

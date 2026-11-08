"""探测 BetterGI 的「外部访问服务」（较新版本才有）。

背景
----
用户装的 0.66.0 **没有**对外接口：`User/config.json` 里没有 `ExternalAccessConfig`，
安装目录里也没有 Kestrel/AspNetCore 依赖。较新版本才提供 loopback 上的

- `GET /api/v1/health`（需要 `Authorization: Bearer <token>`）
- `ws://127.0.0.1:<port>/ws/v1/logs`（实时日志）

而且官方文档写得很清楚：**不提供任务启动、停止等业务控制能力**，默认还是关的。

所以这里的定位是「有就用，没有就静默退回读日志」——绝不因为探测失败而报错或阻塞。
探测结果只用来做两件事：日志里说明判定依据；将来接日志推送时少走一次文件轮询。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_PORT = 30648
TIMEOUT = 2.0


def _read_config(exe: Path) -> dict:
    path = exe.parent / "User" / "config.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def probe(exe: str | Path) -> dict | None:
    """探测外部访问服务。

    返回 `{"base_url", "port", "token", "version"}`；不可用时返回 None。
    任何异常都吞掉——探测失败不该影响任务启动。
    """
    exe = Path(exe)
    config = _read_config(exe)
    access = config.get("ExternalAccessConfig") or {}
    if not isinstance(access, dict):
        return None

    http_on = bool(access.get("HttpApiEnabled"))
    ws_on = bool(access.get("WebSocketEnabled"))
    if not (http_on or ws_on):
        return None

    port = int(access.get("Port") or DEFAULT_PORT)
    token = str(access.get("AccessToken") or "")
    base = f"http://127.0.0.1:{port}"

    req = urllib.request.Request(base + "/api/v1/health")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        data = json.loads(body)
    except (urllib.error.URLError, OSError, ValueError):
        return None

    if not isinstance(data, dict):
        return None
    return {
        "base_url": base,
        "port": port,
        "token": token,
        "version": str(data.get("version") or ""),
        "websocket": ws_on,
    }


def describe(exe: str | Path) -> str:
    """给任务日志用的一句话说明。"""
    info = probe(exe)
    if info is None:
        return "该版本的 BetterGI 没有状态接口，按日志判断"
    version = f" v{info['version']}" if info.get("version") else ""
    extra = "（含日志推送）" if info.get("websocket") else ""
    return f"检测到 BetterGI 外部访问服务{version}，可用：{info['base_url']}{extra}"

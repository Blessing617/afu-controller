"""配置 mtime 缓存的正确性测试。

缓存能省掉每次请求的 JSON 解析，但绝不能因此读到旧值，
也不能把调用方改过的对象留在缓存里。
"""

from __future__ import annotations

import importlib
import json
import time
from pathlib import Path


def _reload_config(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ORCH_DATA_DIR", str(tmp_path))
    import app.core.config as cfg

    return importlib.reload(cfg)


def test_cache_sees_external_change(tmp_path, monkeypatch):
    cfg = _reload_config(tmp_path, monkeypatch)
    first = cfg.load_config()
    first["port"] = 9001
    cfg.save_config(first)

    # 外部直接改文件（模拟用户手改），mtime 变了就应读到新值
    path = Path(cfg.CONFIG_FILE)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["port"] = 9002
    time.sleep(0.01)
    path.write_text(json.dumps(data), encoding="utf-8")

    assert cfg.load_config()["port"] == 9002


def test_returned_object_is_a_copy(tmp_path, monkeypatch):
    cfg = _reload_config(tmp_path, monkeypatch)
    a = cfg.load_config()
    a["paths"]["genshin"] = "改坏了"
    b = cfg.load_config()
    assert b["paths"]["genshin"] == "", "缓存的配置被调用方改脏了"


def test_save_invalidates_cache(tmp_path, monkeypatch):
    cfg = _reload_config(tmp_path, monkeypatch)
    data = cfg.load_config()
    data["port"] = 9123
    cfg.save_config(data)
    assert cfg.load_config()["port"] == 9123

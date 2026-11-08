"""启动前置检查的提示文案测试。

要求：缺依赖时必须写明「缺的是哪一项」和「去哪下载」，
不能像以前那样只丢一句「未找到 XXX，请先在设置中指定路径」。

搬迁后这段逻辑在 `core/tasks.py`（api 只负责翻译成 HTTP 状态码），
所以这里测的是领域异常 `PrecheckError`，不是 `HTTPException`。
"""

import pytest

from app.core import tasks
from app.platform.discovery import KEYS

def _all_found():
    return {key: {"found": True, "path": f"F:/{key}.exe"} for key in KEYS}


@pytest.fixture
def fake_paths(monkeypatch):
    """可控的探测结果。"""

    def _apply(data):
        monkeypatch.setattr(tasks, "detect_all", lambda *a, **k: data)

    return _apply


def _detail(exc: tasks.PrecheckError) -> dict:
    return {
        "error": exc.error,
        "message": exc.message,
        "missing": [m["id"] for m in exc.missing_items],
        "missing_items": exc.missing_items,
    }


def test_缺_MAA_时提示包含名称和官网(fake_paths):
    data = _all_found()
    data["maa"] = {"found": False, "path": ""}
    fake_paths(data)

    with pytest.raises(tasks.PrecheckError) as info:
        tasks.precheck("arknights")

    detail = _detail(info.value)
    assert detail["error"] == "missing_path"
    assert "MAA" in detail["message"]
    assert "https://maa.plus/" in detail["message"]
    assert detail["missing"] == ["maa"]


def test_缺游戏本体时只报真正缺的那一项(fake_paths):
    data = _all_found()
    data["genshin"] = {"found": False, "path": ""}  # BetterGI 仍在
    fake_paths(data)

    with pytest.raises(tasks.PrecheckError) as info:
        tasks.precheck("genshin")

    detail = _detail(info.value)
    assert detail["missing"] == ["genshin"]
    assert "《原神》" in detail["message"]
    # 不能把已经装好的 BetterGI 也说成缺失
    assert "bettergi" not in detail["missing"]


def test_都就绪时放行(fake_paths):
    fake_paths(_all_found())
    paths = tasks.precheck("starrail")
    assert paths["starrail"]["found"] is True


def test_缺多项时全部列出(fake_paths):
    data = _all_found()
    data["maa"] = {"found": False, "path": ""}
    data["mumu"] = {"found": False, "path": ""}
    fake_paths(data)

    with pytest.raises(tasks.PrecheckError) as info:
        tasks.precheck("arknights")

    detail = _detail(info.value)
    assert set(detail["missing"]) == {"maa", "mumu"}
    names = [m["name"] for m in detail["missing_items"]]
    assert any("MAA" in n for n in names)
    assert any("MuMu" in n for n in names)

"""依赖清单的单元测试：这是桌面、手机、README 三处共享的事实源，不能出错。"""

from app.core import deps
from app.platform.discovery import KEYS


def test_清单包含全部六项():
    """公网访问只有 Tailscale Funnel 一条路，cloudflared 已整体移除。"""
    ids = [item["id"] for item in deps.DEPS]
    assert ids == [
        "genshin",
        "bettergi",
        "starrail",
        "m7a",
        "mumu",
        "maa",
    ]


def test_不再包含_cloudflared():
    """回归：cloudflared 的临时地址会误导用户，不该再出现在依赖清单里。"""
    ids = [item["id"] for item in deps.DEPS]
    assert "cloudflared" not in ids


def test_所有官网链接都是_https():
    for item in deps.DEPS:
        assert item["url"].startswith("https://"), f"{item['id']} 的链接不是 https"


def test_都对应真实探测_key():
    for item in deps.DEPS:
        assert item["probe_key"] in KEYS, f"{item['id']} 的 probe_key 不在探测范围内"


def test_每个游戏声明的依赖都存在():
    for game, info in deps.GAMES.items():
        for dep_id in info["requires"]:
            assert deps.get_dep(dep_id) is not None, f"{game} 依赖了不存在的 {dep_id}"


def test_每项依赖至少被一个游戏用到():
    used = set()
    for info in deps.GAMES.values():
        used.update(info["requires"])
    for item in deps.DEPS:
        assert item["id"] in used, f"{item['id']} 没有任何游戏用到，可能是多余项"


def test_缺失说明包含名称和链接而不是只说未找到():
    empty_paths = {key: {"found": False, "path": ""} for key in KEYS}
    text = deps.describe_missing("arknights", empty_paths)
    assert "MAA" in text
    assert "https://maa.plus/" in text
    # 不能是光秃秃的一句「未找到」
    assert len(text) > 20


def test_只报告真正缺失的那一项():
    # 装了 BetterGI 但没装原神
    paths = {
        "genshin": {"found": False, "path": ""},
        "bettergi": {"found": True, "path": "F:/BetterGI/BetterGI.exe"},
    }
    missing = deps.missing_for("genshin", paths)
    assert [m["id"] for m in missing] == ["genshin"]
    assert "《原神》" in missing[0]["name"]


def test_全都装好时没有缺失说明():
    paths = {key: {"found": True, "path": "x"} for key in KEYS}
    assert deps.describe_missing("genshin", paths) == ""


def test_依赖状态包含官网与就绪标记():
    paths = {key: {"found": True, "path": f"F:/{key}.exe"} for key in KEYS}
    status = deps.deps_status(paths)
    by_id = {item["id"]: item for item in status}
    assert len(status) == len(deps.DEPS)
    assert by_id["maa"]["found"] is True
    assert by_id["maa"]["url"] == "https://maa.plus/"

"""依赖清单：运行本项目需要的外部软件，以及它们在哪能拿到。

为什么单独一个文件：这份清单要同时喂给三处（桌面界面、手机端提示、README），
三处说法必须一致，否则用户会看到互相矛盾的信息。所以它是唯一事实源。

本模块**不负责**下载或安装任何东西，只提供「有没有」和「去哪拿」。
"""

from __future__ import annotations

from typing import Any

# item id 与 discovery 的 key 的对应关系。
# discovery 里没有「游戏本体」之外的独立项，所以这里用探测 key 直接对齐。
DEPS: list[dict[str, Any]] = [
    {
        "id": "genshin",
        "name": "《原神》",
        "role": "游戏本体。原神任务需要它已经装好并能正常启动。",
        "url": "https://ys.mihoyo.com/",
        "probe_key": "genshin",
        "required_by": "genshin",
    },
    {
        "id": "bettergi",
        "name": "BetterGI（更好的原神）",
        "role": "原神的自动化工具，负责跑「一条龙」。",
        "url": "https://www.bettergi.com/",
        "probe_key": "bettergi",
        "required_by": "genshin",
    },
    {
        "id": "starrail",
        "name": "《崩坏：星穹铁道》",
        "role": "游戏本体。星铁日常任务需要它已经装好。",
        "url": "https://sr.mihoyo.com/",
        "probe_key": "starrail",
        "required_by": "starrail",
    },
    {
        "id": "m7a",
        "name": "三月七小助手",
        "role": "星穹铁道的自动化工具，负责跑日常。",
        "url": "https://m7a.top/",
        "probe_key": "m7a",
        "required_by": "starrail",
    },
    {
        "id": "mumu",
        "name": "MuMu 模拟器",
        "role": "安卓模拟器。明日方舟跑在它里面。",
        "url": "https://mumu.163.com/",
        "probe_key": "mumu",
        "required_by": "arknights",
    },
    {
        "id": "maa",
        "name": "MAA（MaaAssistantArknights）",
        "role": "明日方舟的自动化工具，负责「一键长草」。",
        "url": "https://maa.plus/",
        "probe_key": "maa",
        "required_by": "arknights",
    },
]

# 注：这里**不再包含 cloudflared**。
# 早先为了「出门在外」集成过 cloudflared 临时隧道，但它的地址每次重启都变，
# 和 Tailscale Funnel 的固定地址不是一回事，摆在界面上会误导用户。
# 现在公网访问只有 Tailscale Funnel 一条路，用户不需要单独装 cloudflared。

GAMES: dict[str, dict[str, Any]] = {
    "arknights": {"label": "明日方舟", "requires": ["maa", "mumu"]},
    "genshin": {"label": "原神", "requires": ["genshin", "bettergi"]},
    "starrail": {"label": "崩坏：星穹铁道", "requires": ["starrail", "m7a"]},
}

_BY_ID: dict[str, dict[str, Any]] = {item["id"]: item for item in DEPS}


def get_dep(dep_id: str) -> dict[str, Any] | None:
    return _BY_ID.get(dep_id)


def deps_status(paths: dict[str, dict], cloudflared_available: bool | None = None) -> list[dict]:
    """把探测结果拼成对外的依赖清单。

    paths: detect_all() 的返回值
    cloudflared_available: 已废弃，保留参数只为兼容旧调用（cloudflared 已不在清单里）
    """
    out: list[dict] = []
    for item in DEPS:
        hit = paths.get(item["probe_key"] or "", {})
        out.append(
            {
                "id": item["id"],
                "name": item["name"],
                "role": item["role"],
                "url": item["url"],
                "optional": bool(item.get("optional", False)),
                "required_by": item.get("required_by"),
                "found": bool(hit.get("found")),
                "path": str(hit.get("path", "") or ""),
            }
        )
    return out


def missing_for(game: str, paths: dict[str, dict]) -> list[dict]:
    """某个游戏缺哪些依赖。返回缺失项（含名称与官网），缺的游戏本体也一并返回。"""
    game_info = GAMES.get(game)
    if not game_info:
        return []
    missing: list[dict] = []
    for dep_id in game_info["requires"]:
        item = _BY_ID.get(dep_id)
        if item is None:
            continue
        hit = paths.get(item["probe_key"] or "", {})
        if not hit.get("found"):
            missing.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "url": item["url"],
                    "role": item["role"],
                }
            )
    return missing


def describe_missing(game: str, paths: dict[str, dict]) -> str:
    """生成一句可以直接给用户看的缺失说明，不要只说「未找到」。"""
    missing = missing_for(game, paths)
    if not missing:
        return ""
    names = "、".join(m["name"] for m in missing)
    first_url = missing[0]["url"]
    return (
        f"缺少{names}。请在电脑上安装后重试；"
        f"下载地址：{first_url}。也可以在电脑端「依赖清单」里查看全部要求。"
    )

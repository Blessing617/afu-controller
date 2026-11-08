"""注册表探测：从卸载列表里找已安装的软件与游戏。

实测要点：
- 《原神》《崩坏：星穹铁道》在注册表里登记的 `InstallLocation` 指向的是
  **miHoYo Launcher 目录**，不是游戏本体，需要从这个目录继续往下找。
- BetterGI、MuMu 也有卸载项，可以直接拿到安装目录。
- MAA 是绿色版，通常没有任何注册表记录。
"""

from __future__ import annotations

import winreg
from pathlib import Path

_UNINSTALL_ROOTS = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]


def list_installed() -> list[dict]:
    """枚举卸载列表，返回 [{name, location, icon}]。"""
    items: list[dict] = []
    for hive, path in _UNINSTALL_ROOTS:
        try:
            key = winreg.OpenKey(hive, path)
        except OSError:
            continue
        with key:
            index = 0
            while True:
                try:
                    sub_name = winreg.EnumKey(key, index)
                except OSError:
                    break
                index += 1
                try:
                    sub = winreg.OpenKey(key, sub_name)
                except OSError:
                    continue
                with sub:
                    def _get(value_name: str) -> str:
                        try:
                            return str(winreg.QueryValueEx(sub, value_name)[0])
                        except OSError:
                            return ""

                    name = _get("DisplayName")
                    if not name:
                        continue
                    items.append(
                        {
                            "name": name,
                            "location": _get("InstallLocation"),
                            "icon": _get("DisplayIcon"),
                        }
                    )
    return items


def find_by_name(needles: list[str]) -> list[dict]:
    """按 DisplayName 关键词模糊匹配。"""
    lowered = [n.lower() for n in needles]
    out = []
    for item in list_installed():
        name = item["name"].lower()
        if any(n in name for n in lowered):
            out.append(item)
    return out


def location_of(needles: list[str]) -> list[Path]:
    """返回匹配项的安装目录（只保留真实存在的目录）。"""
    dirs: list[Path] = []
    for item in find_by_name(needles):
        loc = item.get("location") or ""
        if not loc:
            # 有些卸载项把路径写在 DisplayIcon 里
            icon = item.get("icon") or ""
            if icon.lower().endswith(".exe"):
                loc = str(Path(icon).parent)
        if not loc:
            continue
        p = Path(loc.strip('"'))
        if p.is_dir():
            dirs.append(p)
    return dirs

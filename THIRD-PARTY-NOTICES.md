# 第三方声明

本程序只是「胶水」：真正执行游戏日常的是下面这些成熟的开源工具。
本仓库**不包含**它们的代码与美术素材，只通过命令行与配置文件调用本机已安装的它们。

## 被调用的外部工具

| 工具 | 用途 | 项目地址 | 授权 |
|---|---|---|---|
| MAA（MaaAssistantArknights） | 明日方舟自动化 | <https://github.com/MaaAssistantArknights/MaaAssistantArknights> | AGPL-3.0 |
| BetterGI | 原神自动化 | <https://github.com/babalae/better-genshin-impact> | GPL-3.0 |
| 三月七小助手（March7thAssistant） | 崩坏：星穹铁道日常 | <https://github.com/moesnow/March7thAssistant> | GPL-3.0 |
| MuMu 模拟器 | 安卓模拟器（MAA 的运行环境） | 网易官方 | 厂商许可 |

## 桌面端依赖

| 组件 | 用途 | 授权 |
|---|---|---|
| PySide6（Qt for Python） | 桌面界面 | LGPL-3.0 |
| FastAPI / uvicorn | 本地服务 | MIT / BSD-3-Clause |
| Pillow | 截图编码 | MIT-CMU |

## 手机端依赖

| 组件 | 用途 | 授权 |
|---|---|---|
| Jetpack Compose / AndroidX | 界面 | Apache-2.0 |
| OkHttp | 网络请求 | Apache-2.0 |
| kotlinx.serialization | 数据序列化 | Apache-2.0 |

## 字体

| 字体 | 用途 | 授权 |
|---|---|---|
| ZCOOL KuaiLe（站酷快乐体） | 标题、按钮文字、时间与数字 | SIL Open Font License 1.1 |

字体文件位于 `assets/fonts/zcool-kuaile/`，许可证全文见同目录 `OFL.txt`。

## 界面图形

- 应用图标、导航图标、装饰图形：本项目原创绘制，源文件在 `assets/icons/` 下。
- 三个游戏的应用图标：**不在本仓库内**。它们在运行时从用户本机已安装的游戏与工具中提取，
  仅用于在界面上区分是哪个游戏；本仓库不含任何游戏厂商的美术素材。

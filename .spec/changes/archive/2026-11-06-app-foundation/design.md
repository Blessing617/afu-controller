# 设计：游戏编排 APP 基座

## 1. 整体形状

```
┌──────────────────────┐    Tailscale 虚拟内网    ┌────────────────────────────┐
│ Android APP          │ ◄──── HTTP + WS ────►   │ 电脑端服务 (Python)         │
│ Kotlin + Compose     │   固定地址 + token       │ 计划任务常驻（最高权限）     │
│                      │                          │                            │
│ · 连接页             │                          │ · 配对 / 鉴权               │
│ · 明日方舟页         │                          │ · 路径探测                  │
│ · 原神页             │                          │ · 任务队列（前台互斥）      │
│ · 星穹铁道页         │                          │ · 三个引擎适配器            │
└──────────────────────┘                          └────────────────────────────┘
                                                          │
                                    ┌─────────────────────┼─────────────────────┐
                                    ▼                     ▼                     ▼
                              MAA（远程控制）        BetterGI（CLI+日志）    M7A（CLI+JSON）
                              MuMu 模拟器            原神客户端              星铁客户端
```

## 2. 网络层：为什么是 Tailscale

家用宽带基本没有公网 IP，手机在外面要访问家里的电脑，常见三条路：

| 方案 | 问题 |
|---|---|
| frp / 端口映射 | 需要公网 IP；把服务裸露到公网，这条链路能操控键鼠，风险不可接受 |
| Cloudflare Tunnel | 需要域名；同样要把受保护接口暴露到公网，还得自己补认证 |
| **Tailscale** | 虚拟内网，端到端加密，地址固定（100.x.x.x），个人版免费；同 WiFi 下自动走 LAN 直连 |

选 Tailscale 的直接后果是**地址固定**，于是连接逻辑大幅简化：

- 不需要 mDNS / UDP 广播发现
- 不需要区分「在家」和「在外面」
- 用户只在首次配置时输入（或扫码获得）一次地址

一次性配置成本：电脑和手机各装一次 Tailscale，登录同一账号。之后完全透明。

## 3. 电脑端

### 3.1 技术栈

- Python 3.13 + FastAPI + Uvicorn
- 依赖装进项目内虚拟环境（放 `D:\<项目目录>\Game_play\server\.venv`，不污染 C 盘）
- 复用已验证的部署方式：计划任务 `GameOrchestrator`（`AtLogOn` + `Highest` + 交互式会话），保证拉起的子进程继承管理员权限，全程不弹 UAC

### 3.2 为什么不用现成的 `maa_probe.py`

`server/probe/maa_probe.py` 是验证用的探针：标准库、无依赖、动作白名单写死。它的价值已经兑现（证明了协议与权限模型），继续在上面堆会变成一坨。基座重写为正规分层：路由 / 服务 / 适配器 / 探测，探针保留作对照。

### 3.3 接口轮廓

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 无需鉴权，用于连接测试；返回版本与是否待配对 |
| POST | `/api/pair` | 配对码换 token |
| GET | `/api/status` | 自检：引擎可用性、锁屏、权限、当前任务 |
| GET | `/api/games` | 三个游戏的探测结果与可用性 |
| POST | `/api/games/{id}/path` | 手动指定路径 |
| POST | `/api/discover` | 重新探测 |
| POST | `/api/tasks/{id}/run` | 启动（运行中返回 409） |
| POST | `/api/tasks/stop` | 停止当前任务 |
| GET | `/api/tasks/current` | 当前任务 + 日志尾部 |
| WS | `/ws` | 状态事件流 |

### 3.4 路径探测顺序（依据实测）

实测结论直接影响策略：

| 目标 | 注册表 | 其他线索 |
|---|---|---|
| 原神 | 有「原神」条目，但 `InstallLocation` 指向 **miHoYo Launcher 目录**，不是游戏本体 | 需要从启动器目录继续找 `Genshin Impact/Genshin Impact Game/YuanShen.exe` |
| 星穹铁道 | 同上，指向 miHoYo Launcher | 继续找 `Star Rail Game/StarRail.exe` |
| BetterGI | 有「BetterGI」条目（版本号可能是旧的） | 以 `.exe` 实际存在为准 |
| MAA | **没有**（绿色版） | 扫目录 + `MAA.exe` 特征名 |
| 三月七小助手 | **没有** | `%LOCALAPPDATA%\March7thAssistant\installs.json` 有安装登记 |
| MuMu | 有「MuMu模拟器」条目 | 用于取 `MuMuManager.exe` |

探测管线：**注册表 → 已知登记文件 → 目录扫描（关键词 + 有限深度） → 人工兜底**。
每一级都要「校验目标可执行文件存在」才采纳，避免同名目录误命中。

目录扫描的约束（防止满盘扫描拖死启动）：
- 只扫盘符根目录起的固定深度（建议 3–4 层）
- 关键词使用目录名（原神/星穹铁道/Genshin/StarRail/MuMu/BetterGI/MAA/March7th）
- 单盘超时上限，超时就跳过并记录

## 4. 手机端（Android）

### 4.1 技术栈（对齐 `afu-ledger`）

- Kotlin + Jetpack Compose + Material 3
- MVVM：Screen → ViewModel → Repository → 数据源
- 网络：Retrofit/OkHttp + OkHttp WebSocket
- 本地存储：DataStore（地址、token、手动路径）
- `minSdk 26`，单模块，按功能分包

代码约定沿用它：一个文件一个主要类型、单文件 ≤300 行、UI 不直接访问数据层。

### 4.2 页面结构

底部导航四个入口：

1. **连接**：地址输入 / 扫码、配对码、连接状态与自检结果
2. **明日方舟**：状态卡 + 「开始」
3. **原神**：状态卡 + 「开始」
4. **星穹铁道**：状态卡 + 「开始」

三个游戏页共用一套「任务卡」组件（标题、可用性、运行中状态、耗时、开始/停止按钮、日志入口），只有游戏标识与任务名不同。

### 4.3 状态同步

- 进页面先 `GET /api/tasks/current` 拉全量，再开 WebSocket
- WebSocket 只承载增量事件（状态变化、日志行）
- 断线重连后重新拉全量，不依赖事件重放

## 5. 三引擎适配（复用验证结论）

| 引擎 | 触发 | 完成判定 | 已知坑 |
|---|---|---|---|
| MAA | 服务端下发 `LinkStart`（MAA 主动轮询 `/api/maa/getTask`） | `reportStatus` 的 SUCCESS/FAILED | POST 空 body、device 为空串、需容忍 |
| BetterGI | `BetterGI.exe --startOneDragon`（管理员） | 日志出现一条龙完成/失败关键字；进程退出 | **重跑前必须先结束旧进程**；窗口需在前台 |
| M7A | `m7a.exe daily --after-finish None` | `runs/<id>.json` 的 status + 退出码 | 必须先关 `pause_after_success`，否则进程永不退出 |

## 6. 关键权衡

| 决策 | 选择 | 放弃的方案与原因 |
|---|---|---|
| 网络 | Tailscale | 局域网发现（手机带出门就废）、frp（公网暴露风险） |
| 探测 | 注册表优先 + 有限扫描 | 全盘搜索（太慢）、只靠用户手填（违反「打开就能用」） |
| 服务形态 | 计划任务常驻高权限 | 运行时提权（实测非交互会话下 UAC 弹不出来） |
| 任务结果 | 以引擎自己的状态源为准 | 统一用「进程退出码」（BGI 没有退出码语义） |
| 手机端 | 只做 Android | iOS（用户不需要，跨平台成本高） |

## 7. 风险

| 风险 | 应对 |
|---|---|
| Tailscale 需要用户两端配置一次 | 连接页给出图文步骤 + 电脑端显示自己的 Tailscale 地址可复制 |
| 全盘扫描拖慢启动 | 深度限制 + 超时 + 后台异步探测，探测中先返回已知结果 |
| 三引擎版本更新导致命令变化 | 版本写入自检、命令集中在一处配置、失败时给可读原因 |
| 电脑锁屏导致任务白跑 | 启动前检查锁屏并拒绝 |

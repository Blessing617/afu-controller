# 设计：任务生命周期、分层重构与性能

## 0. 调研结论：三家引擎到底提供了什么

三个引擎都是开源的，判定方式以**源码与官方文档**为准，不靠观察行为猜。

| 引擎 | 接口 | 能力 | 依据 |
|---|---|---|---|
| 三月七 | `m7a.exe --status --json` | `active_run` / `recent_runs` / `elevation` | 本机 `m7a.exe --status` 实测 + 安装目录 `assets/agent/skills/march7th-assistant/SKILL.md` |
| 三月七 | `--control <run_id> stop\|pause\|resume` | 优雅停止；退出码 6 = 被停止 | 同上 |
| 三月七 | `--detach` / `--follow` / `--list --json` | 异步启动、跟随、任务清单 | 同上 |
| 三月七 | `logs/runs/<run_id>.json` / `.log` | 终态记录、完整日志 | 运行记录实测（`20261108-020836-928f.json`） |
| 方舟 | 远程控制 `getTask` / `reportStatus` | 下发任务、终态回报 | `docs/zh-cn/protocol/remote-control-schema.md` |
| 方舟 | 远程控制 **`HeartBeat`** | 回报 `payload` = 当前执行的顺序任务 id，空闲为空串 | `src/MaaWpfGui/Services/RemoteControl/RemoteControlService.cs` |
| 方舟 | 远程控制 `StopTask` | 立即请求停止 | 同上 |
| 原神 | **无**（0.66.0） | 只能读日志 | 安装目录无 `ExternalAccess` 配置、无 Kestrel/AspNetCore 依赖 |
| 原神 | `GET /api/v1/health`、`ws://127.0.0.1:30648/ws/v1/logs` | 健康状态、实时日志（先回放 200 条） | `Docs/design/external-access.md`（较新版本，默认关闭，明确「不提供任务启动/停止」） |
| 原神 | 日志「一条龙和配置组任务结束」 | 完成标志 | `better-genshin-impact20261106.log` 实测 |

三条重要推论：

1. **星铁和方舟都有官方状态接口**，不该再去猜文件。
2. **原神只能读日志**，所以它的日志判定必须做对（现在完成标志就是错的）。
3. 原神的「外部访问服务」即使将来可用，也只给你健康状态和日志流，**没有任务控制**，
   所以它永远只能是「更好的日志投递方式」，不能替代日志解析。

## 1. 引擎适配器统一接口

现在三个适配器是三种写法（m7a 阻塞、BGI 轮询、MAA 事件驱动），外层要写三套分支。
统一成一个接口，外层只认接口：

```python
class EngineAdapter(Protocol):
    game: str
    def capability(self) -> list[TaskOption]: ...          # 能力清单（已有 capability.py）
    def precheck(self) -> PrecheckResult: ...              # 路径、锁屏、引擎是否已经在跑
    def prepare(self, tasks: list[str]) -> None: ...       # 写回子任务配置（已有 apply.py）
    def start(self, job: Job) -> Handle: ...               # 启动，立刻返回句柄（不阻塞）
    def poll(self, job: Job) -> Progress: ...              # 读日志/记录，报告进度与终态候选
    def stop(self, job: Job, reason: str) -> None: ...     # 优雅停止，必要时降级为强杀
```

关键点：

- `start` **必须立刻返回**。任何「等进程结束」的逻辑都不在 `start` 里。
- `poll` 由 `core` 的 supervisor 按节拍调用，返回 `running / success / failed / stopped / stuck`。
- 适配器**不写终态**，只上报；终态由状态机写入并广播一次。

这样「什么时候算完」只在一个地方（supervisor）实现，三个引擎只是提供证据来源。

## 2. 星铁（m7a）：从「等管道」改成「看记录」

### 为什么不用 `--follow`

`--follow <run_id>` 确实能拿到与运行一致的退出码，但它仍是**阻塞子进程**，
和现在的 `subprocess.run` 一样有被派生进程继承句柄的风险；而且它同样要 UAC。
我们要的是「不依赖任何子进程的退出」，所以不走这条路。

### 采用：detach + 文件轮询

```
启动:  m7a.exe <task> --after-finish None --detach --json
       → stdout 里的运行编号 run_id（stdin/stdout 用 DEVNULL/PIPE 但要设超时，见下）
轮询:  1) logs/runs/<run_id>.json 存在 → 读取 status 终态，结束
       2) logs/runs/<run_id>.log 按偏移增量读 → 日志与进展
       3) 每 30 秒一次 m7a.exe --status --json 兜底（校验 run_id 仍是 active_run，
          以及拿 elevation 信息）
停止:  m7a.exe --control <run_id> stop → 等 60 秒 → 仍在则结束进程树
```

注意 detach 启动这一步本身也要有超时（UAC 可能一直没人点），用
`Popen` + 最多等 180 秒读一行 JSON，超时就判「等待授权超时」，把原因说清楚。
**这一步必须用 `Popen(stdout=PIPE, stderr=PIPE)` 配自己的超时循环，
绝不能用 `subprocess.run(capture_output=True, timeout=...)`。**

回退：如果 detach 不可用（退出码 2），退到「`--status --json` 取 active_run 的 run_id」，
再不行就看最新出现的 `logs/runs/*.json`（启动前先记下已有文件集合，只认新出现的）。
任何回退路径都只读文件，不捕获管道。

### 超时：按「无进展」判定，不按总时长

早期打算按任务类型给总时长上限，但那是错的：同一台机器今天快明天慢，任务本身也可能
因为游戏内刷出额外事件而变长。真正要抓的是「卡住了」，而卡住的本质是**没有再推进**。

所以用三档阈值，核心是中间那档：

```python
stall = StallWatch(
    first_progress=15 * 60,   # 启动后这么久没有任何日志才认为没起来
    idle=10 * 60,             # 已有进展后，这么久没有新的有效进展 → 卡死
    hard_cap=6 * 3600,        # 一直有进展但永不结束 → 兜底终止
)
```

`idle=10 分钟` 不是拍脑袋：统计了 2026-10-23～11-08 的实测日志，
星铁单次运行内最长静默 3.4 分钟（战斗中，`尝试进入战斗 → 战斗结束`），
原神一条龙跑满 40 分钟时最长静默只有 31 秒。10 分钟分别是 3 倍与 19 倍余量。
阈值按引擎可覆盖，改之前要重新统计，不能凭感觉调。

`StallWatch` 维护 `last_progress_at`，每次收到有效进展就刷新。
判卡死看的是 `now - last_progress_at`，**与 `started_at` 无关**。

`hard_cap` 只在「一直在刷有效日志却永不结束」时才会命中，属于最后一道保险。
它触发时也要把原因写清楚，而不是笼统的「超时」。

进度与进展由同一个数据源产出，避免两套解析：适配器的 `poll` 返回
`Progress(lines=[...], markers={...}, terminal=None)`，其中 `markers` 是解析出的
结构化进度（如 `{"stage": "11/13"}`、`{"task": "2/4"}`），既用于判断「有没有推进」，
也直接推给手机端显示。

### 日志读取

`core/logstream.py` 负责：记录启动时的文件偏移 → 定时 `seek/read` → 按行切分 →
过反刷屏（同一行连续超过 3 次折叠为一条 + 重复计数）→ 只保留尾部 200 行。
日志文件不存在时（引擎还没写）不报错，继续下一拍。

## 3. 原神（BetterGI）：修正完成判据

- 完成标志改为 `一条龙和配置组任务结束`（实测 2026-11-06 出现 1 次），
  保留 `正在关闭游戏和软件` 作为兼容（有些配置会把游戏一起关掉）。
- 启动时记录日志文件的**字节偏移**，之后只在本次区间内匹配。
  进程退出分支不再用 `run.log_tail[-60:]`（会跨运行），而是用本次区间读到的内容。
- 进程退出 + 本次区间有完成标志 → `success`；退出但无标志 → `failed`，
  原因带上日志里最后几行有效内容，方便用户自己看。
- 进度解析：`一条龙任务执行: i/n` → `{"task": "i/n"}`；`→ "任务启动！"` / `→ "任务结束"`
  用于确认单个任务在切换；具体步骤行（`领取尘歌壶奖励:"接近阿圆"` 等）只进日志。
- 卡死：只在**非重复行**抵达时刷新进展计时；`BetterGI.exe` 存活检测从每 5 秒一次
  降为每 15 秒一次（`tasklist` 每次要起子进程，频率没必要那么高）。
  注意 BGI 有「等待进入主界面」这类可以静默 30 秒以上的阶段，所以门限不能设得太短（默认 10 分钟）。
- 停止：BetterGI 没有停止命令，先结束进程并注明「无法优雅停止」；
  游戏是否跟着关由 cleanup 决定。

## 4. 方舟（MAA）：把事件接回状态机

- `MaaAdapter.on_report` 不再直接 `RUNNER.finish`，改为把结果塞进 `job` 的结果队列，
  由 supervisor 收敛终态。
- 判活用官方 `HeartBeat`：下发 `LinkStart` 前先塞一个心跳，确认顺序队列空闲；
  执行期间每 15 秒下发一个（每次新 id），回报 `payload` 非空即「有任务在跑」。
  心跳的回报单独处理，**不进 `_pending`**，也不改变任务状态。
- **心跳不能当进展用**。`LinkStart` 是一个顺序任务，`_currentSequentialTaskId` 在整段期间
  是不变的（源码：进入 `ExecuteSequentialJobLoop` 时赋值，整个 LinkStart 结束后才清空），
  所以五分钟的基建和一小时的刷体力在心跳里完全一样。
- 方舟的「有效进展」取 `debug/asst.log` 的字节增长。MAA 用 Serilog 写 TRC 级别的核心日志，
  执行期间每条识别/操作都会落盘；空闲时该文件不写。实施时要先实测确认这一点，
  确认不了就退化成「心跳 + 绝对兜底」，并在日志里注明降级，不硬编一个假判据。
- 依据：`src/MaaWpfGui/Services/RemoteControl/RemoteControlService.cs`
  —— `HeartBeat` 走 instant queue 立即执行，`payload = _currentSequentialTaskId`；
  `PollJobTaskLoop` 与执行循环是两个独立 `ContinueWith`，任务执行期间照常轮询。
- 失败判据：
  - `getTask` 超过 15 秒没有被轮询 → 失败「MAA 已离线」
  - 心跳显示仍在执行、且 `asst.log` 连续 10 分钟无增长 → 卡死，先 `StopTask`
- 细粒度进度：MAA 一次 `LinkStart` 内部不回报子任务，所以进度只能到「在跑 / 空闲」。
  若以后需要「第 2/4 个任务」这种粒度，可以按勾选下发 `LinkStart-Base`、
  `LinkStart-Combat` 等**顺序任务序列**，心跳的 payload 天然就是当前子任务 id。
  本次先不做，列为后续增强。
- `ensure_online` 里的 `sleep(20)` / `sleep(4)` 改成 `wait_until(条件, 超时)` 轮询，
  对外表现为「日志里有进度、不是傻等」，也让停止请求能及时打断。

## 5. 状态机与分层

### 服务端目录

```
server/app/
├── main.py                 # 组装：app、路由、生命周期、事件注册
├── api/                    # 只做参数校验与翻译（不碰引擎、不碰状态）
├── core/
│   ├── state.py            # TaskRun / TaskState / TaskRunner（唯一状态持有者）
│   ├── supervisor.py       # 生命周期驱动：节拍、卡死、超时、终态收敛
│   ├── logstream.py        # 增量读日志 + 反刷屏 + 尾部缓冲
│   ├── chain.py            # 链定义与持久化
│   ├── orchestrator.py     # 链调度（只调 supervisor）
│   ├── config.py
│   └── events.py           # 事件广播（WS 用）
├── engine/                 # 适配器（只与引擎进程/配置文件打交道）
│   ├── base.py             # EngineAdapter 协议 + 注册表
│   ├── m7a.py / bgi.py / maa.py
│   ├── capability.py / apply.py
│   └── cleanup.py
└── platform/               # Windows 系统调用
    ├── window.py / capture.py / proc.py / winutil.py / keepawake.py
```

依赖方向：`api → core → engine → platform`，反向导入视为错误，用脚本检查。

### 拆文件（≤300 行）

| 现在 | 拆成 |
|---|---|
| `engine/capture.py` 524 | `capture.py`（抓屏）+ `capture_encode.py`（缩放/JPEG/黑图判定） |
| `api/tasks.py` 350 | `api/tasks.py`（启动/停止）+ `api/cleanup.py`（释放）+ `core/precheck.py` |
| `engine/window.py` 321 | `window.py`（枚举/查找）+ `focus.py`（激活/最小化） |
| `engine/capability.py` 318 | `capability.py`（清单）+ `capability_builtin.py`（静态回退表） |
| `engine/apply.py` 306 | `apply.py`（分发）+ `apply_maa.py` / `apply_bgi.py` |
| `desktop/qt_ui.py` 1278 | `shell.py`（主窗与导航）+ `pages/overview.py` / `connect.py` / `settings.py` / `game.py` + `widgets/*.py` |
| `ui/Screens.kt` 1321 | `ui/screens/` 下按页面拆 |
| `ui/ChainScreen.kt` 1138 | `ui/chain/` 下拆（列表 / 编辑 / 子任务选择） |
| `ui/AppViewModel.kt` 789 | 按职责拆成 连接 / 任务 / 画面 / 编排 四个状态持有者 |

## 6. 性能与内存

### 电脑端（当前 132MB）

| 措施 | 预期 | 代价 |
|---|---|---|
| 桌面端页面懒构建（首次进入才建） | 启动内存与时间都降 | 首进某页有几十毫秒构建 |
| 后台采集节拍 2s → 5s | 空闲 CPU 降 | 地址变化最晚 5 秒后反映 |
| `uvicorn` 关 access log | 每请求少一次写盘与格式化 | 排查时用我们的 app.log |
| 配置读取加 mtime 缓存 | 每请求少一次 JSON 解析 | 外部改文件要靠 mtime 感知（已有） |
| 截图链路复用整屏缓冲 | 每张省一次 16MB 分配 | 需要全局串行（已有）+ 显式释放 |
| PIL 插件裁剪（不需要的部分排除） | 包体与导入内存降 | 打包时要验证截图仍可用 |

**不拆进程**：桌面端与服务端同进程共享同一份配置与状态，拆开要多一份解释器与 IPC，
在当前 120MB 目标下不划算。若实测压不到 120MB，再单独评估「服务端常驻 + 界面按需」。

**不引入 psutil**：测量用 `Get-CimInstance Win32_Process` / `Get-Process`，
运行期不用第三方进程库。

### 手机端（推送优先）

- 已连接时优先建立 WebSocket（`/ws` 已实现），状态与日志走推送。
- WebSocket 可用时**停止** 3s/5s 的轮询；不可用才退回，且间隔 ≥ 15 秒。
- 断线检测靠 WS 关闭事件（即时）；无 WS 时靠一次失败请求直接判定，仍满足 15 秒。
- 位图：保持现状（RGB_565、inSampleSize、单张），补一条「切页不新增位图」的断言。
- 注意：Tailscale Funnel 对 WebSocket 升级的支持要在真机上验证；不支持就退回轮询，
  功能不变、只是省不了那部分电。

## 7. 风险与回退

| 风险 | 处理 |
|---|---|
| `--detach` 在有 UAC 的机器上返回值不稳定 | 三条回退路径（detach → status.active_run → 新增 runs 文件），任何一条都不碰管道 |
| 分层重构期间手机端老版本连不上 | 所有 HTTP 路径、字段、鉴权保持兼容，只新增字段不删 |
| WebSocket 在某些网络下不可用 | 保留轮询兜底，自动降级 |
| 拆文件引入回归 | 每拆一个模块先补该模块的最小测试，再搬；拆完跑一遍端到端（三个引擎至少各一次真跑） |
| 内存目标压不下去 | 先达标优化措施全上，再测；仍不达标就把「界面按需」作为单独变更评估，不硬凑数 |

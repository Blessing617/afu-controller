# 设计：编排能力

## 1. 为什么不能「一招通吃」

实测三个引擎的接口形态完全不同，硬套一套抽象会到处漏：

| 引擎 | 能否枚举子任务 | 如何控制子任务 | 如何知道完成 |
|---|---|---|---|
| **三月七** | ✅ `--list --json` 返回 27 项 | 命令行位置参数（task id） | 退出码 + `logs/runs/<id>.json` |
| **MAA** | ❌ 无 CLI 枚举 | 写配置 `TaskQueue[].IsEnable`，或远程协议 `LinkStart-<子任务>` | `reportStatus` 回报 |
| **BetterGI** | ❌ 无 CLI 枚举 | 写 `User/OneDragon/*.json` 的 `TaskEnabledList` | 日志正则 |

所以设计成 **Capability（能力）+ Adapter（适配）** 两层：

```
Orchestrator（链调度）
   └─ StepExecutor(game)
        └─ EngineAdapter
             ├─ list_tasks()  -> [TaskItem]       ← 各家自己实现
             ├─ apply_tasks(ids) -> None          ← 写回配置 / 不做事
             └─ run(run, tasks) -> TaskState      ← 复用现有 bgi/m7a/maa
```

`list_tasks()` 每个适配器三选一：命令枚举（三月七）、读配置（MAA / BGI）、静态兜底。

## 2. 三月七：直接枚举，最省事

```
m7a.exe --list --json
→ [{"id":"main","name":"完整运行"}, {"id":"power","name":"清体力"}, ...]
```

执行时把选中的 id 依次传给命令行。**只支持一次一个 task**，所以用户的多个勾选要拆成
多次调用串行执行（每次 `m7a.exe <task> --after-finish None`，等它退出再下一次）。
不改配置——它本来就没有「哪些任务默认开」的配置概念。

注意：`daily` 和 `routine` 有重叠（都是日常），界面要给一条提示避免用户两个都勾。

## 3. MAA：读配置 + 写回 IsEnable

配置在 `config/gui.new.json`：

```json
{
  "Current": "Default",
  "Configurations": {
    "Default": {
      "TaskQueue": [
        {"TaskType": "StartUp", "IsEnable": true, ...},
        {"TaskType": "Fight",   "IsEnable": true, "StagePlan": ["TL-9"]},
        {"TaskType": "Infrast", "IsEnable": true},
        ...
      ]
    }
  }
}
```

读：遍历 `TaskQueue`，取每项的 `TaskType`（映射成中文名）+ `IsEnable`。
写：只改 `IsEnable`，其他字段（关卡、干员、配置名）一个不动。

**关键约束**：`gui.new.json` 会被 MAA 自己重写（启动时）。所以写回必须
「读-改-写」在一次操作内完成，且要赶在 MAA 启动之前。流程：

1. 链调度到方舟这一步 → 先 `apply_tasks()` 写配置
2. 再启动 MAA（`ensure_online` 会拉起 MAA）
3. MAA 启动时读到的就是我们写好的配置

**这个「会被重写」不是猜测，是实测过的。** 2026-11-07 检查 MAA 的 config 目录：

```
gui.new.json          19:22:12   ← 主文件
gui.new.json.bak      19:22:05   ← 7 秒前它自己留的备份
gui.new.json.bak-clean / .bak-probe / .bak-uid   ← 历史上还留了好几个
```

把 `gui.new.json` 和它的 `.bak` 逐字段 diff，**只差 1 个字段**
（`Configurations/Default/TaskQueue[5]/IsVisitFriendsAvailable`，一个运行时状态标记）。
说明 MAA 每次启动 / 退出都会把自己内存里的完整状态整份写回这个文件。

所以：

- **情况 A（安全）**：我们写文件 → 启动 MAA → MAA 读到的就是我们写的
- **情况 B（会被覆盖）**：MAA 已在跑 → 我们写文件 → MAA 退出时用内存态整份覆盖 → 改动丢失

因此写回 SHALL 发生在启动 MAA 之前；且写前若检测到 MAA 在线（`MAA.online()` 判定它
是否在轮询），先 `StopTask` + 等它退出，再写。

这个风险**只有 MAA 有**：

- 三月七：不写配置，命令行直传 task id，无此问题
- BetterGI：也会重写自己的配置，但 `TaskEnabledList` 属于用户设置（会原样写回），
  风险较小；同样遵循「先写后启」的顺序即可。

备份：写之前把原文件复制成 `gui.new.json.bak-orch`。解析失败直接放弃写入并报错。

## 4. BetterGI：读配置 + 写回 TaskEnabledList

```json
{
  "TaskDefinitions": {"bbff84c2-...": "领取邮件", "9e78f950-...": "自动秘境", ...},
  "TaskEnabledList": {"bbff84c2-...": true, "9da3defc-...": false, ...}
}
```

`TaskDefinitions` 是 UUID → 中文名，`TaskEnabledList` 是 UUID → 是否启用。
读出来的清单直接给界面；写回只改 `TaskEnabledList` 的布尔值。

问题：UUID 在不同机器/不同版本上可能不一样。所以**清单必须从本机配置读**，
不能写死 UUID。内置兜底清单只给「一条龙（全部）」这一个粗粒度选项，
避免猜错 UUID 写坏配置。

## 5. 链调度器

```python
class Orchestrator:
    def run_chain(chain, policy="skip"):
        for i, step in enumerate(chain.steps):
            if not step.enabled: mark_skipped(); continue
            if aborted: mark_not_run(); continue
            emit_progress(i, len(steps), step.game)
            state = execute_step(step)     # 复用 tasks._execute
            if state is FAILED and policy == "stop": aborted = True
```

它**不新建任务运行器**，而是复用现有的 `RUNNER`：每一步仍然是一个 `TaskRun`，
只是多一个 `chain_id` 字段把同一次链的多个 run 串起来。这样：
- 单步启动 / 停止 / 日志 / WebSocket 广播全部不用改
- 前端既能看「当前步」也能看「整条链」

进度事件新增一种：`{"type":"chain","event":"step"|"finished","chain":{...}}`，
与现有 `{"type":"task",...}` 并存，老版本客户端忽略即可。

## 6. 失败策略与边界

- 默认 `skip`：失败了记录原因，继续下一步
- 可选 `stop`：失败即中止，后续标 `not_run`
- 用户中途停止：当前步 `stopped`，后续 `not_run`
- **不做**：失败自动重试（不可靠，且有封号风险叠加）

## 7. 手机端编辑

编排页结构：

```
[ 编排 ]
┌─────────────────────────────┐
│ 1 ▣ 明日方舟  基建/公招/商店  ⋮ │
│ 2 ▣ 原神      一条龙          ⋮ │
│ 3 ▣ 星穹铁道  日常/清体力     ⋮ │
└─────────────────────────────┘
[ + 添加步骤 ]
[ ▶ 一键跑完整条链 ]
```

拖动排序用 `LazyColumn` + 长按拖拽。增删改立刻 `POST /api/chain` 保存。
断网时写本地 DataStore，恢复后补发。

子任务勾选用二级页/底部面板，按引擎返回的清单渲染。

## 8. 新增接口

```
GET    /api/chain              -> 当前任务链
PUT    /api/chain              -> 保存任务链（整份替换）
POST   /api/chain/run          -> 开始执行
POST   /api/chain/stop         -> 停止整条链
GET    /api/chain/status       -> 链执行状态（当前步 / 各步结果）
GET    /api/engines/{game}/tasks -> 该引擎的能力清单
```

`PUT /api/chain` 校验：步骤数 ≤ 10、game 合法、tasks 里的 id 属于该引擎清单。

## 9. 兼容

- 老的「单游戏一键启动」接口保持不动
- 老的 `UiState` 加字段而不是改结构，老客户端能继续跑
- 任务链配置独立文件 `data/chain.json`，不塞进 `config.json`（避免和现有配置互相覆盖）

## 10. 风险

| 风险 | 缓解 |
|---|---|
| 写坏引擎配置 | 写前 `.bak-orch` 备份；解析失败不写；只改开关字段 |
| MAA 内存态覆盖写入 | 写回前检测 MAA 是否在线，在线则先停 |
| 引擎升级后 UUID 变化 | BetterGI 清单每次从本机配置读，不缓存 |
| 链跑到一半电脑崩溃 | 链状态只存内存，重启后链视为未运行（不自动续跑） |
| 用户勾了两个重叠任务 | 界面给提示（如 daily + routine） |

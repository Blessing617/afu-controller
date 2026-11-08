# orchestration

## Purpose

把「三个游戏各自点一下」升级成「编排一条链从头跑到尾」，并让每一步只做用户想做的子任务。
编排的重点是**总体**（多游戏串行、任意顺序、任意子集）和**局部**（单个引擎内选子任务）两件事。

## Requirements

### Requirement: 任务链定义

系统 SHALL 支持定义一个「任务链」：一个有序的步骤列表，每个步骤包含：

- `game`：`arknights` / `genshin` / `starrail` 三者之一
- `enabled`：这一步是否参与本次执行
- `tasks`：该游戏要执行的子任务选择（为空表示「按引擎当前配置全跑」）
- `label`：可选的自定义显示名

同一个游戏 SHALL 允许在链里出现多次（例如「原神一条龙 → 星铁日常 → 原神收尾」）。

系统 SHALL 持久化任务链，重启电脑端服务后仍然存在。
系统 SHALL 允许只保留任意子集（只有原神一步、或只有原神和星铁）。

#### Scenario: 三步全跑

- GIVEN 任务链是「明日方舟 → 原神 → 星铁」，三步都启用
- WHEN 用户点「运行」
- THEN 三个游戏按该顺序依次执行
- AND 上一步结束后才开始下一步

#### Scenario: 只跑其中两个

- GIVEN 任务链是「明日方舟 → 原神 → 星铁」，但明日方舟那步被关掉
- WHEN 用户点「运行」
- THEN 只执行原神与星铁
- AND 明日方舟一步被跳过，日志里写明「已跳过（用户关闭）」

#### Scenario: 调整顺序

- GIVEN 任务链默认顺序是方舟 → 原神 → 星铁
- WHEN 用户把星铁拖到最前面
- THEN 执行顺序变为星铁 → 方舟 → 原神
- AND 该顺序被保存

#### Scenario: 重启后仍在

- GIVEN 用户改过任务链
- WHEN 电脑端服务重启
- THEN 任务链保持用户改过的样子

#### Scenario: 空链

- GIVEN 所有步骤都被关闭
- WHEN 用户点「运行」
- THEN 拒绝启动并提示「没有可执行的步骤」
### Requirement: 引擎能力清单

系统 SHALL 为每个引擎提供「能执行哪些子任务」的清单，供界面勾选。
清单 SHALL 尽量从引擎自身获取，而不是写死在代码里：

- 三月七：SHALL 通过 `m7a.exe --list --json` 实时获取任务列表（含 id 与中文名）
- MAA：SHALL 从 `config/gui.new.json` 的 `TaskQueue` 读取已有任务的 `TaskType` 与启用状态
- BetterGI：SHALL 从 `User/OneDragon/<配置名>.json` 的 `TaskDefinitions` 读取任务名与启用状态

当某个引擎取不到清单时（未安装、配置损坏、命令超时），系统 SHALL 退回内置的静态清单，
并 SHALL 在界面上标注「未能从引擎读取，使用默认清单」，MUST NOT 让界面空白。

#### Scenario: 三月七实时枚举

- GIVEN 三月七已安装
- WHEN 界面请求星铁的子任务清单
- THEN 返回引擎实际支持的 27 项（如「清体力」「模拟宇宙」「混沌回忆」）
- AND 每项带 id 与中文名

#### Scenario: MAA 读配置

- GIVEN MAA 已安装且配置里有第 1-7 与基建任务
- WHEN 界面请求方舟的子任务清单
- THEN 返回该配置里的任务项及各自的启用状态

#### Scenario: 引擎不在时退回默认

- GIVEN 某台机器没有安装 BetterGI
- WHEN 界面请求原神的子任务清单
- THEN 返回内置默认清单（一条龙里的常见项）
- AND 界面标注这是默认清单而非引擎实际配置

#### Scenario: 引擎报错不影响其他

- GIVEN 三月七的 `--list --json` 超时
- WHEN 用户打开编排页
- THEN 另外两个引擎的清单照常显示
- AND 星铁一项标注「未能读取」
### Requirement: 局部编排写回引擎配置

用户选择的子任务 SHALL 写回**引擎自己的配置文件**，使用引擎本来就识别的字段，
MUST NOT 修改引擎程序、MUST NOT 注入任何东西：

- MAA：写 `TaskQueue` 里对应任务的 `IsEnable`
- BetterGI：写 `OneDragon` 配置里的 `TaskEnabledList`
- 三月七：不改配置，直接把选中的 task id 依次传给命令行

写回前 SHALL 备份原文件（`.bak-orch`），SHALL 在原文件无法解析时放弃写入并报错，
MUST NOT 把引擎配置写坏。写回 SHALL 只改与子任务开关相关的字段，其余字段原样保留。

#### Scenario: MAA 只跑基建与公招

- GIVEN 用户在方舟步骤里只勾选了「基建」「公招」
- WHEN 开始执行
- THEN 写回 MAA 配置，使基建与公招 `IsEnable=true`，其余任务 `IsEnable=false`
- AND 其余字段（关卡、干员、配置名等）保持原样
- AND 执行完成后 MAA 只做这两件事

#### Scenario: 不改用户的其他配置

- GIVEN MAA 里有多套配置
- WHEN 编排写回子任务开关
- THEN 只影响当前选中的那套配置
- AND 其他配置一个字段都不变

#### Scenario: 配置损坏

- GIVEN MAA 的 `gui.new.json` 被外部写坏、无法解析
- WHEN 用户启动任务链
- THEN 该步失败并提示「MAA 配置无法解析，已跳过写回」
- AND 链上其余步骤照常执行

#### Scenario: 三月七不写配置

- GIVEN 用户在星铁步骤里勾选了「日常」「清体力」
- WHEN 开始执行
- THEN 用 `m7a.exe` 依次执行这两个 task id
- AND 三月七的配置文件不被修改
### Requirement: 任务链执行

系统 SHALL 从任务链的第一步开始依次执行，任一时刻只有一个步骤在运行。
每一步 SHALL 复用对应引擎现有的启动链路（前置检查、窗口焦点、清理策略）。

系统 SHALL 在每一步开始时把当前进度广播给手机端（第几步、共几步、当前是哪个游戏）。

#### Scenario: 正常跑完

- GIVEN 三步链全部成功
- WHEN 最后一步结束
- THEN 整条链标记为「成功」
- AND 返回每步的耗时与结果

#### Scenario: 进度可见

- GIVEN 链正在跑第二步（原神）
- WHEN 用户查看手机端
- THEN 显示「2/3 · 原神 · 运行中」
- AND 已完成的第一步显示「成功」与其耗时

#### Scenario: 上一步没结束不会开始下一步

- GIVEN 第一步仍在运行
- WHEN 观察第二步
- THEN 第二步处于「等待中」，不产生任何按键操作
### Requirement: 失败策略

默认策略 SHALL 为「失败跳过继续」：某一步失败或超时后，记录失败原因并继续执行下一步。
整条链跑完后 SHALL 给出总结：成功几步、失败几步、跳过几步。

用户 SHALL 能选择「失败即停」策略：任一步失败则中止整条链，后续步骤标记为「未执行」。

#### Scenario: 一步失败继续

- GIVEN 链是方舟 → 原神 → 星铁，方舟失败
- WHEN 执行继续
- THEN 原神与星铁照常执行
- AND 最终总结写明「1 失败 2 成功」

#### Scenario: 失败即停

- GIVEN 策略是「失败即停」，方舟失败
- WHEN 该步结束
- THEN 原神与星铁标记为「未执行」
- AND 整条链标记为「失败」

#### Scenario: 用户中途停止

- GIVEN 链正在跑第二步
- WHEN 用户点「停止」
- THEN 当前这一步被终止并标记「用户停止」
- AND 后续步骤标记为「未执行」
- AND 已完成的步骤保留其结果
### Requirement: 链与单步任务的关系

系统 SHALL 保持现有的「单游戏一键启动」入口可用。
任务链运行期间，单步启动 SHALL 被拒绝并说明「正在执行任务链」。

#### Scenario: 链运行时单步启动被拒

- GIVEN 任务链正在执行
- WHEN 用户在某个游戏页点「开始」
- THEN 拒绝启动并提示「正在执行任务链，请先停止」

#### Scenario: 单步任务不受影响

- GIVEN 用户没有运行任务链
- WHEN 用户在游戏页点「开始」
- THEN 行为与现在完全一致（跑该游戏的完整流程）
### Requirement: 编排界面（手机端）

APP SHALL 提供「编排」入口，展示任务链并允许编辑：

- 步骤列表，每步显示游戏图标、名称、子任务摘要、启用开关
- 拖动调整顺序
- 增删步骤
- 点进某一步可勾选子任务（来自能力清单）
- 底部一个「一键跑完整条链」按钮
- 运行中显示总进度与每步状态，可停止

编辑 SHALL 即时保存到电脑端；电脑端不可达时 SHALL 本地暂存并在恢复后同步。

#### Scenario: 默认链

- GIVEN 用户第一次打开编排页
- WHEN 页面加载
- THEN 显示默认链「明日方舟 → 原神 → 星铁」，三步都启用
- AND 每步的子任务是「按引擎当前配置全跑」

#### Scenario: 编辑并保存

- GIVEN 用户关掉方舟那步并调整了顺序
- WHEN 离开编排页再回来
- THEN 改动仍在（已保存到电脑端）

#### Scenario: 断网编辑

- GIVEN 手机与电脑断开
- WHEN 用户修改任务链
- THEN 改动暂存在手机本地
- AND 重连后自动同步到电脑端

#### Scenario: 运行时只读

- GIVEN 任务链正在执行
- WHEN 用户尝试编辑
- THEN 编辑入口被禁用并说明「执行中不能修改」

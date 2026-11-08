# task-launch

## Purpose

从手机上一键发起对应游戏的一条龙，并让用户清楚看到它是「在跑」「成功了」还是「失败了/自己停的」。

## Requirements

### Requirement: 三个游戏页各自一键启动

系统 SHALL 提供明日方舟、原神、星穹铁道 三个页面，每页一个「开始」按钮，点击后触发该游戏对应的一条龙流程。

#### Scenario: 启动原神一条龙

- GIVEN 已探测到 BetterGI 与《原神》且电脑未锁屏
- WHEN 用户在原神页点击「开始」
- THEN 电脑端先结束残留的 BetterGI 进程，再以管理员权限启动 `BetterGI.exe --startOneDragon`
- AND 页面进入「运行中」状态

#### Scenario: 启动星铁日常

- GIVEN 已探测到三月七小助手且电脑未锁屏
- WHEN 用户在星穹铁道页点击「开始」
- THEN 电脑端以管理员权限执行 `m7a.exe daily --after-finish None`
- AND 页面进入「运行中」状态

#### Scenario: 启动方舟一键长草

- GIVEN MAA 已配置远程控制端点且电脑端服务在线
- WHEN 用户在明日方舟页点击「开始」
- THEN 电脑端向 MAA 下发 `LinkStart` 任务
- AND 页面进入「运行中」状态

### Requirement: 前台任务互斥

系统 SHALL 保证同一时刻最多只有一个「占用前台键鼠」的任务在运行。

#### Scenario: 运行中重复点击

- GIVEN 已有任务正在运行
- WHEN 用户再次点击任意游戏页的「开始」
- THEN 电脑端拒绝启动新任务
- AND APP 提示「已有任务在运行」并显示当前任务

#### Scenario: 任务结束后可再次启动

- GIVEN 上一个任务已结束（成功、失败或用户停止）
- WHEN 用户点击「开始」
- THEN 允许启动新任务

### Requirement: 任务状态回传

系统 SHALL 把任务状态（排队 / 运行中 / 成功 / 失败 / 用户停止）回传给 APP，并保留可查看的执行记录。

#### Scenario: 任务成功

- GIVEN 任务正在运行
- WHEN 引擎报告成功（星铁退出码 0、原神日志出现一条龙完成、MAA 回报 SUCCESS）
- THEN APP 显示「成功」并记录耗时与结束时间

#### Scenario: 任务失败

- GIVEN 任务运行中发生失败
- WHEN 引擎报告失败或超过该任务的超时时间
- THEN APP 显示「失败」并给出可读原因
- AND 保留日志尾部供查看

#### Scenario: 用户主动停止

- GIVEN 任务正在运行
- WHEN 用户在 APP 点击「停止」
- THEN 电脑端终止该任务
- AND 状态记为「用户停止」，不算作失败

### Requirement: 启动前置检查

系统 SHALL 在启动任务前检查必要前置条件，不满足时拒绝启动并说明原因。

#### Scenario: 电脑锁屏

- GIVEN 电脑处于锁屏状态
- WHEN 用户点击「开始」
- THEN 拒绝启动并提示「请先在电脑上解锁」

#### Scenario: 工具未就绪

- GIVEN 对应工具或游戏路径未探测到
- WHEN 用户点击「开始」
- THEN 拒绝启动并提示「未找到 XXX，请先在设置中指定路径」

### Requirement: 运行期窗口焦点管理

系统 SHALL 在任务运行前把目标游戏窗口切到前台，并把其它自动化工具的窗口最小化，避免它们与游戏抢焦点。
窗口激活 SHALL 使用能绕过 Windows 前台锁的方式（附加输入队列），而不是仅调用 `SetForegroundWindow`。

#### Scenario: 多个工具窗口同时在

- GIVEN MAA、MuMu、BetterGI 等多个窗口都在前台
- WHEN 启动星铁任务
- THEN 系统把星铁窗口切到前台成功
- AND 其它工具窗口被最小化
- AND 引擎不再报「无法切换界面 / Failed to set window foreground」

#### Scenario: 只有游戏窗口

- GIVEN 没有其它工具窗口
- WHEN 启动任务
- THEN 直接激活游戏窗口并继续

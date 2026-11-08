# Delta：task-launch

## ADDED Requirements

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

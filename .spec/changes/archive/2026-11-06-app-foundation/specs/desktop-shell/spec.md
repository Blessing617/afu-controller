# Delta：desktop-shell

## Purpose

电脑端需要一个自己的桌面应用，替代命令行/批处理：双击即可启动服务、看到状态、读出配对码，并常驻托盘。这是「手机一点、电脑全自动」里「电脑侧不需要人操作」的前提。

## ADDED Requirements

### Requirement: 双击启动（自动提权）

系统 SHALL 提供电脑端桌面应用，双击运行后自动请求管理员权限，并以该权限启动本地服务。

#### Scenario: 首次启动
- GIVEN 电脑上没有正在运行的服务
- WHEN 用户双击桌面应用
- THEN 应用请求管理员权限（一次 UAC）
- AND 获得权限后启动本地服务并显示「运行中」

#### Scenario: 服务已在运行
- GIVEN 已有一个实例在运行
- WHEN 用户再次双击
- THEN 不启动第二个实例，而是把已有窗口显示到前台

#### Scenario: 用户拒绝提权
- GIVEN 用户在 UAC 对话框点了「否」
- WHEN 应用继续运行
- THEN 显示「需要管理员权限才能启动任务」的明确提示，而不是静默失败

### Requirement: 状态与配对展示

系统 SHALL 在桌面应用中显示服务状态、配对码、以及三个游戏/工具的可用性。

#### Scenario: 展示配对码
- GIVEN 尚无手机配对
- WHEN 用户查看桌面应用
- THEN 显示 6 位配对码与 Tailscale 地址，便于手机输入

#### Scenario: 展示引擎状态
- GIVEN 服务已运行
- WHEN 用户查看桌面应用
- THEN 显示三个游戏各自是否可用（依赖的游戏与工具是否都已探测到）

### Requirement: 服务控制与退出

系统 SHALL 允许用户从桌面应用停止/重启服务，并在退出时正确清理。

#### Scenario: 停止服务
- GIVEN 服务正在运行且没有任务在执行
- WHEN 用户点击「停止服务」
- THEN 服务停止，界面显示「已停止」

#### Scenario: 退出应用
- GIVEN 用户关闭窗口
- WHEN 应用退出
- THEN 服务随之停止，不残留后台进程

#### Scenario: 任务运行中退出
- GIVEN 有任务正在执行
- WHEN 用户尝试退出
- THEN 提示「有任务正在运行」，由用户确认后再退出

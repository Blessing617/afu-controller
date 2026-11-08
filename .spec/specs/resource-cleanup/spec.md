# resource-cleanup

## Purpose

游戏和模拟器跑起来后非常吃内存（实测 MuMu 一项就占 12.8GB 提交内存，曾把整机压到只剩 2GB）。任务结束后必须能把它们收掉，手机端也要能随时主动释放。

## Requirements

### Requirement: 任务结束后自动清理

系统 SHALL 在任务正常结束或失败后，自动关闭该任务拉起的游戏与工具进程，释放内存。
方舟任务 SHALL 关闭 MuMu 的**主程序**（不只是虚拟机进程）——实测只关虚拟机会让 `MuMuNxMain` 常驻。

#### Scenario: 任务成功结束

- GIVEN 某个游戏任务成功完成
- WHEN 任务进入 `success` 状态
- THEN 关闭该游戏对应的游戏进程与自动化工具
- AND 方舟任务关闭 MuMu 主程序与虚拟机

#### Scenario: 任务失败或超时

- GIVEN 任务以 `failed` 或 `timeout` 结束
- WHEN 任务进入终态
- THEN 同样执行清理，避免残留进程继续占用内存

#### Scenario: 用户主动停止

- GIVEN 任务被用户停止（`stopped`）
- WHEN 任务进入终态
- THEN **不**自动清理（用户可能还要继续用电脑）

#### Scenario: 清理可以关闭

- GIVEN 用户希望任务结束后保留游戏
- WHEN 配置里把自动清理关掉
- THEN 任务结束不再动这些进程

### Requirement: 手机端主动释放

系统 SHALL 提供接口让手机端随时关闭指定游戏的相关进程。

#### Scenario: 从手机释放方舟
- GIVEN 方舟任务已结束但 MuMu 仍在运行
- WHEN 用户在方舟页点击「关闭并释放」
- THEN 电脑端关闭 MAA 与模拟器
- AND 返回释放了哪些进程

#### Scenario: 释放时没有相关进程
- GIVEN 目标进程本来就没在跑
- WHEN 用户点击「关闭并释放」
- THEN 正常返回，提示「没有需要关闭的进程」

#### Scenario: 释放不影响其他游戏
- GIVEN 原神相关进程也在运行
- WHEN 用户在方舟页执行释放
- THEN 只关闭方舟相关进程，原神的不受影响

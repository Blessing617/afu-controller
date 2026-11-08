# Delta：performance

## Purpose

（本能力已有主规格，这里只追加本次新增的预算。既有的「界面线程不阻塞」「截图预算」
「解码不占主线程」等约束继续有效，不改动。）

## ADDED Requirements

### Requirement: 两端常驻内存预算

系统 SHALL 把「不玩游戏时」的常驻内存控制在下列范围内，为游戏腾出可用内存：

- **电脑端**：桌面端窗口 + 服务端合起来，空闲稳定 60 秒后的工作集 MUST ≤ 120MB（修复前实测约 132MB）
- **电脑端任务期间**：相对空闲值的增量 MUST ≤ 60MB
- **手机端**：已连接、无任务时的进程内存 MUST ≤ 200MB，且同一时刻只保留一张画面位图

内存 MUST NOT 随运行时长、日志长度、轮询次数持续增长（无泄漏）。

测量口径：电脑端用 `Get-Process` 的 `WorkingSet64`；手机端用 `adb shell dumpsys meminfo`。
数值 MUST 能在真机上用命令复现，不靠目测。

#### Scenario: 空闲内存达标

- GIVEN 电脑端启动并停在「总览」页
- WHEN 静置 60 秒后读取工作集
- THEN ≤ 120MB

#### Scenario: 长跑不涨内存

- GIVEN 电脑端连续运行 6 小时（期间有任务、有截图请求）
- WHEN 再次读取工作集
- THEN 与启动时的差值 ≤ 15MB

#### Scenario: 手机端只留一张画面

- GIVEN 用户在三个游戏页之间来回切换
- WHEN 观察手机端内存
- THEN 不随切页次数增加而增长
- AND 同一时刻只持有一张已解码的画面

### Requirement: 手机端推送优先

系统 SHALL 优先用 WebSocket 推送来更新任务状态与进度；只有在 WebSocket 不可用时才退回轮询。
有 WebSocket 连接时，手机端 MUST NOT 再以高频轮询拉取同一份状态。

无 WebSocket 时的兜底轮询间隔 SHALL ≥ 15 秒；断开检测仍 SHALL 在 15 秒内完成
（由 WebSocket 关闭事件或一次失败请求直接判定，不依赖多轮轮询）。

#### Scenario: 有推送时不轮询

- GIVEN 手机已通过 WebSocket 连上电脑端
- WHEN 静置 3 分钟
- THEN 状态请求次数为 0（除非用户主动刷新）
- AND 状态变化由推送即时反映

#### Scenario: 推送不可用时保持断开检测

- GIVEN WebSocket 建立失败（代理不支持升级）
- WHEN 电脑端服务停止
- THEN 手机端在 15 秒内显示「已断开」
- AND 轮询频率不高于每 15 秒一次

### Requirement: 电脑端空闲 CPU 预算

系统 SHALL 在空闲时把 CPU 占用控制在「单核 1% 以内为常态」，MUST NOT 用高频定时器做无变化的刷新。

#### Scenario: 空闲不空转

- GIVEN 电脑端已启动、没有任务、手机端未连接
- WHEN 观察 5 分钟的平均 CPU
- THEN ≤ 单核 1%
- AND 没有每秒多次的子进程调用

### Requirement: 截图链路的内存可复用

系统 SHALL 复用截图链路的缓冲区与编码器，MUST NOT 每张截图都重新分配整屏大小的像素缓冲。

#### Scenario: 连续截图不涨内存

- GIVEN 用户连续请求 50 张画面
- WHEN 观察服务端内存
- THEN 峰值与首张时相差 ≤ 20MB
- AND 单张耗时仍在既有预算内（通常 < 200ms）

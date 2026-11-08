# performance

## Purpose

定义两端的「不卡」边界，并把卡顿点收敛成可检查的约束。
合并后与 `live-screen` 的截图预算、`desktop-shell` 的「界面不冻结」保持一致。

## Requirements

### Requirement: 界面线程不做阻塞调用

电脑端 SHALL 在界面线程上不做任何阻塞操作：发起子进程、读取子进程输出、
枚举网络地址、读写磁盘日志，MUST NOT 在界面线程执行。
周期性刷新 SHALL 由后台线程完成，并通过信号把结果送回界面线程。
同一类周期刷新 SHALL NOT 存在多个计时器各拉一次。

#### Scenario: 连接页静置不卡

- GIVEN 用户停留在「连接」页，什么都不点
- WHEN 静置 60 秒
- THEN 窗口可随时拖动、导航可点、按钮有即时反馈
- AND 后台的 `tailscale` 查询按固定间隔在后台线程进行，界面线程不被占用

#### Scenario: 子进程调用失败也不卡

- GIVEN 电脑上没有安装 Tailscale
- WHEN 界面启动并进行周期性刷新
- THEN 与平时一样流畅
- AND 不出现界面冻结或按钮点不动


### Requirement: 手机端状态更新只重组变化部分

手机端 SHALL 在轮询拿到的数据与当前状态相同时**不发射新状态**，
MUST NOT 因为「又轮询了一次」而让整棵界面树重组。

画面帧更新 SHALL 只让画面区重组，MUST NOT 连带重组游戏页的其余部分。

#### Scenario: 空闲轮询不引起重组

- GIVEN APP 已连接电脑且没有任务在运行
- WHEN 静置 30 秒（期间完成 6 次轮询，数据没有变化）
- THEN 界面不产生因轮询引起的重组
- AND 不出现周期性的画面闪烁

#### Scenario: 新画面到达只刷新画面区

- GIVEN 任务正在运行，画面每 20 秒刷新一张
- WHEN 新一张画面到达
- THEN 只有画面区发生变化
- AND 任务状态卡与主操作按钮不重新组合


### Requirement: 画面解码不占主线程

手机端 SHALL 在后台线程完成 JPEG 解码与位图转换，MUST NOT 在组合阶段做解码。

#### Scenario: 大图到达不掉帧

- GIVEN 服务端返回一张宽度为 960 的 JPEG
- WHEN APP 收到并显示
- THEN 解码发生在后台线程
- AND 界面在解码期间保持可交互


### Requirement: 画面请求只取当前页

手机端 SHALL 只为当前停留的游戏页请求画面，切到别的页面后 SHALL 立即停止对上一页的请求；
三个游戏页共用同一张全屏截图时，SHALL 复用已在内存中的那一张，MUST NOT 因切页而重新拉取。

#### Scenario: 切页不重复拉图

- GIVEN 用户停留在明日方舟页，已有一张画面
- WHEN 用户切到原神页
- THEN 页面直接显示已有的那张画面
- AND 不发起新的画面请求（除非用户手动点「刷新一张」）


### Requirement: 截图性能与体积

系统 SHALL 保证单张「截图 + 缩放 + JPEG 编码」的服务端耗时通常低于 200ms，
输出宽度不超过 960 像素，JPEG 体积不超过 300KB。

#### Scenario: 性能预算

- GIVEN 2560×1600 屏幕
- WHEN 请求一张默认 quality 的画面
- THEN `X-Capture-Ms` 通常在 200 以内
- AND 输出宽度为 960，JPEG 不超过 300KB


### Requirement: 界面不冻结

应用 SHALL 保证界面在后台执行耗时操作（路径探测、服务启动、隧道建立、依赖检查）期间保持响应。
界面 SHALL 在耗时操作进行中显示进行状态，而不是无反馈地卡住。

启动后的首屏 SHALL 在服务与探测完成之前就显示出来并可用，MUST NOT 等到全部后台任务结束才绘制窗口。

#### Scenario: 重新探测期间

- GIVEN 用户点击「重新检查」
- WHEN 探测正在扫描磁盘
- THEN 窗口仍可拖动、可切换导航
- AND 有明确的「正在检查…」指示

#### Scenario: 服务启动中

- GIVEN 用户刚启动应用
- WHEN 服务还没就绪
- THEN 界面正常显示并给出进度提示
- AND 不出现白窗或无响应

#### Scenario: 首屏先出来

- GIVEN 用户双击程序
- WHEN 界面出现
- THEN 各页面骨架已可见并在显示「正在…」占位
- AND 不出现「窗口空白几秒才出现内容」

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


### Requirement: 界面动效的性能预算

两端 SHALL 在播放界面动效时保持流畅，MUST NOT 用动画掩盖卡顿：

- 电脑端：页面切换与按压动效期间，窗口 MUST 可拖动、导航可点；
  动效 MUST NOT 阻塞界面线程，MUST NOT 在滚动区域内使用投影特效。
- 手机端：动效期间 MUST NOT 出现可感知掉帧；无限循环动画 MUST 只出现在
  「任务正在运行」的主按钮上，任务停止后 MUST 立即取消。
- 两端：动效 MUST NOT 引起布局抖动（相邻控件位移），
  系统开启「减少动画」时 MUST 退化为直接切换且功能不变。

验证口径：手机端 MUST 用 release 包在真机上测量，MUST NOT 用 debug 包的数据下结论；
电脑端 MUST 用实际窗口交互观察，MUST NOT 只凭代码推断。

#### Scenario: 切页不卡

- GIVEN 用户连续快速点击三个导航项
- WHEN 动效播放中
- THEN 窗口可拖动、点击有响应
- AND 不出现「窗口未响应」或白屏

#### Scenario: 循环动画不常驻

- GIVEN 没有任务在运行
- WHEN 静置 30 秒观察 CPU 与帧
- THEN 界面上没有任何无限循环动画
- AND CPU 占用不因动画上升

#### Scenario: release 包测量

- GIVEN 手机已连上电脑
- WHEN 安装 release 包并操作界面
- THEN 记录到的掉帧比例低于可感知阈值
- AND 测量命令与结果写在验证记录里，可复现

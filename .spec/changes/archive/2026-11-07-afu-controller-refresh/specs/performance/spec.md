# Delta：performance

## Purpose

定义两端的「不卡」边界，并把卡顿点收敛成可检查的约束。
合并后与 `live-screen` 的截图预算、`desktop-shell` 的「界面不冻结」保持一致。

## ADDED Requirements

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

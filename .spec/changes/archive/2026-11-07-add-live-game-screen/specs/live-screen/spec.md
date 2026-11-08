# Delta：live-screen

## Purpose

把电脑屏幕的实时画面送到手机上：服务端按需截图并编码成 JPEG，APP 在游戏页按需刷新显示。让用户不用坐在电脑前，就能确认「任务跑得怎么样、卡在哪一步」。

## ADDED Requirements

### Requirement: 屏幕截图

系统 SHALL 在收到请求时截取**整个电脑屏幕**并编码成 JPEG，不依赖各引擎的私有接口，也不引入 ffmpeg 等重型依赖。
截图 SHALL 只读取屏幕内容，SHALL NOT 改变任何窗口的激活状态、位置、层级或大小。
截图 SHALL NOT 因为「某个游戏窗口不在」而失败——屏幕上是什么就截什么；游戏窗口被别的窗口挡住时，截到的自然就是挡住它的窗口。

方舟（跑在模拟器里）SHALL 优先通过模拟器的 ADB 截屏取得模拟器内部画面；ADB 不可用时退回全屏截图。

#### Scenario: 三个游戏都能出图

- GIVEN 电脑端服务在线
- WHEN 分别请求 arknights / genshin / starrail 的画面
- THEN 每次都返回一张该时刻的屏幕截图
- AND 三个游戏返回的是同一类全屏画面（不需要按游戏区分）

#### Scenario: 游戏没开

- GIVEN 电脑上没有任何游戏在运行
- WHEN 请求画面
- THEN 仍然返回当前屏幕截图（桌面），而不是报「找不到窗口」

#### Scenario: 方舟走模拟器 ADB

- GIVEN MuMu 模拟器正在运行且 adb 里能看到 `emulator-*` 设备
- WHEN 请求明日方舟的画面
- THEN 返回的是模拟器内部画面（没有窗口标签栏/工具条）
- AND ADB 不可用时自动退回全屏截图，不报错

#### Scenario: 屏幕全黑

- GIVEN 屏幕已关闭或处于休眠
- WHEN 请求画面
- THEN 返回错误码 `capture_black` 与「请先唤醒电脑」的文案
- AND 不返回黑图

### Requirement: 截图接口

系统 SHALL 提供 `GET /api/screen/{game}` 返回 `image/jpeg`：

- `game` 取值 `arknights` / `genshin` / `starrail`，其它值返回 404 `unknown_game`
- 支持 `quality` 参数，默认 70，有效范围 30–90，越界时夹紧到边界值而不是报错
- 与其它受保护接口一致，需要配对 token
- 成功响应 SHALL 携带 `X-Captured-At`（截图时间）、`X-Capture-Ms`（服务端处理耗时）、`X-Image-Width`、`X-Image-Height`
- 失败响应 SHALL 是 JSON，顶层含 `error` 与 `message` 字段

#### Scenario: 正常取图

- GIVEN 已配对
- WHEN 请求 `/api/screen/genshin`
- THEN 返回 200、`Content-Type: image/jpeg`，并带四个元信息头

#### Scenario: 按 quality 调节

- GIVEN 同一屏幕
- WHEN 分别以 `quality=40` 与 `quality=90` 请求
- THEN 前者体积明显更小，两者都能正常显示

#### Scenario: quality 越界

- GIVEN `quality` 传 0 或 999
- WHEN 请求画面
- THEN 服务端夹紧为 30 / 90 并正常返回图片

#### Scenario: 未知游戏

- GIVEN 请求 `/api/screen/minecraft`
- THEN 返回 404，`error` 为 `unknown_game`

#### Scenario: 未配对

- GIVEN 请求未携带有效 token
- THEN 返回 401，且不含任何画面内容

### Requirement: 截图性能与体积

系统 SHALL 保证单张「截图 + 缩放 + JPEG 编码」的服务端耗时通常低于 200ms，输出宽度不超过 1280 像素，JPEG 体积不超过 300KB。

#### Scenario: 性能预算

- GIVEN 2560×1600 屏幕
- WHEN 请求一张默认 quality 的画面
- THEN `X-Capture-Ms` 通常在 200 以内
- AND 输出宽度为 1280，JPEG 不超过 300KB

### Requirement: 截图不拖慢任务

系统 SHALL 保证截图不影响正在运行的任务：不激活窗口、不抢焦点；多个请求串行处理；单张截图失败 SHALL NOT 写入任务日志，SHALL NOT 改变任务状态。

#### Scenario: 任务运行中连续刷新

- GIVEN 某游戏任务正在运行
- WHEN APP 每 1.5 秒请求一次画面
- THEN 任务日志不出现焦点或点击类错误
- AND 任务继续正常执行

#### Scenario: 截图失败不影响任务

- GIVEN 任务运行中，截图因屏幕休眠失败
- WHEN 服务端返回 `capture_black`
- THEN 任务继续运行，该错误不进入任务日志

### Requirement: 截图不残留、不堆积

系统 SHALL NOT 把截图写入磁盘，SHALL NOT 保留历史帧；每次截图 SHALL 释放它占用的 GDI 资源。
APP SHALL 只保留每个游戏最新的一张画面，不累积历史帧。
连续大量请求之后，服务端与 APP 的内存、句柄占用 SHALL 回到稳定区间。

#### Scenario: 服务端连续请求不泄漏

- GIVEN 服务运行中
- WHEN 连续请求 300 次画面
- THEN GDI 句柄数没有持续增长
- AND 内存稳定
- AND 磁盘上没有产生任何截图文件

#### Scenario: 客户端只留最新一帧

- GIVEN APP 连续刷新 100 张画面
- THEN 内存不随刷新次数增长，只保留最新一张

### Requirement: APP 端画面区域

APP SHALL 在每个游戏页提供「画面」区域，显示该游戏最近一张截图、截图时间、以及失败原因。

#### Scenario: 任务运行中自动刷新

- GIVEN 该游戏任务正在运行且手机已连接
- WHEN 用户停留在该游戏页
- THEN 每隔 1~2 秒自动刷新一张新画面

#### Scenario: 任务结束停止刷新

- GIVEN 任务结束
- WHEN 用户继续停留
- THEN 自动刷新停止
- AND 最后一张保留显示并标记「旧快照」

#### Scenario: 手动刷新

- GIVEN 任务未运行
- WHEN 用户点「刷新一张」
- THEN 请求并显示一张新画面

#### Scenario: 截图失败提示

- GIVEN 服务端返回 `capture_black` 或网络错误
- WHEN APP 刷新
- THEN 画面区显示对应中文原因
- AND 若之前有成功的图，保留它并显示它的截图时间
- AND 不显示空白或黑图

#### Scenario: 显示截图时间

- GIVEN 成功拿到一张画面
- THEN 画面区显示这张图的截图时间（精确到秒）

#### Scenario: 离开页面暂停刷新

- GIVEN 该游戏任务正在运行，画面正在自动刷新
- WHEN 用户切换到别的游戏页或把 APP 切到后台
- THEN 停止对该游戏的刷新请求
- AND 回到该游戏页时立即刷新一张

#### Scenario: 未连接

- GIVEN 手机与电脑断开
- WHEN 用户查看游戏页
- THEN 画面区停止自动请求并提示连接已断开

# Delta：live-screen

## MODIFIED Requirements

### Requirement: 屏幕截图

系统 SHALL 在收到请求时截取**整个电脑屏幕**并编码成 JPEG，不依赖各引擎的私有接口，也不引入 ffmpeg 等重型依赖。
截图 SHALL 只读取屏幕内容，SHALL NOT 改变任何窗口的激活状态、位置、层级或大小。
截图 SHALL NOT 因为「某个游戏窗口不在」而失败——屏幕上是什么就截什么；游戏窗口被别的窗口挡住时，截到的自然就是挡住它的窗口。

三个游戏 SHALL 走完全相同的截图路径，MUST NOT 为其中某一个单独走模拟器/ADB 之类的外部通道。

> （原为：方舟优先走模拟器 ADB 截屏，ADB 不可用时退回全屏截图。已移除——ADB 要另起
> 子进程、路径依赖模拟器安装位置，与「三个游戏一套代码」的目标冲突，且用户实际只看全屏。）

#### Scenario: 三个游戏都能出图

- GIVEN 电脑端服务在线
- WHEN 分别请求 arknights / genshin / starrail 的画面
- THEN 每次都返回一张该时刻的屏幕截图
- AND 三个游戏返回的是同一类全屏画面（不需要按游戏区分）

#### Scenario: 游戏没开

- GIVEN 电脑上没有任何游戏在运行
- WHEN 请求画面
- THEN 仍然返回当前屏幕截图（桌面），而不是报「找不到窗口」

#### Scenario: 方舟不依赖 ADB

- GIVEN 电脑上没有安装 adb，也没有模拟器
- WHEN 请求明日方舟的画面
- THEN 正常返回全屏截图
- AND 服务端不尝试启动 adb 子进程

#### Scenario: 屏幕全黑

- GIVEN 屏幕已关闭或处于休眠
- WHEN 请求画面
- THEN 返回错误码 `capture_black` 与「请先唤醒电脑」的文案
- AND 不返回黑图

### Requirement: APP 端画面区域

APP SHALL 在每个游戏页提供「画面」区域，显示该游戏最近一张截图、截图时间、以及失败原因。

画面区域 SHALL 位于游戏页的**固定层**，切换游戏页时画面区 MUST NOT 被销毁重建；
MUST NOT 出现「切到另一个游戏页时整页刷新」的观感。

#### Scenario: 任务运行中自动刷新

- GIVEN 该游戏任务正在运行且手机已连接
- WHEN 用户停留在该游戏页
- THEN 每隔 15~20 秒自动刷新一张新画面

#### Scenario: 任务结束停止刷新

- GIVEN 任务结束
- WHEN 用户继续停留
- THEN 自动刷新停止
- AND 最后一张保留显示并标记「旧快照」

#### Scenario: 手动刷新

- GIVEN 任务未运行
- WHEN 用户点「刷新一张」
- THEN 请求并显示一张新画面

#### Scenario: 切换游戏页不刷新整页

- GIVEN 用户停留在明日方舟页，画面区已有一张图
- WHEN 用户点底栏切到原神页
- THEN 画面区继续显示同一张图（不闪白、不出现加载圈）
- AND 页面其余部分（标题、状态行、主操作按钮）在各页之间保持稳定，不发生整体重建
- AND 原神任务没有在运行时，不自动发起新的截图请求

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

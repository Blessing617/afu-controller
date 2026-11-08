# Delta：desktop-shell

## ADDED Requirements

### Requirement: 切换页面的过渡动效

电脑端 SHALL 在切换导航项时播放一致的过渡动效，参考阿福记账的动效语言：

- 时长 SHALL 在 160~260ms 之间，使用缓出（decelerate）或弹簧曲线，MUST NOT 线性匀速
- 内容 SHALL 有轻微的方向位移（位移幅度不超过内容区宽度的 6%），MUST NOT 整页大幅平移
- 内容 SHALL 有淡入，旧内容直接消失，MUST NOT 出现两页同时可见的重叠闪烁
- 系统开启「减少动画」时（Windows 的「显示动画」关闭）SHALL 退化为直接切换，功能不变

#### Scenario: 切换导航有过渡

- GIVEN 用户在「总览」页
- WHEN 点击「依赖清单」
- THEN 新内容在 260ms 内淡入并带小幅位移落位
- AND 不出现整页左右滑动的夸张效果
- AND 不出现白屏

#### Scenario: 减少动画

- GIVEN 系统设置里关闭了窗口动画
- WHEN 用户切换导航项
- THEN 直接切换到目标页面
- AND 不播放任何过渡

### Requirement: 部分游戏可用时的表现

总览页 SHALL 用一张卡片展示三款游戏与各自依赖的状态；
当只有一款或两款游戏可用时，界面 SHALL 照常显示，其余游戏标为「缺 XX」，MUST NOT 报错或隐藏整块区域。

#### Scenario: 只配好一款游戏

- GIVEN 电脑上只有原神与 BetterGI
- WHEN 用户打开总览页
- THEN 原神一行显示「可用」
- AND 方舟一行显示「缺 MAA、MuMu」，星铁一行显示「缺 三月七」
- AND 其它卡片（服务、连接信息、依赖）正常显示

#### Scenario: 全部未装

- GIVEN 什么依赖都没装
- WHEN 用户打开总览页
- THEN 三行都给出缺失清单
- AND 不出现异常弹窗

## MODIFIED Requirements

### Requirement: 界面视觉与导航结构

电脑端应用 SHALL 采用**侧边栏导航 + 内容区卡片**的结构，而不是把所有信息堆在同一个窗口里。
应用 SHALL 提供深色与浅色两套主题，并跟随系统设置。
应用 SHALL NOT 使用操作系统默认控件外观（如 Windows 经典按钮、灰底窗体）。

侧边栏的品牌区 SHALL 显示应用图标（大肥鱼抱手柄）与产品名「阿福代肝控制器」。
导航项 SHALL 收敛为：总览 / 依赖清单 / 设置。
「连接」SHALL 作为总览页内的一组卡片呈现（地址 + 配对码 + Funnel 检查表），
SHALL NOT 单独占据一个导航项——它是给用户照抄去手机上的信息，不是需要「进入」的页面。

#### Scenario: 启动后的第一屏

- GIVEN 用户双击应用
- WHEN 界面显示出来
- THEN 左侧有导航项（总览、依赖清单、设置）
- AND 右侧内容区以卡片形式组织信息
- AND 整体为深色或浅色主题之一，跟随系统
- AND 品牌区显示大肥鱼图标与「阿福代肝控制器」

#### Scenario: 切换导航

- GIVEN 应用正在运行
- WHEN 用户在左侧点击「依赖清单」
- THEN 右侧切换到依赖清单内容
- AND 当前导航项有明确的选中态

#### Scenario: 窗口缩放

- GIVEN 用户把窗口拖大到接近全屏或缩小到最小尺寸
- WHEN 界面重新布局
- THEN 内容不错位、不重叠、不被截断
- AND 关键操作按钮始终可见

#### Scenario: 连接信息不再是一个导航项

- GIVEN 应用正在运行
- WHEN 用户查看侧边栏
- THEN 没有「连接」这一项
- AND 地址、配对码、Funnel 四步检查表都在「总览」页里

### Requirement: 桌面端应用图标

应用 SHALL 拥有自己的图标，用于窗口标题栏、任务栏与可执行文件本身。
图标 SHALL 为项目原创矢量图形，并打包进 exe；图形内容为「大肥鱼抱手柄」，
由 `assets/icons/app-icon.svg` 作为单一源文件，`.ico` 由脚本从它生成。

#### Scenario: 任务栏与任务管理器

- GIVEN 应用正在运行
- WHEN 用户查看任务栏图标或任务管理器
- THEN 显示的是本项目图标，而不是 Python 或系统默认图标

#### Scenario: exe 文件图标

- GIVEN 用户拿到打包好的程序目录
- WHEN 在资源管理器里查看 `阿福代肝控制器.exe`
- THEN 显示本项目图标

#### Scenario: 图标文件不手工维护

- GIVEN 需要修改图标
- WHEN 只改 `assets/icons/app-icon.svg` 并运行图标生成脚本
- THEN `icon.ico`、PNG 预览与安卓图标资源全部同步更新
- AND 不需要手工导出任何一张图

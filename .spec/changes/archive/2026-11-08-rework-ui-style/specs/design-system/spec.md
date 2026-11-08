# Delta：design-system

## Purpose

两端（电脑端 PySide6 / 手机端 Compose）共用一套可检查的设计系统：
配色、形状、字阶、间距、组件质感与动效曲线都来自同一组数值，
且这些数值由脚本比对而不是靠人记。
本能力只管「长什么样、动起来什么样」，不描述任何功能行为。

## ADDED Requirements

### Requirement: 两端共用的视觉 token

系统 SHALL 维护一份两端共用的视觉 token，至少包含：配色（背景 / 卡片面 / 次级面 / 主色 /
主色深 / 强调 / 成功 / 警告 / 危险 / 文字 / 次要文字）、形状（卡片圆角 / 控件圆角 / 标签圆角）、
间距（4 / 8 / 12 / 16 / 20 / 24 六档）、字阶（标题 / 小标题 / 正文 / 次要 / 数字大字）与
动效曲线（press / enter / state 三条）。

token SHALL 有两个落地文件：电脑端 `desktop/tokens.py`、手机端
`android/app/src/main/java/com/afu/controller/ui/Theme.kt`。
两份文件中的同名 token MUST 取相同的值。

系统 SHALL 提供一个不依赖构建的比对脚本，逐项比较两份文件中的 token 数值；
不一致时脚本 MUST 以非零退出码失败并列出差异项。

#### Scenario: token 一致时通过

- GIVEN 两端 token 文件内容一致
- WHEN 运行比对脚本
- THEN 退出码为 0
- AND 输出每一项 token 的名称与数值

#### Scenario: 有人只改了一端

- GIVEN 有人把手机端主色改成另一个值
- WHEN 运行比对脚本
- THEN 退出码非零
- AND 输出明确指出「主色」在两端不一致、各自的值是多少

### Requirement: 糖果组件质感

两端 SHALL 提供同一套组件质感，至少覆盖：卡片、主按钮、次级按钮、幽灵按钮、状态胶囊、
输入框、选择胶囊、对话框。

- 卡片 SHALL 为纯色面 + 大圆角（22），MUST NOT 使用投影特效作为主要分层手段。
- 主按钮 SHALL 为「主色填充 + 白字 + 底部 2px 深色厚度」，形似糖果；
  次级按钮 SHALL 为次级面填充 + 主色文字；幽灵按钮 SHALL 默认只显示文字，
  悬停/按压时出现次级面底色。
- 所有可点击控件 SHALL 有一致的按压反馈：缩放 0.96 + 亮度降低，松开以弹簧回弹。
- 手机端 MUST NOT 直接使用 Material3 的 `AlertDialog`、`TimePicker`、`FilterChip`、
  `AssistChip` 的默认外观作为用户可见控件；需要这些交互时 SHALL 用本项目组件实现同样的行为。

#### Scenario: 两端按钮像一家人

- GIVEN 电脑端总览页与手机端游戏页各自展示一个主操作按钮
- WHEN 并排观察两张截图
- THEN 两者都是圆角胶囊、同一主色、同样的按压观感
- AND 没有一端出现系统默认按钮外观

#### Scenario: 手机上不出现 Material 时钟盘

- GIVEN 用户在手机端编排页点击「添加时间」
- WHEN 选择器弹出
- THEN 出现的是本项目自绘的时间选择器
- AND 不出现 Material3 的圆形时钟盘 `TimePicker`

### Requirement: 动效语言

两端 SHALL 使用同一组动效参数：

| 名称 | 时长 | 用途 |
|---|---|---|
| press | 140ms，弹簧曲线（含轻微过冲） | 按钮按下与松开 |
| enter | 220ms，缓出 + 不超过 6% 位移 | 页面切换、卡片进场 |
| state | 150ms，缓入缓出 | 开关、选中态、颜色过渡 |

系统 MUST NOT 使用线性匀速曲线做界面过渡（进度条除外）。

#### Scenario: 切换页面有回弹感但不是弹球

- GIVEN 用户在电脑端从「总览」切到「依赖清单」
- WHEN 新页面出现
- THEN 内容在 220ms 内淡入并小幅落位
- AND 不出现整页横移或连续多次弹跳

### Requirement: 界面资源本地化

两端界面使用的字体、图标、装饰图形 SHALL 随应用一起分发，MUST NOT 在运行时联网加载。

图标与装饰 SHALL 为项目原创的矢量图形或明确许可的开源资源，
MUST NOT 包含游戏厂商的美术素材或商标图案。

#### Scenario: 断网仍完整

- GIVEN 电脑没有连接互联网
- WHEN 打开电脑端与手机端界面
- THEN 字体、图标、装饰全部正常显示
- AND 不出现方块字符或空白图标

#### Scenario: 没有厂商素材

- GIVEN 检查组内所有界面资源文件
- WHEN 逐个核对来源
- THEN 每个文件都能对应到「本项目原创」或「明确许可的开源资源」
- AND 不含任何游戏角色立绘、Logo 或官方 UI 截图

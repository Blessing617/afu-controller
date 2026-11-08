# new-user-onboarding

## Purpose

把应用从「只有作者这台机器能跑」变成「任何人都能跑」：新用户第一次打开时，系统能告诉他缺什么、去哪装、装好后怎么确认，而不是丢一个全是「⚠ 缺少组件」的界面让他自己猜。

## Requirements


### Requirement: 依赖清单与官网入口

系统 SHALL 在教程与界面上给出运行所需外部软件的官网下载地址，
每项说明它「是干什么用的」以及「装好之后怎么确认」。

教程 SHALL 建议用户**先单独把每个工具跑通一次**，再回来配置本程序。

#### Scenario: 查看三个工具的安装说明

- GIVEN 用户打开教程第一步
- WHEN 他展开「明日方舟 → MAA + MuMu」
- THEN 看到官网下载地址与逐步安装要点
- AND 提示「解压到简单路径，别放 Program Files」
- AND 提示 MAA 需要开启远程控制

#### Scenario: 装完不知道对不对

- GIVEN 用户装完三个工具
- WHEN 他打开本程序的「依赖清单」页
- THEN 每项显示「已就绪」或「未安装」
- AND 未安装的项旁有官网链接

### Requirement: 首次启动引导

系统 SHALL 提供一份**图文教程**，覆盖从零到能用的完整过程，
并在首次启动时引导用户查看。
教程 SHALL 同时以两种形式存在：程序内的引导页，以及仓库里的 Markdown 文档，
两者 SHALL 描述同一套步骤。

教程 SHALL 按以下顺序组织，每一步都要说清「做什么、为什么、做完之后是什么样」：

1. **适用性说明**：这个程序是干什么的、不干什么、适合谁用
2. **前置工具安装**：MAA / MuMu / BetterGI / 三月七小助手 / 游戏本体的下载与安装要点
3. **公网地址获取**：Tailscale 的注册、安装、登录、开启 Funnel 四步，
   并说明「哪一步做完之后才有地址」
4. **电脑端安装与界面说明**
5. **手机 APP 安装与连接**
6. **日常使用**

教程 SHALL 包含本程序自身界面的截图。

#### Scenario: 新用户第一次打开

- GIVEN 数据目录为空（新机器、新解压）
- WHEN 用户双击运行桌面应用
- THEN 自动打开图文引导页
- AND 引导页可逐步骤浏览，也可点击顶部步骤条直接跳转

#### Scenario: 引导内容完整

- GIVEN 用户打开引导页
- WHEN 他按顺序看完六步
- THEN 每一步都能看到「要做什么」与「做完之后是什么样」
- AND 包含本程序总览页、手机连接页、手机游戏页的截图

#### Scenario: 明确说明不做什么

- GIVEN 用户在看第 0 步
- WHEN 他读到适用性说明
- THEN 明确写出「本程序不替你操作游戏，只是遥控器」
- AND 明确写出封号风险没有任何官方承诺

#### Scenario: 第三方工具的界面不作为教程素材

- GIVEN 教程涉及 MAA / BetterGI / 三月七 / Tailscale
- WHEN 教程展示这些工具相关内容
- THEN 只给出官网下载地址与安装要点
- AND 不引用这些工具的界面截图（它们不属于本项目，也没必要）

#### Scenario: 跳过引导

- GIVEN 引导流程展示中
- WHEN 用户选择跳过
- THEN 直接进入主界面
- AND 该跳过决定被记住

### Requirement: 缺失依赖的可读说明

当用户尝试启动某个游戏任务而其依赖缺失时，系统 SHALL 明确说明**缺的是哪一项**、以及**去哪里获取**，而不是只提示「未找到」。
说明文字 SHALL 与依赖清单中的同一信息保持一致。

#### Scenario: 缺 MAA 时启动方舟

- GIVEN 用户未安装 MAA
- WHEN 用户在明日方舟页点击「开始」
- THEN 提示明确写出「未找到 MAA」
- AND 同时给出 MAA 的官网地址与「在电脑端依赖清单里查看」

#### Scenario: 缺游戏本体

- GIVEN 用户装了 BetterGI 但没装《原神》
- WHEN 用户在原神页点击开始
- THEN 提示缺失项是《原神》而不是 BetterGI
- AND 只报告真正缺失的那一项

### Requirement: 公网地址的来源说明

文档 SHALL 解释清楚公网固定地址是怎么构成的、每一段的含义，
并明确告知用户**不能照抄文档中的示例地址**——它是每个人各不相同的。

#### Scenario: 用户看到 https://主机名.tailxxxxxx.ts.net

- GIVEN 用户第一次拿到 Funnel 域名
- WHEN 他阅读文档
- THEN 文档说明主机名来自自己电脑的名称
- AND 说明 `tailxxxxxx` 这一段是 Tailscale 注册时随机分配的十六进制串
- AND 说明 `ts.net` 是固定后缀
- AND 明确写出「这段随机串每个人都不一样，不能照抄本文档的示例」

#### Scenario: 用户想知道去哪看自己那一串

- GIVEN 用户已经配好了 Funnel
- WHEN 用户需要知道自己的域名
- THEN 文档给出三个途径：本程序「连接」页自动显示、
      管理员 PowerShell 执行 `tailscale funnel status`、
      Tailscale 网页控制台的 Tailnet DNS name 一栏

#### Scenario: 用户嫌这串不好记

- GIVEN 用户觉得十六进制串难记
- WHEN 用户阅读文档
- THEN 文档说明可以在控制台点 Rename tailnet 换成单词组合
- AND 说明这样做之后旧链接可能失效

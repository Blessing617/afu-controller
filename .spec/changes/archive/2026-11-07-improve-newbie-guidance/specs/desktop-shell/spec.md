# Delta：desktop-shell

## MODIFIED Requirements

### Requirement: 状态与配对展示

系统 SHALL 在桌面应用中显示服务状态、配对码、以及三个游戏/工具的可用性。

连接信息 SHALL 以**可以照着操作**的形式呈现，SHALL NOT 只罗列一串裸地址：
界面 SHALL 说明这些信息分别填到手机上哪里，并分步骤指引。

界面 SHALL 明确指出**推荐填哪一个地址**，并从多个候选地址中按优先级自动选取：
优先公网固定域名（手机端不需要装任何软件），其次局域网地址。

推荐地址 SHALL 提供一键复制，避免用户手抄长字符串出错。

#### Scenario: 新用户第一次看到总览页

- GIVEN 服务已运行且用户从未连过手机
- WHEN 用户打开桌面应用
- THEN 看到「手机怎么连上这台电脑」卡片
- AND 卡片分「① 填地址」「② 填配对码」两步
- AND 地址以醒目大字号显示，旁边有「复制地址」

#### Scenario: 推荐地址的选取

- GIVEN 电脑已开启 Tailscale Funnel
- WHEN 总览页展示推荐地址
- THEN 显示的是 Funnel 的固定域名（`https://xxx.ts.net`）
- AND 说明写明「出门在外也能用，手机不用装任何软件」

#### Scenario: 没有 Funnel 时

- GIVEN 电脑没有配置 Funnel
- WHEN 总览页展示推荐地址
- THEN 显示局域网地址
- AND 说明写明「只有手机和电脑连同一个 WiFi 时能用」

#### Scenario: 复制地址

- GIVEN 推荐地址已显示
- WHEN 用户点击「复制地址」
- THEN 地址进入剪贴板
- AND 按钮短暂显示「已复制 ✓」作为反馈

#### Scenario: 展示配对码

- GIVEN 尚无手机配对
- WHEN 用户查看桌面应用
- THEN 显示 6 位配对码
- AND 说明配对码只能使用一次、有效期 5 分钟

#### Scenario: 展示引擎状态

- GIVEN 服务已运行
- WHEN 用户查看桌面应用
- THEN 显示三个游戏各自是否可用（依赖的游戏与工具是否都已探测到）

## ADDED Requirements

### Requirement: 总览页的依赖提示

总览页 SHALL 直接显示「外部软件是否齐全」，SHALL NOT 要求用户先点进「依赖清单」才知道还要装东西。

#### Scenario: 缺软件

- GIVEN 某个必需外部软件未安装
- WHEN 用户打开总览页
- THEN 服务卡片内显示「还缺 N 个外部软件：XXX」
- AND 引导用户去「依赖清单」页看下载地址

#### Scenario: 都装好了

- GIVEN 全部必需软件都已就位
- WHEN 用户打开总览页
- THEN 显示「运行所需的软件都装好了，可以开始用」

### Requirement: 重复启动的可操作提示

当用户重复启动应用时，提示 SHALL 给出可以照着做的排查步骤，
SHALL NOT 只说「请查看任务栏」。

#### Scenario: 已有实例在运行

- GIVEN 应用已经有一个实例在运行
- WHEN 用户再次双击
- THEN 提示说明「它没有关掉，只是窗口被最小化或在别的窗口后面」
- AND 给出 Alt+Tab、托盘区（含 ^ 箭头）两种查找方式
- AND 说明实在找不到时可以在任务管理器里结束进程后重开

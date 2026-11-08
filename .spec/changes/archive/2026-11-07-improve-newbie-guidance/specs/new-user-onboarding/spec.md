# Delta：new-user-onboarding

## ADDED Requirements

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

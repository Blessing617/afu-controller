# Delta：connection

## MODIFIED Requirements

### Requirement: 固定地址连接

系统 SHALL 提供两种连接方式，**默认推荐「手机端不需要安装任何软件」的那种**：

1. **公网固定域名（推荐）**：电脑端用 Tailscale Funnel 暴露一个固定网址
   （形如 `https://<tailnet名>.ts.net`），手机 APP 直接填这个网址即可连接。
   手机端 SHALL NOT 需要安装 Tailscale 或任何其它 App。
   该域名在 Tailnet 不变的前提下 SHALL 保持固定，重启电脑与重启本程序都不改变。
2. **Tailscale 私有地址（进阶）**：手机也安装 Tailscale 并登录同一账号后，
   可填电脑的 `100.x` 地址。此方式不暴露公网，但手机需要额外安装 App。

电脑端 SHALL 在界面上直接展示 Funnel 的固定域名，用户 SHALL NOT 需要到命令行
自行查询才能知道手机该填什么。

#### Scenario: 出门在外连电脑（主路径）

- GIVEN 电脑端已配置好 Tailscale Funnel
- WHEN 用户打开手机 APP 的连接页
- THEN 电脑端界面上直接显示形如 `https://xxx.ts.net` 的固定网址
- AND 用户把这个网址填进 APP 即可连接成功
- AND 手机端不需要安装任何额外软件

#### Scenario: 地址固定不变

- GIVEN 用户已经用 Funnel 域名连过一次
- WHEN 电脑重启或本程序重启
- THEN 该域名保持不变
- AND 手机不需要重新填写地址

#### Scenario: Funnel 未配置

- GIVEN 电脑装了 Tailscale 但没开 Funnel
- WHEN 用户查看电脑端连接页
- THEN 界面提示「未开启」并给出开启命令
- AND 该命令里带上本程序当前的实际端口

#### Scenario: Funnel 端口与实际服务端口不一致

- GIVEN Funnel 转发到 8765 但本程序服务跑在 8766
- WHEN 用户查看电脑端连接页
- THEN 界面明确指出两者不一致
- AND 给出重新指向正确端口的命令

#### Scenario: 无管理员权限查看 Funnel 状态

- GIVEN 当前程序没有管理员权限
- WHEN 它尝试执行 `tailscale funnel status`
- THEN 界面显示「已安装（需管理员权限查看）」而不是「未开启」
- AND 给出用管理员 PowerShell 查看的命令

## ADDED Requirements

### Requirement: 连接引导按场景区分

连接页 SHALL 覆盖「在家（同一个 WiFi）」与「在外面」两种场景，
并在文案中明确「在外面」的主路径是电脑端的公网固定域名。

「搜索同一网络」的功能 SHALL 被明确标注为仅在同一个 WiFi 下有效。

#### Scenario: 出门在外打开连接页

- GIVEN 用户手机不在电脑所在局域网
- WHEN 用户打开连接页
- THEN 顶部说明提到「在外面填『公网地址』那个 https:// 开头的固定网址」
- AND 说明里写明「手机不用装任何软件」
- AND 底部的帮助卡片讲的是如何开启 Funnel，而不是如何安装 Tailscale

#### Scenario: 局域网搜索失败

- GIVEN 用户在连接页点了「搜索同一网络里的电脑」但没搜到
- WHEN 界面提示失败原因
- THEN 说明搜索只能在同一个 WiFi 下用
- AND 建议改用公网固定网址

### Requirement: Funnel 域名解析

系统 SHALL 能从 `tailscale funnel status` 的输出中正确解析出固定域名。
Tailscale 域名段数不固定（可能是 `xx.ts.net`，也可能是
`机器名.tailnet名.ts.net`），解析 SHALL 同时支持这两种形态。

#### Scenario: 四段域名

- GIVEN Funnel 输出 `https://host.tailxxxxxx.ts.net`
- WHEN 界面解析该输出
- THEN 得到完整域名 `https://host.tailxxxxxx.ts.net`

#### Scenario: 两段域名

- GIVEN Funnel 输出 `https://mybox.ts.net`
- WHEN 界面解析该输出
- THEN 得到 `https://mybox.ts.net`

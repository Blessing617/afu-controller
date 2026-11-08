# Delta：connection

## REMOVED Requirements

### Requirement: 临时隧道不作为用户主路径

（该要求本身已被更强的规则取代：cloudflared 不再存在于产品中，
不存在「放在哪」的问题。公网访问只保留 Tailscale Funnel。）

## MODIFIED Requirements

### Requirement: 固定地址连接

系统 SHALL 提供两种连接方式，**默认推荐「手机端不需要安装任何软件」的那种**：

1. **公网固定域名（推荐）**：电脑端用 Tailscale Funnel 暴露一个固定网址
   （形如 `https://<主机名>.<tailnet后缀>.ts.net`），手机 APP 直接填这个网址即可连接。
   手机端 SHALL NOT 需要安装 Tailscale 或任何其它 App。
   该域名在 Tailnet 不变的前提下 SHALL 保持固定，重启电脑与重启本程序都不改变。
2. **Tailscale 私有地址（进阶）**：手机也安装 Tailscale 并登录同一账号后，
   可填电脑的 `100.x` 地址。此方式不暴露公网，但手机需要额外安装 App。

系统 SHALL NOT 集成 cloudflared 或其它「地址会变」的临时隧道方案。
公网访问只保留 Tailscale Funnel 这一种形式。

电脑端 SHALL 在界面上直接展示 Funnel 的固定域名，并 SHALL 提供一键复制，
用户 SHALL NOT 需要到命令行自行查询才能知道手机该填什么。

**系统 SHALL 明确说明这个地址是怎么来的**：它是用户完成
「注册账号 → 安装 → 登录 → 开启 Funnel」四步之后才由 Tailscale 生成的，
SHALL NOT 表现为一个凭空存在、不需要任何前置条件的地址。

#### Scenario: 新用户第一次打开连接页（什么都还没做）

- GIVEN 用户刚下载本程序，电脑上什么都没配
- WHEN 用户打开「连接」页的「公网固定地址」卡片
- THEN 看到四步检查表：①注册账号 ②安装 ③登录 ④开启 Funnel
- AND 未完成的步骤明确标红，并写明该去哪里做
- AND 不会显示一个其实用不了的地址

#### Scenario: 做完四步后拿到地址

- GIVEN 用户已注册、安装、登录并开启 Funnel
- WHEN 用户查看「连接」页
- THEN 四步全部显示已完成
- AND 下方以醒目大字显示 `https://xxx.ts.net`
- AND 提供复制按钮

#### Scenario: 地址固定不变

- GIVEN 用户已经拿到并记录下该域名
- WHEN 电脑重启或本程序重启
- THEN 该域名保持不变
- AND 手机不需要重新填写地址

#### Scenario: 界面上没有会变的地址

- GIVEN 程序正常运行
- WHEN 用户浏览「总览」「连接」「设置」任一页面
- THEN 不会出现任何「每次重启都不同」的公网地址
- AND 不会出现 cloudflared 相关的字样或状态

#### Scenario: 端口不一致

- GIVEN Funnel 转发到 8765 但本程序服务跑在 8766
- WHEN 用户查看该卡片
- THEN 明确指出两者不一致
- AND 给出重新指向正确端口的命令

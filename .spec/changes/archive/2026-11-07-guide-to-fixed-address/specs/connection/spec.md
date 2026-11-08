# Delta：connection

## MODIFIED Requirements

### Requirement: 固定地址连接

系统 SHALL 提供两种连接方式，**默认推荐「手机端不需要安装任何软件」的那种**：

1. **公网固定域名（推荐）**：电脑端用 Tailscale Funnel 暴露一个固定网址
   （形如 `https://<主机名>.<tailnet后缀>.ts.net`），手机 APP 直接填这个网址即可连接。
   手机端 SHALL NOT 需要安装 Tailscale 或任何其它 App。
   该域名在 Tailnet 不变的前提下 SHALL 保持固定，重启电脑与重启本程序都不改变。
2. **Tailscale 私有地址（进阶）**：手机也安装 Tailscale 并登录同一账号后，
   可填电脑的 `100.x` 地址。此方式不暴露公网，但手机需要额外安装 App。

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

#### Scenario: 中途卡在登录

- GIVEN 已安装 Tailscale 但没登录
- WHEN 用户查看四步检查表
- THEN ②安装显示已完成
- AND ③登录标红并提示「点托盘图标 → Log in → 浏览器授权」

#### Scenario: 中途卡在开启 Funnel

- GIVEN 已登录但没开启 Funnel
- WHEN 用户查看四步检查表
- THEN ④标红并给出开启命令
- AND 命令里带上本程序当前的实际端口

#### Scenario: 地址固定不变

- GIVEN 用户已经拿到并记录下该域名
- WHEN 电脑重启或本程序重启
- THEN 该域名保持不变
- AND 手机不需要重新填写地址

#### Scenario: 无管理员权限

- GIVEN 程序以普通权限运行，读不到 Tailscale 状态
- WHEN 用户查看「公网固定地址」卡片
- THEN 已缓存的地址仍然显示
- AND 没缓存时明确提示「需要管理员权限」并说明怎么以管理员运行

#### Scenario: 端口不一致

- GIVEN Funnel 转发到 8765 但本程序服务跑在 8766
- WHEN 用户查看该卡片
- THEN 明确指出两者不一致
- AND 给出重新指向正确端口的命令

## ADDED Requirements

### Requirement: 临时隧道不作为用户主路径

cloudflared 提供的临时隧道地址 SHALL NOT 出现在「连接」页这类主路径上。
它 SHALL 放在「设置」页，并明确标注「地址每次重启都会变」。

系统 SHALL NOT 用「公网隧道」这类容易与固定地址混淆的名称来称呼它。

#### Scenario: 用户查看连接页

- GIVEN 程序已启动且 cloudflared 隧道也建立了
- WHEN 用户打开「连接」页
- THEN 页面里只有固定地址相关内容
- AND 不出现 `trycloudflare.com` 这类临时地址

#### Scenario: 用户查看设置页

- GIVEN 同上
- WHEN 用户打开「设置」页
- THEN 可以看到临时隧道的状态与当前地址
- AND 卡片标题与说明都写明「地址会变」

### Requirement: 固定域名的启动期缓存

系统 SHALL 在启动时读取一次 Tailscale 固定域名并持久化，
以便后续以普通权限运行时仍能展示正确地址。

#### Scenario: 启动时读取

- GIVEN 程序以管理员权限启动且 Tailscale 已登录
- WHEN 程序完成启动
- THEN 固定域名被写入配置的 `public_url`
- AND 之后即使降权运行，「连接」页仍显示该域名

#### Scenario: 读取失败

- GIVEN 读取 Tailscale 状态失败（未安装、未登录、无权限）
- WHEN 程序启动
- THEN 保留配置里已有的 `public_url`，不覆盖为空
- AND 界面按四步检查表显示卡在哪一步

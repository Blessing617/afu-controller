# connection

## Purpose

让手机在任何网络下都能连上家里的电脑：用 Tailscale 提供一个固定地址，用一次性配对码建立信任，并在网络波动后自动恢复。

## Requirements

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

### Requirement: 配对鉴权

系统 SHALL 要求首次连接时用一次性配对码换取长期 token，此后每次请求携带 token。

#### Scenario: 配对成功

- GIVEN 电脑端处于待配对状态并显示 6 位配对码
- WHEN 手机提交正确的配对码
- THEN 返回长期 token
- AND 该配对码立即失效

#### Scenario: 配对码错误或过期

- GIVEN 配对码错误或已超过有效期
- WHEN 手机提交该配对码
- THEN 返回失败且不发放 token
- AND APP 提示「配对码无效，请在电脑上重新生成」

#### Scenario: token 缺失或失效

- GIVEN 请求受保护接口但未携带 token 或 token 已失效
- WHEN 电脑端处理该请求
- THEN 返回 401
- AND APP 引导用户重新配对

### Requirement: 连接状态显示

系统 SHALL 在界面上持续显示当前连接状态（已连接 / 连接中 / 已断开），并展示电脑端自检结果。
当电脑端不可达时，APP SHALL 在 15 秒内把状态改为「已断开」，不依赖用户手动重连或重启 APP；空闲（没有任务在运行）时同样如此。

#### Scenario: 连接成功后展示自检

- GIVEN 手机已连接电脑
- WHEN 用户查看主界面
- THEN 显示服务版本、三个游戏是否可用（路径已探测）、电脑是否锁屏、服务是否具备管理员权限

#### Scenario: 连接断开

- GIVEN APP 处于已连接状态
- WHEN 与电脑端的连接中断
- THEN 界面状态变为「已断开」并停止刷新任务进度

#### Scenario: 空闲时电脑端停止服务（本次修复）

- GIVEN APP 已连接且没有任务在运行
- WHEN 电脑端服务被关闭或网络中断
- THEN APP 在 15 秒内显示「已断开」
- AND 不要求用户退出 APP 重进

#### Scenario: 电脑端恢复

- GIVEN APP 处于「已断开」状态
- WHEN 电脑端服务重新可用
- THEN APP 在数秒内自动连上，状态变回「已连接」
- AND 当前游戏页的画面刷新随之恢复

### Requirement: 断线自动重连

系统 SHALL 在网络恢复后自动重连，并从电脑端拉取全量状态，不依赖断线期间丢失的事件。
连接失败时系统 SHALL 每 5 秒自动重试，直到成功；并 SHALL 提供手动「重新连接」与「断开连接」入口。

#### Scenario: 网络切换

- GIVEN APP 处于已连接状态
- WHEN 手机从 WiFi 切到移动网络（或反向切换）
- THEN APP 在可接受时间内自动重连
- AND 重新拉取当前任务状态与最新日志尾部

#### Scenario: 重连期间任务仍在运行

- GIVEN 断线前有任务正在运行
- WHEN 重连成功
- THEN APP 正确显示该任务仍处于「运行中」，时长按服务端记录的开始时间计算

#### Scenario: 先开 APP 后开电脑（本次修复）

- GIVEN 手机 APP 已打开，但电脑上的服务尚未启动
- WHEN 用户随后启动电脑端服务
- THEN APP 在数秒内自动连上，无需重新打开 APP

#### Scenario: 手动断开

- GIVEN APP 处于已连接状态
- WHEN 用户点「断开连接」
- THEN APP 停止请求并显示已断开
- AND 保留已保存的地址与凭据，便于下次直接连接

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

# Delta：mobile-ux

## MODIFIED Requirements

### Requirement: 连接设置页的返回行为

连接设置页 SHALL 响应系统返回操作（返回键与左右边缘滑动手势），返回后回到主界面，SHALL NOT 因此退出 APP。

#### Scenario: 系统返回键

- GIVEN 用户从主界面进入了连接设置页
- WHEN 用户按系统返回键
- THEN 回到主界面
- AND APP 不退出
- AND 停留在进入前的那个游戏页

#### Scenario: 左右边缘滑动

- GIVEN 用户停留在连接设置页
- WHEN 用户从屏幕左右边缘向内滑动
- THEN 回到主界面
- AND APP 不退出

#### Scenario: 未配对时

- GIVEN 用户尚未成功配对任何电脑
- WHEN 用户在连接页按返回
- THEN 停留在连接页（因为还没有可回的主界面），不直接退出 APP
- AND 给出可继续操作的提示

## ADDED Requirements

### Requirement: 出门在外的连接引导

连接页 SHALL 同时涵盖「在家（同一个 WiFi）」与「在外面」两种场景，
SHALL NOT 默认假设用户和电脑在同一个网络。
页面 SHALL 明确告诉用户出门在外该填哪种地址。

#### Scenario: 出门在外的人打开连接页

- GIVEN 用户手机不在电脑所在的局域网内
- WHEN 用户打开连接页
- THEN 说明文字提到 Tailscale 的 `100.x` 地址
- AND 「搜索同一网络」被明确标注为仅在同一个 WiFi 下有效
- AND 页面提供「出门在外连不上」的排查提示

#### Scenario: 地址输入

- GIVEN 连接页展示地址输入框
- WHEN 用户还没输入
- THEN 占位提示同时给出 `100.x.x.x:8765` 与 `192.168.x.x:8765` 两种形态
- AND 说明这个地址在电脑端窗口的哪里能找到

### Requirement: 地址规范化

系统 SHALL 正确处理用户输入的地址：
裸 IP 与 http 地址 SHALL 补上默认端口；`https://` 开头的地址 SHALL NOT 补端口（它走 443）。
系统 SHALL NOT 在错误提示里把主机名截断（例如把 `https://host` 误显示为 `https`）。

#### Scenario: 公网 HTTPS 地址

- GIVEN 用户填入 `https://xxx.ts.net`
- WHEN 系统建立连接
- THEN 实际请求的是 443 端口
- AND 不出现 `https://xxx.ts.net:8765` 这种连不上的形式

#### Scenario: 裸 IP

- GIVEN 用户填入 `100.x.x.x`
- WHEN 系统建立连接
- THEN 实际请求 `100.x.x.x:8765`

#### Scenario: 错误提示不截断主机名

- GIVEN 连接 `https://xxx.ts.net` 失败
- WHEN 界面显示失败原因
- THEN 提示里出现完整的主机名 `xxx.ts.net`
- AND 不出现只有 `https` 或 `b` 这样的残缺字样

### Requirement: 连接与配对的反馈

连接与配对 SHALL 在执行期间显示进行中状态，SHALL NOT 让按钮点击后毫无反应。
失败原因 SHALL 常驻显示在页面内，SHALL NOT 只用一闪而过的提示。

失败提示 SHALL 按地址类型给出**可照着做的**排查步骤，而不是统一的「连接失败」。

#### Scenario: 连接进行中

- GIVEN 用户点击「连接」
- WHEN 请求尚未返回
- THEN 按钮显示「连接中…」并禁用，防止重复点击

#### Scenario: Tailscale 地址连不上

- GIVEN 用户填入 `100.x` 地址但连不上
- WHEN 失败
- THEN 提示引导用户检查手机 Tailscale 是否登录、电脑是否在线、电脑端程序是否运行

#### Scenario: 局域网地址连不上

- GIVEN 用户填入 `192.168.x` 地址但连不上
- WHEN 失败
- THEN 提示说明这需要同一 WiFi，并建议改用 Tailscale 地址

#### Scenario: 配对码无效

- GIVEN 用户提交了过期或错误的配对码
- WHEN 服务端返回 400
- THEN 页面常驻显示「配对码无效或已过期，请在电脑端重新生成」
- AND 不需要用户猜测为什么没反应

### Requirement: 本地配置损坏自愈

系统 SHALL 在本地配置（DataStore 文件）损坏时自动丢弃损坏数据并按空配置启动，
SHALL NOT 因此崩溃。

#### Scenario: 配置文件损坏

- GIVEN 应用的数据文件被外部因素写坏
- WHEN 用户启动 APP
- THEN APP 正常打开并回到连接页
- AND 不出现闪退
- AND 用户重新填写连接信息即可继续使用

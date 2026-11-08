# Delta：connection

## Purpose

让手机在任何网络下都能连上家里的电脑：用 Tailscale 提供一个固定地址，用一次性配对码建立信任，并在网络波动后自动恢复。

## ADDED Requirements

### Requirement: 固定地址连接

系统 SHALL 允许手机通过一个固定地址连接电脑端服务，地址在首次配置后持久化，后续打开 APP 自动复用。

#### Scenario: 首次配置

- GIVEN 手机尚未配置任何电脑
- WHEN 用户在连接页输入电脑的 Tailscale 地址并提交
- THEN 系统尝试连接该地址的健康检查接口
- AND 连接成功后保存地址与凭据
- AND 进入主界面

#### Scenario: 后续打开

- GIVEN 已保存地址与凭据且电脑在线
- WHEN 用户打开 APP
- THEN 直接使用已保存的地址建立连接，不再要求输入

#### Scenario: 地址不可达

- GIVEN 已保存地址
- WHEN 用户打开 APP 但电脑离线或 Tailscale 未连接
- THEN 显示「无法连接电脑」并提供重试与修改地址入口
- AND 不清空已保存的地址与凭据

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

#### Scenario: 连接成功后展示自检

- GIVEN 手机已连接电脑
- WHEN 用户查看主界面
- THEN 显示服务版本、三个游戏是否可用（路径已探测）、电脑是否锁屏、服务是否具备管理员权限

#### Scenario: 连接断开

- GIVEN APP 处于已连接状态
- WHEN 与电脑端的连接中断
- THEN 界面状态变为「已断开」并停止刷新任务进度

### Requirement: 断线自动重连

系统 SHALL 在网络恢复后自动重连，并从电脑端拉取全量状态，不依赖断线期间丢失的事件。

#### Scenario: 网络切换

- GIVEN APP 处于已连接状态
- WHEN 手机从 WiFi 切到移动网络（或反向切换）
- THEN APP 在可接受时间内自动重连
- AND 重新拉取当前任务状态与最新日志尾部

#### Scenario: 重连期间任务仍在运行

- GIVEN 断线前有任务正在运行
- WHEN 重连成功
- THEN APP 正确显示该任务仍处于「运行中」，时长按服务端记录的开始时间计算

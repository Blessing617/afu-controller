# Delta：connection

## MODIFIED Requirements

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

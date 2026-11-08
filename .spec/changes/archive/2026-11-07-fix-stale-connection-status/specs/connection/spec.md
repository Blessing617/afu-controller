# Delta：connection

## MODIFIED Requirements

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

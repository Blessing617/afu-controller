# Delta：resource-cleanup

## MODIFIED Requirements

### Requirement: 任务结束后自动清理

系统 SHALL 在任务正常结束或失败后，自动关闭该任务拉起的游戏与工具进程，释放内存。
方舟任务 SHALL 关闭 MuMu 的**主程序**（不只是虚拟机进程）——实测只关虚拟机会让 `MuMuNxMain` 常驻。

#### Scenario: 任务成功结束

- GIVEN 某个游戏任务成功完成
- WHEN 任务进入 `success` 状态
- THEN 关闭该游戏对应的游戏进程与自动化工具
- AND 方舟任务关闭 MuMu 主程序与虚拟机

#### Scenario: 任务失败或超时

- GIVEN 任务以 `failed` 或 `timeout` 结束
- WHEN 任务进入终态
- THEN 同样执行清理，避免残留进程继续占用内存

#### Scenario: 用户主动停止

- GIVEN 任务被用户停止（`stopped`）
- WHEN 任务进入终态
- THEN **不**自动清理（用户可能还要继续用电脑）

#### Scenario: 清理可以关闭

- GIVEN 用户希望任务结束后保留游戏
- WHEN 配置里把自动清理关掉
- THEN 任务结束不再动这些进程

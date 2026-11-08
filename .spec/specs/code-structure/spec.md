# code-structure

## Purpose

把「代码太乱」收敛成可检查的工程约束。参考阿福记账的分层约定：一个文件一个主要职责、
单文件不超过 300 行、界面不直接碰数据层。这里只写能被脚本验证的硬约束，
不描述具体实现细节（实现怎么拆由 design 决定）。

## Requirements

### Requirement: 单文件规模上限

服务端（Python）、桌面端（Python）与手机端（Kotlin）的每个源文件 MUST ≤ 300 行（不含空行与纯注释行）。
超过的文件 MUST 按职责拆分，MUST NOT 靠压缩排版规避。

#### Scenario: 规模检查可执行

- GIVEN 任意一次提交
- WHEN 运行规模检查脚本
- THEN 所有源文件的有效行数 ≤ 300
- AND 超限文件被列出并通过拆分消除

### Requirement: 分层依赖方向

服务端 SHALL 分为四层，依赖只能自上而下：

```
api/        HTTP 与 WebSocket 契约（只做参数校验与翻译）
core/       任务生命周期、编排、配置、状态（唯一的状态持有者）
engine/     三个引擎的适配器（只与引擎进程和引擎配置文件打交道）
platform/   Windows 系统调用（窗口、进程、截图、锁屏、唤醒）
```

约束：

- `api` MUST NOT 直接启动或结束引擎进程，只调用 `core`
- `engine` MUST NOT 导入 `api`，也不 MUST NOT 自行修改全局任务状态
- `platform` MUST NOT 依赖 `core` / `engine` / `api`
- 桌面端 MUST NOT 直接调用引擎脚本，只能通过服务端接口或 `core` 的能力
- 手机端 UI MUST NOT 直接拼装 HTTP 请求，只能经由数据层

#### Scenario: 依赖方向检查

- GIVEN 重构完成后的代码
- WHEN 运行依赖检查（导入关系扫描）
- THEN 不存在反向依赖（`engine` → `api`、`platform` → `core` 等）
- AND 违规处被列出

### Requirement: 任务状态单一来源

任务与任务链的运行状态 SHALL 只由 `core` 层的状态机维护。
引擎适配器 MUST NOT 直接写任务终态，只能上报事件（进度、日志、结果），
由状态机统一收敛并广播。

#### Scenario: 适配器不越权

- GIVEN 某个引擎适配器在运行中出错
- WHEN 它上报错误
- THEN 由状态机决定任务终态并广播一次
- AND 不存在「适配器与状态机各改一次」导致的状态抖动

# 任务

## 1. 数据模型与存储

- [x] 1.1 新增 `server/app/chain.py`：`ChainStep` / `Chain` 数据类，默认链（方舟→原神→星铁），读写 `data/chain.json` — 验证：import 后 `Chain.default()` 返回三步
- [x] 1.2 链配置校验：步骤数 ≤10、game 合法、同一 game 允许多次 — 验证：`pytest tests/test_chain.py -k validate`
- [x] 1.3 `PUT /api/chain` 整份替换 + 自动备份旧文件 — 验证：连续 PUT 两次，`chain.json` 是后一份，且生成 `.bak`

## 2. 引擎能力清单

- [x] 2.1 `EngineAdapter.list_tasks()` 抽象 + 三月七实现（`m7a --list --json`，5 秒超时）— 验证：实机调用返回 27 项且含中文名
- [x] 2.2 MAA 实现：读 `config/gui.new.json` 的 `TaskQueue`，`TaskType` 映射中文名 — 验证：返回基建/公招/商店等项及 IsEnable
- [x] 2.3 BetterGI 实现：读 `User/OneDragon/*.json` 的 `TaskDefinitions` + `TaskEnabledList` — 验证：返回「领取邮件/自动秘境」等项
- [x] 2.4 静态兜底清单 + `source` 字段标注（engine / fallback）— 验证：把引擎路径改成不存在的，仍返回清单且 source=fallback
- [x] 2.5 `GET /api/engines/{game}/tasks` 接口，单引擎失败不影响其他 — 验证：mock 一个引擎超时，另两个正常返回

## 3. 局部编排写回

- [x] 3.1 MAA 写回：只改 `TaskQueue[].IsEnable`，写前 `.bak-orch` 备份，解析失败报错且不动原文件 — 验证：改完后 diff 只有 IsEnable 变化
- [x] 3.2 MAA 写回前检测在线状态，在线先停 — 验证：`_ensure_maa_stopped()` 在写回前调用，`pytest tests/` 全绿
- [x] 3.3 BetterGI 写回：只改 `TaskEnabledList` 布尔值 — 验证：diff 只有该字段变化
- [x] 3.4 三月七不写配置，多选时拆成多次串行调用 — 验证：选 2 个 task，`m7a.exe` 被调用 2 次
- [x] 3.5 写回失败只让该步失败，不影响链上其他步骤 — 验证：损坏的 MAA 配置下链继续跑

## 4. 链调度器

- [x] 4.1 新增 `server/app/orchestrator.py`：按顺序检查 enabled → 执行 → 记录结果 — 验证：三步链按序跑完
- [x] 4.2 复用现有 `RUNNER`，`TaskRun` 加 `chain_id` 字段 — 验证：单步启动不受影响，链内 run 带 chain_id
- [x] 4.3 失败策略 skip / stop 两种 — 验证：skip 时后续继续；stop 时后续标 not_run
- [x] 4.4 用户中途停止：当前步 stopped、后续 not_run — 验证：`test_stop_mid_chain` 通过（确认调用了 stop_current）
- [x] 4.5 进度事件 `{"type":"chain"}` 广播（步骤开始 / 链结束）— 验证：WebSocket 能收到两类事件
- [x] 4.6 `POST /api/chain/run`、`/api/chain/stop`、`GET /api/chain/status` — 验证：接口可用，冲突时 409
- [x] 4.7 链运行时拒绝单步启动 — 验证：链运行中点单游戏「开始」返回 409 并说明原因

## 5. 手机端编排界面

- [x] 5.1 新增 `ChainScreen`：步骤列表（图标+名称+子任务摘要+启用开关）— 验证：默认链正确显示三步
- [x] 5.2 拖动排序 + 增删步骤 — 验证：拖第一项到最后，保存后顺序改变
- [x] 5.3 子任务勾选面板：按引擎清单渲染，标注 source — 验证：星铁显示 27 项；BGI 缺失时显示「默认清单」
- [x] 5.4 底部「一键跑完整条链」+ 运行中显示总进度与每步状态 — 验证：跑三步链，界面依次显示 1/3 2/3 3/3
- [x] 5.5 断网时本地暂存、恢复后同步 — 验证：DataStore 增 pending_chain 字段；保存遇网络/5xx 错误暂存，重连后 flushPendingChain 补发
- [x] 5.6 执行中禁用编辑 — 验证：运行中编辑入口灰掉并说明原因
- [x] 5.7 编排入口加在顶部或底栏，不与现有游戏页冲突 — 验证：能进出，返回不丢状态

## 6. 验证与收尾

- [x] 6.1 `server/tests/test_chain.py` + `test_apply.py` — 验证：pytest 全绿（65 passed）
- [x] 6.2 三步链顺序与进度 — 验证：假执行器实测 1/3→2/3→3/3，失败跳过继续（不拉起游戏）
- [x] 6.3 局部编排 — 验证：配置副本上验证只改 IsEnable、其余字段逐项一致；Fight#2 能单独控制
- [x] 6.4 打包 exe + APK，装机验证 — 验证：exe 以管理员权限启动正常；APK 装机后连接、编排、拖拽全部通过
- [x] 6.5 清理临时文件与测试配置备份 — 验证：`_tmp/` 下的截图与 dump 已删；两个引擎的 `.bak-orch` 已无残留（MAA 配置已复原）

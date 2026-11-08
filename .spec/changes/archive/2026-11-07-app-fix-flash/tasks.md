# 任务

- [x] 1.1 新增 `app/engine/proc.py`（`run` / `spawn`，内置 `CREATE_NO_WINDOW`）— 验证：模块可导入
- [x] 1.2 替换 bgi / m7a / window / cleanup / maa / tasks / winutil 的子进程调用 — 验证：24 个模块全部导入成功，5 个单测通过
- [x] 1.3 修正 `winutil.py` 的相对导入（在 app 顶层应为单点）— 验证：不再出现 `attempted relative import beyond top-level package`
- [x] 1.4 实机验证 — 验证：触发原神任务后 20 秒高频采样，捕获 tasklist/taskkill 闪窗 **0 次**（修复前每 5 秒 1 次）

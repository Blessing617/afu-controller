# 任务

## 1. 修复

- [x] 1.1 `AppViewModel.startPolling()` 增加空闲探活：有任务 3 秒、空闲 5 秒，空闲时请求 `/api/health` — 验证：服务停掉后 5 秒内 `connected` 变 false
- [x] 1.2 `refreshAll()` 的 `games` / `current` 网络失败（非 401）调用 `markDisconnected()` — 验证：断网时状态不再停留在「已连接」
- [x] 1.3 画面请求网络层失败（code=0）同样标记断开 — 验证：任务运行中拔网络，状态与画面提示同步变为断开
- [x] 1.4 重新编译：`gradle :app:assembleDebug` — 验证：BUILD SUCCESSFUL，新 apk 已生成

## 2. 验证

- [x] 2.1 真机：多次重启电脑端服务验证——APP 在 5 秒探活周期内变为「已断开」，服务恢复后自动重连（本次收口过程中反复触发）

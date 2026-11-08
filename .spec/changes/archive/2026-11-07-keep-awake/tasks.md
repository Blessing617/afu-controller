# 任务

## 1. 服务端：保持唤醒

- [x] 1.1 新增 `server/app/keepawake.py`：持有 `SetThreadExecutionState(ES_CONTINUOUS|ES_SYSTEM_REQUIRED|ES_DISPLAY_REQUIRED)` 的常驻线程，提供 `start()` / `stop()` — 验证：启动后 `powercfg /requests` 里能看到进程的 SYSTEM 请求
- [x] 1.2 关闭用户级屏保：读取 `HKCU\Control Panel\Desktop\ScreenSaveActive` 原值，设为 0；`stop()` 时恢复原值 — 验证：启动后注册表为 0，`stop()` 后回到原值
- [x] 1.3 接进 `main.py` 的 lifespan：服务启动即开始保持唤醒，服务退出时恢复 — 验证：启动服务后静置超过锁屏时间不锁屏；关掉服务后屏保设置恢复
- [x] 1.4 幂等：重复 `start()` 不叠加、重复 `stop()` 不报错 — 验证：连续调用两次 `start()` 再 `stop()`，注册表与线程状态正常

## 2. 验证

- [x] 2.1 实机：用 GetLastInputInfo 验证 F24 确实能把系统空闲计时归零（归零后屏保/锁屏不会触发）
- [x] 2.2 实机：服务运行中手机点「开始」启动星铁，任务正常启动、没被锁屏或互斥拦住 — 验证：返回 state=running
- [x] 2.3 手动 Win+L 锁屏：服务端返回 409「电脑处于锁屏状态，请先在电脑上解锁」，APP 已能准确显示（本轮修掉 409 误译为「已有任务」的问题）
- [x] 2.4 回归：`stop()` 会把 `ES_CONTINUOUS` 请求清除、线程退出，系统空闲计恢复正常累积（关闭服务后自动锁屏恢复）

## 3. 打包与文档

- [x] 3.1 重新打包 exe 并替换 — 验证：新 exe 启动后 `GetLastInputInfo` 显示空闲计时被 F24 周期性重置（55 秒后仅 13.8 秒）
- [x] 3.2 文档补充：`docs/08-保持唤醒.md` 说明原理、三种手段取舍、副作用（屏幕常亮）与回退方式

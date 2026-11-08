# 任务

## 1. 服务端截图内核

- [x] 1.1 `engine/window.py` 增加 `find_game_window(game)`：按游戏进程名候选找可见顶层窗口，取面积最大者，返回句柄、矩形、是否最小化 — 验证：星铁真实窗口定位到「崩坏：星穹铁道」1295×757；未启动时三个游戏各 1.6ms 返回 None
- [x] 1.2 新增 `engine/capture.py`：BitBlt → PIL → 宽 1280 上限 → JPEG；全黑检测；模块级锁串行 — 验证：本机脚本连截 20 张，打印每张耗时与体积
- [x] 1.3 `engine/capture.py` 的耗时与体积达标：单张 < 100ms、1080p 体积 ≤ 300KB — 验证：真实窗口实测 1294×829 均值 29.1ms / 256KB（噪点最坏情况），1080p 类 33.7ms / 200KB
- [x] 1.3b 连续 300 次截图后 GDI 句柄与内存无持续增长，且磁盘无截图文件 — 验证：GDI +0、USER +0、RSS +0.2MB，`server/data` 无新增文件
- [x] 1.4 新增 `api/screen.py`：`GET /api/screen/{game}`、quality 夹紧 30–90、错误码映射、四个元信息头 — 验证：真实服务 curl 四种失败路径，状态码与 `error` 字段正确
- [x] 1.5 注册路由到 `main.py`，确认鉴权生效 — 验证：无 token 请求返回 401 且无图像字节
- [x] 1.6 `tests/test_screen.py`：未知游戏、窗口不存在、最小化、全黑、quality 越界夹紧、响应头存在、未配对 401（窗口用 monkeypatch 假造）— 验证：`pytest server/tests -q` 15 passed

## 2. APP 端画面区域

- [x] 2.1 `ApiClient` 新增 `fetchScreen(game, quality)`：二进制下载、短超时 client、解析 `X-Captured-At` / `X-Image-Width`、错误走 `ErrorDetail` — 验证：编译通过；真机取图待端到端
- [x] 2.2 `UiState` 增加 `screens: Map<String, GameScreen>`（image / capturedAt / error / loading / stale），每个游戏只保留最新一帧 — 验证：真机连续运行三轮任务刷新正常、无卡顿；内存曲线尚未用 Profiler 量化
- [x] 2.3 `Screens.kt` 增加 `ScreenCard`（标题下方）：画面、截图时间、「旧快照」标记、「刷新一张」按钮、失败原因文案 — 验证：`assembleDebug` BUILD SUCCESSFUL
- [x] 2.4 `MainActivity` 接入前后台生命周期：`onStop` 停刷新，`onStart` 恢复 — 验证：编译通过
- [x] 2.5 页面接入 `LaunchedEffect` + `DisposableEffect(game)`，切页自动收尾 — 验证：代码完成，真机观察待 3.2

## 3. 构建与端到端验证

- [x] 3.1 构建 APP：`GRADLE_USER_HOME=D:\Android\gradle-home` 下 `gradle :app:assembleDebug` — 验证：BUILD SUCCESSFUL，apk 生成
- [x] 3.2 端到端（星铁实机）：任务运行中手机看到 1280×720 画面每 1.5 秒更新；停止后自动刷新停止并标记「旧快照」；窗口不存在时显示明确中文文案；游戏在后台时不再返回别的窗口画面 — 验证：记录在 `docs/07-实时画面验证.md` 第六节
- [x] 3.3 耗时与体积实测：星铁 71~87ms、原神 310ms → 改用 GDI 截屏后 24ms，均 1280×720 / ≤ 80KB — 验证：数据在 `docs/07` 第二节
- [x] 3.5 方舟画面：改为通过模拟器 ADB 截屏（`emulator-5554 screencap`），拿到模拟器内部纯净画面，不需要窗口在前台；实测 1280×720、~700ms（该值在改成全屏方案后为 164ms）
- [x] 3.4 打包复验（已替换部署）：PyInstaller onedir 重新打包 `游戏编排器.exe`，确认 `_internal` 内含 `PIL` — 验证：`_internal/PIL` + `_imaging.cp313-win_amd64.pyd` 存在，`app.main`/`app.api.screen`/`PIL.Image` 均在 PYZ；旧版备份在 `D:\DSHData\backups\游戏编排器-2026-11-07-before-screen`，data 已迁移（exe 环境取图待 3.2 启动验证）

## 4. 方案收口（实机反馈后）

- [x] 4.1 放弃「按游戏窗口截图 + 客户区裁剪」，改为**全屏截图**：不算坐标、不猜 DPI、不裁标题栏，屏幕上显示什么就截什么

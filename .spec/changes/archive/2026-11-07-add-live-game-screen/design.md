# 设计：游戏画面实时查看

## 1. 服务端截图管线

### 窗口定位

现有 `server/app/engine/window.py` 已经能按进程名枚举可见顶层窗口（`_pids_of` + `_windows_of`），但只暴露了 `activate` / `minimize`，没有「拿到句柄」。新增：

```python
GAME_PROCESSES = {
    "genshin":   ["YuanShen.exe", "GenshinImpact.exe"],
    "starrail":  ["StarRail.exe"],
    "arknights": ["MuMuNxMain.exe", "MuMuPlayer.exe", "MuMuVMMHeadless.exe", "NemuPlayer.exe"],
}

def find_game_window(game) -> (hwnd, left, top, width, height, minimized) | None
```

要点：

- 一个进程可能有多个窗口（启动器、报错框、遮罩层），取**面积最大的可见顶层窗口**，比取第一个稳。
- 方舟的画面在 MuMu 模拟器里，所以按模拟器窗口（含标题栏与侧栏）截取——这是用户确认过的口径，实现成本最低，也不依赖模拟器渲染细节。
- `IsIconic(hwnd)` 判定最小化，最小化时直接返回 `window_minimized`，不做无意义的 BitBlt。
- 定位失败不抛异常，返回 `None`，由接口层转成 `window_not_found`。

### 截图与编码

新增 `server/app/engine/capture.py`，抓图分两步（实机踩坑后的结论见下）：

1. `GetWindowDC(hwnd)` → `CreateCompatibleDC` + `CreateCompatibleBitmap`
2. **先 `PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)`**：能取到窗口自己在 DWM 合成层里的内容，窗口被遮挡时也不会拿到遮挡物
3. 若 PrintWindow 失败或整张全黑，回退 **`BitBlt`**：窗口在前台时最快最可靠
4. `GetDIBits` 拿到 BGRA 缓冲 → `PIL.Image.frombytes` 转 RGB
5. 缩放：宽度上限 1280，等比缩放到宽度 1280（更窄的窗口保持原宽）；`Image.Resampling.BILINEAR`
6. 编码：`crop.save(BytesIO(), "JPEG", quality=q, optimize=True)`（实测约 20ms）

**实机踩坑记录**：第一版只用了 BitBlt（依据是「1294×829 只要 3.9ms」这条实测线索）。真机上发现：星铁窗口在后台、被 DSH 窗口盖住时，BitBlt 截出来的是 **DSH 的界面**，不是游戏画面——D3D 渲染的窗口在后台时窗口 DC 拿到的是屏幕合成结果。改用 PrintWindow + `PW_RENDERFULLCONTENT` 后，窗口被遮挡也能拿到它自己的内容（tkinter 窗口实测：遮挡状态下 PrintWindow 9.9ms、内容正确）。两步策略保证「被遮挡时正确、前台时最快」。

全黑检测放在缩放之后、编码之前：把图缩到 32×32 后统计亮度最大值，`max < 8` 视为全黑。两种抓法都全黑才返回 `capture_black`。

### 并发与任务隔离

- 模块级 `threading.Lock`，整个「定位 → 截图 → 编码」串行执行。三张请求一起到时排队等待（不返回 busy），因为 APP 侧只有一个页面在刷新。
- 截图只调 `GetWindowDC` / `BitBlt`，**不调** `ShowWindow` / `SetForegroundWindow` / `SetFocus`，所以不会和引擎的点击抢焦点。
- 路由用同步 `def`（FastAPI 自动放进线程池），不阻塞 asyncio 事件循环——这一点很关键：否则 20ms 的编码会卡住 WebSocket 日志推送。
- 截图异常只在响应里表达，不调 `RUNNER.append_log`，也不触碰 `STATE`。

### 接口

`server/app/api/screen.py`，注册进 `main.py`：

| 情况 | 状态码 | error |
|---|---|---|
| 成功 | 200 | — |
| 未知 game | 404 | `unknown_game` |
| 未配对 | 401 | `unauthorized`（中间件统一返回） |
| 窗口不存在 | 404 | `window_not_found` |
| 窗口最小化 | 409 | `window_minimized` |
| 全黑 | 409 | `capture_black` |
| 其它截图失败 | 500 | `capture_failed` |

错误体用 `JSONResponse` 直接返回顶层 `{"error","message"}`（与 `auth_middleware` 一致），因为 APP 的 `ErrorDetail` 就是按顶层解析的——`HTTPException(detail=...)` 会包一层 `detail`，客户端拿不到 message。

`quality` 用 `Query(default=70)` 声明为 int，范围手写夹紧 `max(30, min(90, q))`；非整数由 FastAPI 自身返回 422。

`X-Captured-At` 用 `datetime.now().astimezone().isoformat(timespec="seconds")`，`X-Capture-Ms` 用 `round(耗时)`。

### 为什么不用别的方案

- **PrintWindow**：这是现在的首选方案。`PW_RENDERFULLCONTENT` 对 DWM/D3D 窗口有效，被遮挡时也能拿到自身内容。代价是比 BitBlt 慢一点（实测 9.9ms），且少数老游戏仍可能返回黑图——所以保留 BitBlt 兜底。
- **只靠 BitBlt**：最快的方案，但窗口在后台时对 D3D 窗口不可靠（实测截到了盖在上面的别的窗口），这正是实机发现的问题。
- **各引擎私有截图（MAA `CaptureImage`）**：MAA 单张返回几十 MB 的 base64，其它两个引擎也没有稳定接口，而且方舟之外的场景用不上。统一 BitBlt 才有「三种游戏一套代码」。
- **ffmpeg / 视频流**：需求明确排除录制与推流，引入 ffmpeg 会让打包体积和部署复杂度上一个台阶。

## 2. APP 端

### 网络层

`ApiClient` 新增：

```kotlin
data class ScreenFrame(val bytes: ByteArray, val capturedAt: String, val width: Int, val height: Int)
suspend fun fetchScreen(game: String, quality: Int = 70): ApiResult<ScreenFrame>
```

- 复用现有 token header，`Accept: image/jpeg`。
- 单独建一个短超时的 client（`readTimeout 12s`），不要用主 client 的 210 秒——画面请求卡住不能拖住界面。
- 非 2xx 时按 `ErrorDetail` 解析 JSON 拿 `message`（顶层结构），解析失败再退回 `friendlyHttp`。
- 元信息头缺省时用当前时间兜底，不因为少一个头就失败。

### 状态与刷新策略

`UiState` 增加：

```kotlin
data class GameScreen(
    val image: ImageBitmap? = null,
    val capturedAt: String = "",
    val error: String = "",
    val loading: Boolean = false,
    val stale: Boolean = false,   // 任务结束后保留的旧快照
)
val screens: Map<String, GameScreen>
```

刷新任务放在 ViewModel 里，一个 `screenJob`（对应当前游戏页）：

- 进入某个游戏页 → `startScreenLoop(game)`：先立即取一张，然后 `while` 每 1500ms 取一张。
- 该游戏任务结束（`current == null` 或 `current.game != game`）→ 取消 job，把已有图标记 `stale = true`。
- 切页 / 断开连接 / `ON_STOP` → 取消 job。
- 手动「刷新一张」→ 单独一次请求，不影响循环；失败只写 `error`。

页面通过 `DisposableEffect(game)` 调用相应方法，切页时自动收尾，不用在 Composable 里手写定时器。

### 界面

`Screens.kt` 新增 `ScreenCard`，放在游戏名标题与可用性状态之间（用户最先看到画面）：

- 16:10 左右的圆角容器，`Image(bitmap, contentScale = ContentScale.Fit)`，无图时显示占位文案。
- 底部一行：`截图时间` + `X-Capture-Ms` 可选显示；失败时红色文案替换时间。
- 「刷新一张」按钮始终可用（未运行时也能手动看一眼）。
- `stale` 时在时间旁加「旧快照」小标签。

图片不落盘、不做磁盘缓存；`ImageBitmap` 由 Compose 直接解码字节数组，1.5 秒一张的频率不需要额外优化。

## 3. 风险与已知限制

- **独占全屏**：原神/星铁切到独占全屏时 BitBlt 会黑屏，返回 `capture_black`。这是设计内的降级，不是 bug。
- **模拟器窗口被最小化**：MuMu 最小化后画面不渲染，返回 `window_minimized`。
- **多窗口抢焦点**：截图不激活窗口，所以「截到的画面」可能被别的窗口遮住（BitBlt 截的是窗口 DC，被遮挡区域可能拿到的是别的窗口内容）。当前不做置顶处理，因为那会与任务抢焦点。
- **打包**：exe 环境需要 `PIL` 被 PyInstaller 收录（`--collect-all PIL` 或 hooks 已覆盖）；打包后必须复验一次。

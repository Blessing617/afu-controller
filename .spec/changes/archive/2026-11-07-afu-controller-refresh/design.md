# 设计：阿福代肝控制器（品牌 / 性能 / 编排）

## 1. 图标：为什么手绘成 SVG 而不是用网图

- **一份源文件，四处派生**：`assets/icons/app-icon.svg` 是唯一源。`assets/make_icon.py` 用
  PySide6 的 `QSvgRenderer` 渲染出 `icon.ico`（六个尺寸）与 256px PNG；安卓的三层
  vector drawable 由同一份几何路径改写而来（`viewportWidth=108`）。
  改图标只改 SVG 再跑脚本，不会出现「exe 换了、手机没换」。
- **小尺寸可辨认**：16/32px 下只保留「鲸鱼身体轮廓 + 手柄的亮色轮廓」两个层次，
  不给眼睛/腮红留细节——那些在 32px 只会糊成一团。
- **参考图只作构图参考**：找「蓝发鲸鱼娘 / 大肥鱼 + 手柄」的网图仅用于确定构图与配色倾向，
  不复制像素、不打包进仓库。原因有两条：项目 spec 明确要求原创矢量；网图素材的授权
  往往无法确认。参考来源记在 `assets/icons/README.md`。
- **自适应图标安全区**：安卓 108dp 画布只显示中央 66dp（内切圆约 66dp 直径安全区），
  所以主体缩到中央 60dp 以内，尾巴和水花作为可裁切的装饰放在边缘。

## 2. 电脑端卡顿：根因与改法

根因（读代码确认）：`qt_ui.py` 的 `_poll_status()` 每 2 秒在**界面线程**同步执行
`_tailscale_setup_state()`，它内部 `subprocess.run(tailscale status --json)` 和
`tailscale funnel status` 各一次，每次超时上限 10 秒；同时 `_update_addresses()`
同步做一次 `socket.getaddrinfo` + `gethostbyname_ex`。Tailscale 未安装/未响应时，
这两次调用会把界面线程卡住数秒——这就是「很卡」的主要来源。

改法：

- 新增 `desktop/backend.py`：一个后台线程 + 一个 2 秒定时器，负责
  ① 查询 Tailscale 四步状态 ② 枚举本机地址 ③ 读配对码，产出一个
  `ConnectionSnapshot` 数据类，通过 `QtCore.Signal(object)` 推给主窗口。
  主窗口的槽只做 `setText` / 重建几行 QLabel，不再调用任何外部进程。
- 地址列表变化时才重建控件（比较快照是否相等），否则一个 QLabel 都不动。
- `_on_refresh_code` 当前起两次线程，是明显的复制粘贴 bug，一并修掉。

### 为什么不干脆上 QThread worker 池

截图、探测、依赖检查都已经在独立线程里跑。这里只有一个周期任务，
一个常驻 daemon 线程 + `threading.Event.wait(2.0)` 做节拍就够，
不需要引入线程池或 asyncio，改动面小、也更好排查。

## 3. 电脑端切页动效：为什么不用 QStackedWidget 自带动画

`QStackedWidget` 没有内置转场。可选方案：

| 方案 | 结论 |
|---|---|
| 换成 `QStackedLayout` + 自己接管 `currentIndex`，给离场/入场页各挂一个 `QGraphicsOpacityEffect` 和 `QPropertyAnimation` | **采用**。改动局限在 `show_page()` 一处，两个 `QPropertyAnimation`（opacity + pos）并行跑 200ms `OutCubic`，结束后复位 pos、清掉 effect |
| QML / QtQuick 重写 | 收益不足以抵消整个界面重写 |
| 第三方库（如 `qtmaterials`） | 引入依赖、打包体积变大，且本项目刻意精简 Qt 模块 |

注意两点（都是踩过的坑）：

- `QGraphicsOpacityEffect` 加在**页面根 Widget** 上会让整个页面走一遍离屏合成，
  页面卡片多时容易掉帧。所以只在切页期间挂、动画结束立刻 `setGraphicsEffect(None)`，
  静止时零成本。
- 位移用 `QPropertyAnimation(target, b"pos")` 时必须记录初始 `pos` 并在结束时还原，
  否则多次切页后内容会越飘越远。

减少动画：`QApplication` 里读 `QStyleHints` 拿不到 Windows 的「显示动画」开关，
改为读注册表 `HKCU\Control Panel\Desktop\WindowMetrics\MinAnimate`（"0" 表示关闭）。

## 4. 手机端卡顿：根因与改法

根因（读代码确认）：

1. `UiState` 是一个大的 `data class`，`refreshAll()` 每 3~5 秒无条件
   `copy(current=..., history=...)` —— 即使数据完全没变，`StateFlow` 也会发射新值，
   `collectAsStateWithLifecycle` 于是让 `MainScreen` 整体重组一次。列表 `history` 每次
   都是新 `ArrayList`，`equals` 必然为 false，等于每轮必重组。
2. 画面帧（`ImageBitmap`，宽 960 的位图）塞在同一个 `UiState` 里，来一张新图就让
   `GamePage`、`TaskCard`、`PrimaryActionBar` 全部重组。
3. 解码用 `Dispatchers.Default`（小对象池），与 CPU 密集任务混在一起；且只丢掉
   `ImageBitmap` 引用，原生 `Bitmap` 要等 GC。

改法：

1. `UiState.copy` 之前先做 `if (next == current) return`——`data class` 的 `equals`
   对 `List<TaskRun>` 是逐元素比较，`TaskRun` 也是 `data class`，所以这条判断有效。
   `history` 每次都是新实例但内容相同时 `equals` 为 true，不会误判。
2. 把 `screen: GameScreen` 从 `UiState` 移到独立的 `MutableStateFlow<GameScreen>`，
   并在 UI 层单独 `collect`。只有读它的 composable 会重组。
3. 解码切到 `Dispatchers.IO`，解码成功后 `bitmap.recycle()` 掉 `BitmapFactory` 产出的
   原生 `Bitmap`（`asImageBitmap()` 会共享像素，先 `copy` 再回收，或直接保留引用让
   `ImageBitmap` 持有——实测后者更省，采用「保留引用、不额外拷贝」）。
4. 轮询间隔：有任务 3 秒、空闲 5 秒保持不变；只在 `current` 变化时才触发画面循环启停。

## 5. 手机端编排：固定层 + 内容层

现状：`GamePage(vm, game)` 整体跟着 `games[tab]` 变化 —— 切 tab 时 Compose 认为是
新参数，`LaunchedEffect(game)` / `DisposableEffect` 全部重跑，画面卡、任务卡、
按钮一起重建。用户感知就是「切过去先空白一下再刷新」。

改成：

```
Scaffold(bottomBar = GameBottomBar, topBar = TopBar)
 └ Box
    ├ GameContent(tab)      ← 只有它随 tab 变（状态行、说明、次要按钮）
    └ ScreenCard + PrimaryActionBar  ← 固定层，不随 tab 重建
```

`ScreenCard` 读独立的 screen flow；`PrimaryActionBar` 只读 `current`/`games`/`connected`。
切 tab 时这一层一帧都不动，符合「三个游戏共用同一张全屏截图」的事实。

设置入口：顶部条的图标 → `showSettings` → 设置页列表 →
「连接设置」二级页（复用现有 `ConnectScreen`，去掉它的 `canGoBack` 兜底按钮，
统一由顶部返回箭头负责）。

## 6. 截图路径统一

`capture()` 现在对 `arknights` 先试 `_grab_via_adb()`，失败退回全屏。ADB 分支的问题：

- 需要 `adb.exe` 与模拟器在线，任一步失败都要多等一轮超时（adb devices 6 秒 + 
  screencap 15 秒），期间 `_LOCK` 一直被持有，另一个请求在排队。
- 三个游戏本来共用一张全屏截图，方舟却给出另一种画面比例，切页时观感不一致。

删掉 ADB 分支后 `capture()` 变成单一分支：`_grab_fullscreen()` → 缩放 → 编码。
`_find_adb` / `_adb_serial` / `_grab_via_adb` / `_ADB_SERIAL_CACHE` / `_NO_WINDOW` 一并删除，
模块里不再 import `subprocess`。

## 7. 兼容性：只有部分游戏可用

现在 `games.py` 的 `_game_snapshot()` 已经对每个游戏独立算 `ready`，缺的不会整块消失；
真正会出问题的是 UI 侧：`GAME_ICONS[key]!!` 的强制解包、以及「三款都齐才显示」的隐式假设。
改法：底栏固定渲染三个按键，图标用 `GAME_ICONS.getValue(key)` 加兜底；不可用时按键
仍然可点（能进去看缺什么），只是加一个角标；`PrimaryActionBar` 的 `enabled` 已由
`ready` 控制，保持不变。

## 8. 不做的事及理由

- **不换技术栈**：Electron/Tauri 重写收益不匹配成本，Qt 侧的问题已经定位到具体调用。
- **不动服务端接口结构**：手机端与网页控制台都在用，改结构要两边同时升，风险大于收益。
- **不做主题换肤 / 背景图**：用户这次没要求，属于范围蔓延。

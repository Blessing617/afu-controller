# 任务

## 1. 品牌与图标

- [x] 1.1 写 `assets/make_icon.py` 的新源：重画 `assets/icons/app-icon.svg` 为「大肥鱼抱手柄」原创矢量（蓝白渐变底 + 圆滚滚鲸鱼 + 手柄 + 水花），保留无文字、无厂商素材 — 验证：用 Qt 渲染 512px 预览图，肉眼确认鲸鱼与手柄清晰可辨
- [x] 1.2 用参考图核对方向：找 1~2 张「蓝发鲸鱼娘 / 大肥鱼 + 手柄」的网图作构图参考（不打包进仓库、不复制像素），把来源与「手绘」说明写进 `assets/icons/README.md` — 验证：README 里记录了参考链接与授权/参考性质说明
- [x] 1.3 生成多尺寸图标：`assets/icons/app-icon-256.png` + `desktop/icon.ico`（16/32/48/64/128/256）— 验证：`python assets/make_icon.py` 成功，`read_image` 查看 32px 版本仍能分辨鲸鱼
- [x] 1.4 安卓自适应图标三件套（`ic_launcher_background.xml` / `ic_launcher_foreground.xml` / `ic_launcher_monochrome.xml`）改成同一形象，前景主体位于中央 66dp 安全区内 — 验证：用 `mask-preview.html` 在圆形/圆角/方形三种遮罩下预览，主体不被裁切
- [x] 1.5 改名：`desktop/游戏编排器.spec` → `desktop/阿福代肝控制器.spec` 并改 `name=`；`desktop/main.py` 的 `APP_TITLE`、单实例提示、`APP.spec` 的 exe 名；`android` 的 `strings.xml` `app_name`；`server/app/static/*.html` 里的产品名 — 验证：`grep -rn "游戏编排器" desktop server/app/static android/app/src/main/res` 无用户可见残留
- [x] 1.6 安卓包名迁移：`namespace` / `applicationId` → `com.afu.controller`，Kotlin 包目录 `com/gameorch/app` → `com/afu/controller` 并改所有 `package` / `import` — 验证：`./gradlew :app:assembleDebug` 通过，`unzip -l` 查 APK 里 `com/afu/controller` 存在

## 2. 电脑端性能与编排

- [x] 2.1 新增 `desktop/backend.py`：把 `tailscale` 调用与地址枚举挪到后台线程，用单个 2 秒定时器统一产出「连接信息快照」，通过信号推给界面；界面线程只负责渲染 — 验证：连接页静置 60 秒，窗口可拖动、按钮有反馈（任务管理器里 UI 线程 CPU 不再周期性尖峰）
- [x] 2.2 修掉 `_on_refresh_code` 里重复起两个线程的问题，并把「换一个配对码」改成走公开接口的明确路径 — 验证：点一次只产生一次请求（`app.log` 一行）
- [x] 2.3 首屏先画出来：`start_bootstrap()` 之后立即 `show()`，探测与依赖检查全部后台化 — 验证：双击后窗口 1 秒内出现且可操作
- [x] 2.4 导航收敛为 总览 / 依赖清单 / 设置，连接信息并入总览页；侧边栏品牌改为图标 + 「阿福代肝控制器」 — 验证：截图确认四项变三项、总览页含地址与配对码
- [x] 2.5 页面切换过渡动画：新增 `desktop/motion.py` 统一动效 token（时长 200ms、`OutCubic` 缓出、位移 ≤ 内容宽 6%、淡入），`QStackedWidget` 切页时对目标页做 `QGraphicsOpacityEffect` + 位移 `QPropertyAnimation` — 验证：录屏/连续切换 20 次无白屏，减少动画开关下退化为直切
- [x] 2.6 侧边栏与图标路径同步到新图标文件 — 验证：侧边栏、窗口图标、任务栏图标都是新图标

## 3. 服务端截图统一

- [x] 3.1 `server/app/engine/capture.py` 删除 ADB 分支（`_find_adb` / `_adb_serial` / `_grab_via_adb`）与相关常量，`capture()` 三个游戏走同一 `_grab_fullscreen()` 路径 — 验证：`/api/screen/arknights` 与 `/api/screen/genshin` 的 `X-Capture-Ms` 同量级，且服务端不再 import `subprocess` 于该模块
- [x] 3.2 更新 `server/app/engine/capture.py` 与 `api/screen.py` 的模块注释，去掉「方舟走 ADB」的描述 — 验证：grep `adb` 在 server/app 下无残留
- [x] 3.3 在 `server/tests/test_screen.py` 补两条契约测试：方舟与原神走同一截图路径（产物逐字节一致）、capture 模块里不许残留 ADB 符号 — 验证：`pytest tests/ -q` 全绿（33 passed）

## 4. 手机端性能与编排

- [x] 4.1 `AppViewModel`：`UiState` 的轮询更新改为「内容相等就不发射」；`screen` 状态拆成独立的 `StateFlow`，画面帧变化只让画面区重组 — 验证：空闲静置 30 秒，Layout Inspector / 日志计数显示无周期性重组
- [x] 4.2 画面解码改到 `Dispatchers.IO`，并用 `BitmapFactory.Options.inSampleSize` + `RGB_565` 降采样（960 宽以内），只保留一张 `ImageBitmap` — 验证：`assembleDebug` 通过；解码不再发生在主线程
- [x] 4.3 界面重构为「固定层 + 内容层」：顶部状态条、画面卡、底部主操作栏在 `Scaffold` 里固定；只让中间的滚动内容跟随选中的游戏变化 — 验证：方舟 → 原神切换时画面不闪白、不出现加载圈（录屏帧比对）
- [x] 4.4 移除每个游戏页里的「连接设置」按钮；新增顶部设置图标 → 设置页 → 「连接设置」二级页（复用现有 ConnectScreen）— 验证：三个游戏页都只剩「重新探测 / 关闭并释放」，设置页能进连接页
- [x] 4.5 缺游戏时的表现：底栏三个按键始终存在，不可用的按键加标记；游戏页正文写明缺哪几项 — 验证：把模拟器里的探测结果造假的三种组合（1 款 / 2 款 / 0 款）各看一遍
- [x] 4.6 切页动画：底部标签之间用「方向位移 ≤ 屏宽 12% + 缩放纵深 + spring」的 `AnimatedContent`，设置等二级页从底部滑入并让底层缩小压暗，全部时长来自 `ui/Motion.kt` 的 token；系统关闭动画时退化为直切 — 验证：连续切换 40 次无掉帧可感，减少动画下直切
- [x] 4.7 更新 `Theme.kt` 注释与 token，保证与 `desktop/tokens.py`、新的 `desktop/motion.py` 三处数值一致 — 验证：三份数值逐一对照

## 5. 文档与收尾

- [x] 5.1 README / `docs/新手图文教程.md` 里的产品名、exe 名、apk 名同步为新名 — 验证：grep 旧名无用户可见残留
- [x] 5.2 构建产物验证：PyInstaller 打包出 `dist/阿福代肝控制器/阿福代肝控制器.exe` 并实际启动（界面 + 服务都起来了）；Gradle 出 `app-debug.apk`（包名 `com/afu/controller` 523 处、`com/gameorch` 0 处）— 验证：exe 能启动、窗口标题与图标正确；APK 安装后图标与名称正确
- [x] 5.3 清理本次产生的临时文件 — 已删 `_refs/`（参考图快照，7MB，只用于定构图方向）；保留 `dist/`（构建产物）、`assets/icons/preview-*.png`（小尺寸检查用）、`desktop/selftest.py`（回归自检）。旧包 `游戏编排器/` 未动，由用户决定何时删

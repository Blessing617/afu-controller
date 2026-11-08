# 任务

## 1. 桌面端：命令文字不可见

- [x] 1.1 命令框 `setStyleSheet` 同时设 `background` 与 `color` — 验证：深色主题下命令文字清晰可读
- [x] 1.2 检查其它 setStyleSheet 是否有同样问题 — 验证：纯色圆点无需文字色；依赖提示只设 color 是对的
- [x] 1.3 重新打包并实测 — 验证：界面截图中命令可见

## 2. 手机端：返回键失效

- [x] 2.1 定位根因：`enabled = showConnect && state.paired` 在未配对时恒为 false — 验证：代码审查确认
- [x] 2.2 改成三分支：能回主界面就回 / 不能回给提示但不退出 / 已配对主界面放行 — 验证：`blockBack` 逻辑
- [x] 2.3 `AppViewModel.toast()` 由 private 改 public — 验证：界面层可调用
- [x] 2.4 编译 APK 并装到真机 — 验证：BUILD SUCCESSFUL + install Success
- [x] 2.5 真机验证：未配对时按返回，APP 不退到桌面 — 验证：`mCurrentFocus` 仍是 com.gameorch.app

## 3. 收尾

- [x] 3.1 桌面端重新打包并替换 — 验证：exe 更新
- [x] 3.2 清理构建产物 — 验证：无 _dist_qt / _build_qt

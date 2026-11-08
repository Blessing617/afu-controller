# 变更：修复控制台窗口反复闪现

## 动机

用户反馈「启动原神时屏幕上一直有窗口一闪一闪」。高频采样（每 100ms）抓到元凶：

```
出现 +2555ms  tasklist.exe
消失 +2664ms  tasklist.exe
出现 +7748ms  tasklist.exe   ← 每 5 秒一次
```

**是我们自己的代码在闪**：服务用 PyInstaller `--windowed` 打包，进程没有控制台；此时 `subprocess` 启动任何子进程（`tasklist` / `taskkill` / `MuMuManager`）都会为新进程创建控制台窗口。

BGI 适配器每 5 秒检测一次进程存活，于是屏幕上每 5 秒闪一个黑框。

## 范围

在范围内：
- 统一所有子进程调用，抑制控制台窗口
- 覆盖 BGI / M7A / 清理 / 窗口管理 / MAA / 停止接口 / winutil

不在范围内：
- 其它窗口问题（遮罩窗口已在 app-fixes 关闭）

## 方法

新增 `app/engine/proc.py`，提供 `run()` 与 `spawn()`，内置 `CREATE_NO_WINDOW`。
把 7 个模块里的 `subprocess.run` / `subprocess.Popen` 全部替换为这两个函数。

## 关于 delta 规格

本变更**不修改主规格**：这是实现层缺陷修复，对外可见行为没有新增或变更（只是不再闪窗）。

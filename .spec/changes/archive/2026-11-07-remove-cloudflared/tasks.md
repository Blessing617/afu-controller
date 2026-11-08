# 任务

## 1. 代码移除

- [x] 1.1 删除 `desktop/main.py` 的 `TunnelHost` 类 — 验证：`hasattr(m, 'TunnelHost')` 为 False
- [x] 1.2 补回被误删的 `main()` 与 `cleanup_legacy_autostart()` — 验证：函数列表里两者都存在，程序能启动
- [x] 1.3 删除 `qt_ui.py` 的隧道卡片、`sig_tunnel` 信号、`_on_tunnel` 回调 — 验证：grep 无残留
- [x] 1.4 `_poll_tunnel` 改名 `_poll_status`，去掉隧道相关分支 — 验证：定时器连接的是 `_poll_status`
- [x] 1.5 构造函数去掉 `tunnel` 参数 — 验证：`MainWindow(host, data_dir, fallback, port)` 签名
- [x] 1.6 服务启停、关闭窗口处去掉 `tunnel.start()/stop()` — 验证：grep 无 `self.tunnel`

## 2. 依赖清单

- [x] 2.1 从 `server/app/deps.py` 的 `DEPS` 移除 cloudflared 条目 — 验证：清单只剩 6 项
- [x] 2.2 `deps_status()` 去掉 cloudflared 特殊分支 — 验证：不再有 `if item["id"] == "cloudflared"`
- [x] 2.3 `server/app/api/deps.py` 删除 `cloudflared_path()` / `_available()` — 验证：接口实测返回 6 项
- [x] 2.4 接口实测 `/api/deps` 不含 cloudflared — 验证：curl 后检查 id 列表

## 3. 测试

- [x] 3.1 删除 `tests/test_tunnel.py`（TunnelHost 已不存在） — 验证：文件不存在
- [x] 3.2 删除 `tests/test_deps_api.py`（测的是已删的 cloudflared_path） — 验证：文件不存在
- [x] 3.3 更新 `test_deps.py`：清单从 7 项改 6 项，新增「不含 cloudflared」回归测试 — 验证：测试通过
- [x] 3.4 全部测试通过 — 验证：`pytest tests/ -q` 31 passed

## 4. 打包与文件

- [x] 4.1 `游戏编排器.spec` 移除 cloudflared 打包项 — 验证：新包 `_internal` 下无 cloudflared.exe
- [x] 4.2 删除仓库根的 `cloudflared.exe`（53MB） — 验证：文件不存在
- [x] 4.3 删除已装目录里的 cloudflared.exe — 验证：`游戏编排器/_internal/` 下无该文件
- [x] 4.4 重新打包 — 验证：打包成功
- [x] 4.5 确认体积下降 — 验证：155.7MB → 102.9MB

## 5. 文档

- [x] 5.1 README 删除「另一种选择：cloudflared」整节 — 验证：grep 无 cloudflared
- [x] 5.2 README 的三方案对比表去掉 cloudflared 行 — 验证：表格只剩两行
- [x] 5.3 全 README grep 确认无 cloudflared / trycloudflare — 验证：无匹配

## 6. 验证

- [x] 6.1 源码启动正常，health 200 — 验证：curl 返回 200
- [x] 6.2 打包版启动正常，只有一个窗口，无异常弹框 — 验证：窗口数 1，health 200
- [x] 6.3 总览页正常显示固定地址 — 验证：截图显示 https://host.tailxxxxxx.ts.net
- [x] 6.4 用户数据保留 — 验证：data 下 config/auth/discovery 齐全

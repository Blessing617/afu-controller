# 任务

- [x] 1.1 APP 连接自动重试（每 5 秒）+ 断连提示卡 + 手动「重新连接」/「断开连接」— 验证：先开 APP 后启动电脑端，APP 自动连上，无需重开
- [x] 1.2 清理覆盖 MuMu 主程序 — 验证：cleanup 返回 `killed: ["MAA.exe","MuMuNxMain.exe"]`，任务管理器里 MuMu 主程序消失
- [x] 1.3 MAA 加解密弹窗 — 验证：清空 `RemoteControlUserIdentity` 后启动无弹窗，且 `online: true, polls` 正常增长
- [x] 1.4 BGI 遮罩窗口 — 验证：`maskWindowConfig.maskEnabled` 置 false 后原神启动不再出现遮罩窗口
- [x] 1.5 窗口焦点竞争 — 验证：窗口激活改用 AttachThreadInput 绕过前台锁；任务前最小化其它工具窗口。星铁实测 `success 73.5s`（此前报「无法切换界面」）

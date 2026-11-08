# Delta：performance

## ADDED Requirements

### Requirement: 界面动效的性能预算

两端 SHALL 在播放界面动效时保持流畅，MUST NOT 用动画掩盖卡顿：

- 电脑端：页面切换与按压动效期间，窗口 MUST 可拖动、导航可点；
  动效 MUST NOT 阻塞界面线程，MUST NOT 在滚动区域内使用投影特效。
- 手机端：动效期间 MUST NOT 出现可感知掉帧；无限循环动画 MUST 只出现在
  「任务正在运行」的主按钮上，任务停止后 MUST 立即取消。
- 两端：动效 MUST NOT 引起布局抖动（相邻控件位移），
  系统开启「减少动画」时 MUST 退化为直接切换且功能不变。

验证口径：手机端 MUST 用 release 包在真机上测量，MUST NOT 用 debug 包的数据下结论；
电脑端 MUST 用实际窗口交互观察，MUST NOT 只凭代码推断。

#### Scenario: 切页不卡

- GIVEN 用户连续快速点击三个导航项
- WHEN 动效播放中
- THEN 窗口可拖动、点击有响应
- AND 不出现「窗口未响应」或白屏

#### Scenario: 循环动画不常驻

- GIVEN 没有任务在运行
- WHEN 静置 30 秒观察 CPU 与帧
- THEN 界面上没有任何无限循环动画
- AND CPU 占用不因动画上升

#### Scenario: release 包测量

- GIVEN 手机已连上电脑
- WHEN 安装 release 包并操作界面
- THEN 记录到的掉帧比例低于可感知阈值
- AND 测量命令与结果写在验证记录里，可复现

# Delta：branding

## ADDED Requirements

### Requirement: 界面字体

应用 SHALL 随包分发一款开源中文字体用于标题、按钮文字、时间与地址数字，
MUST NOT 依赖系统已装字体才能呈现品牌观感。

字体 SHALL 为可商用且允许随应用分发的开源授权（如 SIL OFL 1.1），
字体文件与许可证全文 SHALL 一起放在仓库的 `assets/fonts/<字体名>/` 下。
若最终无法采用第三方字体，应用 SHALL 回退系统字体，并在 README 中如实说明，
MUST NOT 声称使用了实际未打包的字体。

#### Scenario: 干净机器上仍然是品牌字体

- GIVEN 一台从未安装过该字体的电脑
- WHEN 用户打开应用查看标题
- THEN 显示的是打包的圆体，而不是回退成微软雅黑

#### Scenario: 字体授权可追溯

- GIVEN 检查仓库 `assets/fonts/` 目录
- WHEN 打开其中的许可证文件
- THEN 能看到完整的授权原文与字体名称
- AND README 的第三方声明里登记了它

### Requirement: 视觉素材的来源与授权

界面中所有装饰图形（鲸鱼形象、尾鳍、气泡、水波、图标）SHALL 为项目原创绘制或
明确许可的开源资源，并 SHALL 在 `assets/` 下能对应到源文件（SVG 或生成脚本）。

MUST NOT 使用游戏厂商的美术素材；MUST NOT 直接使用来源不明的网图位图。

本次新增的装饰素材 SHALL 与既有「大肥鱼抱手柄」形象属于同一视觉家族，
MUST NOT 引入第二套互不相关的吉祥物。

#### Scenario: 每个图形都有出处

- GIVEN 检查仓库内所有界面图形资源
- WHEN 逐个回溯来源
- THEN 每个文件都能对应到 `assets/` 下的源文件与生成脚本，或第三方授权说明
- AND 不存在孤立的不明来源图片

#### Scenario: 形象统一

- GIVEN 用户同时看到应用图标、侧边栏品牌区与手机端顶部
- WHEN 观察其中的鲸鱼形象
- THEN 是同一形象的不同姿态/裁切
- AND 不出现第二种吉祥物

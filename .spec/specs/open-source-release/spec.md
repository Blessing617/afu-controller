# open-source-release

## Purpose

把「本地能跑的项目」变成一个别人能看懂、能安全公开的 GitHub 仓库：
内容边界清楚、敏感信息零残留、README 能带人走通、许可证与第三方声明齐全。
本能力只管「仓库对外呈现什么」，不改变程序行为。

## Requirements

### Requirement: 仓库内容边界

公开仓库 SHALL 只包含：源码、可追溯的资源文件、必需文档、构建与使用说明。
以下内容 MUST NOT 进入仓库或提交历史：

- 运行时数据（配对信息、任务记录、日志、数据库文件）
- 依赖安装目录、虚拟环境、包管理器缓存
- 构建产物（`dist/`、`build/`、`*.apk`、`*.exe`、`_internal/`）
- 签名密钥与凭证（`*.jks`、`*.keystore`、`keystore.properties`、token）
- 缓存与临时文件（`__pycache__`、`.pytest_cache`、`_tmp/`、测试输出目录）

仓库 SHALL 提供 `.gitignore` 覆盖上述类别；首次提交前 SHALL 用
`git status --ignored` 人工核对一遍将要提交的文件清单。

#### Scenario: 首次提交前的清单核对

- GIVEN 仓库已 `git init` 并写好 `.gitignore`
- WHEN 执行 `git status --ignored` 并逐条查看
- THEN 列出的待提交文件都是源码、资源、文档
- AND 被忽略的文件里能看到 venv、构建产物、运行数据、缓存
- AND 没有任何一项被误加入暂存区

#### Scenario: 历史里没有大文件

- GIVEN 推送前的本地仓库
- WHEN 检查提交历史中的文件体积
- THEN 没有单个文件超过 5MB（字体、截图等必要资源除外，且已说明来源）
- AND 不存在被 `.gitignore` 排除却已进入历史的文件

### Requirement: 敏感信息脱敏

仓库内所有文本与图片 SHALL 不含作者的私有信息，至少包括：
真实公网域名（`*.ts.net` 主机名）、真实主机名、真实局域网 IP 段、真实姓名、
QQ / 邮箱、本机绝对路径（含用户名）、签名密钥路径。

示例地址 SHALL 使用明显的占位形式（如 `https://你的主机名.你的随机串.ts.net`
或 `https://demo-node.example.ts.net`），使读者不会误以为是可直接使用的地址。

README 与教程 SHALL NOT 让读者「照抄作者的地址」，SHALL 说明地址由读者自己的 Tailscale 生成。

#### Scenario: 全仓扫描无残留

- GIVEN 仓库内容已改写
- WHEN 对全部受版本控制的文本文件执行敏感串扫描（真实域名、主机名、内网 IP、邮箱、用户目录路径）
- THEN 命中数为 0
- AND 扫描脚本与关键词清单一起提交，便于日后复查

#### Scenario: 截图里看不到真实地址

- GIVEN README 中的界面截图
- WHEN 放大查看地址区域
- THEN 显示的是占位地址或已遮挡
- AND 不出现作者的真实 `*.ts.net` 域名或内网 IP

#### Scenario: 教程不误导

- GIVEN 读者按教程操作
- WHEN 看到示例地址
- THEN 教程明确告诉他这个地址要换成自己生成的
- AND 不会出现「直接填这个地址就能连」的表述

### Requirement: README 与教学引导

仓库 SHALL 有一份 README，结构包含：产品一句话说明、功能概览、演示截图、
快速开始（电脑端 + 手机端）、外部依赖与下载地址、架构简述、构建方式、
常见问题、许可证、第三方声明。

README SHALL 面向「没用过自动化工具的新人」写：每个外部依赖给出官网与安装要点，
连接方式（局域网 / 公网固定地址）分别说明适用场景与限制。

README MUST NOT 包含开发过程中的内部验证记录、待办、作者本机的调试细节。

#### Scenario: 新读者能判断「适不适合我」

- GIVEN 读者第一次打开仓库
- WHEN 阅读 README 前两屏
- THEN 能知道这是做什么的、需要先装哪些外部软件、手机怎么连
- AND 能看到至少一张真实界面截图

#### Scenario: 图文教程可用

- GIVEN 读者打开 `docs/新手图文教程.md`
- WHEN 按步骤操作
- THEN 每一步都有可执行的动作与判断标准
- AND 文中的截图与当前界面一致（不含旧版界面截图）
- AND 所有外部链接可访问（给出主站或 Releases 页，不写死具体版本号）

### Requirement: 许可证与第三方声明

仓库 SHALL 包含 `LICENSE`，授权条款与作者既有项目保持一致（PolyForm Noncommercial 1.0.0），
并在文件内保留 `Required Notice: Copyright (c) <年份> Blessing617` 形式的声明。

仓库 SHALL 包含 `THIRD-PARTY-NOTICES.md`，登记：三个自动化工具（MAA / BetterGI / 三月七小助手）
的名称与项目地址、桌面端框架、随包字体（含 OFL 全文位置）、图标与装饰素材的来源说明。
本程序与上述工具的关系 SHALL 写明「只是调用它们，不包含其代码与素材」。

#### Scenario: 许可证存在且一致

- GIVEN 检查仓库根目录
- WHEN 打开 `LICENSE`
- THEN 是 PolyForm Noncommercial 1.0.0 全文，含 Required Notice
- AND README 的「许可证」一节与之一致

#### Scenario: 第三方登记齐全

- GIVEN 检查 `THIRD-PARTY-NOTICES.md`
- WHEN 对照程序实际使用的依赖与资源
- THEN 每个外部工具、框架、字体、素材都有登记
- AND 字体授权文件路径指向仓库内实际存在的文件

### Requirement: README 截图尺寸一致

README 中展示的界面截图 SHALL 保持一致的视觉尺寸：同一端的截图 SHALL 使用同一分辨率拍摄，
在 README 中 SHALL 用统一的显示宽度（同一组图片宽度相同），MUST NOT 出现一张大一张小。

桌面端截图与手机端截图 SHALL 分组展示（各自的宽高比不同），MUST NOT 混排在同一行。

截图中 MUST NOT 出现作者本机的目录路径、真实域名、内网 IP 或其它个人信息。

#### Scenario: 一眼看过去是整齐的两组

- GIVEN 读者打开 README
- WHEN 浏览「界面预览」一节
- THEN 桌面截图一组、手机截图一组
- AND 每一组里的图片显示宽度完全相同
- AND 没有一张图明显比同组其它图大

#### Scenario: 截图不含隐私

- GIVEN 放大查看任意一张 README 截图
- WHEN 检查地址栏、路径、连接信息
- THEN 地址是占位形式或界面本来就不显示地址
- AND 看不到本机目录路径与真实域名

### Requirement: 可复现的构建与安装路径

README SHALL 给出两端可复现的构建命令：电脑端从源码运行与打包、手机端
`assembleRelease` 与 `adb install -r`，并写明所需 JDK / Android SDK / Python 版本。

构建说明 MUST NOT 依赖作者本机的绝对路径或私有环境变量；
需要用户自行配置的项（SDK 路径、Gradle 缓存目录）SHALL 以占位符给出。

#### Scenario: 别人能照着构建

- GIVEN 一台装好 JDK、Android SDK、Python 的机器
- WHEN 按 README 的命令执行
- THEN 能得到可运行的电脑端程序与可安装的 APK
- AND 没有命令要求访问作者本机路径

### Requirement: 首次推送前的完整验证

推送前 SHALL 完成一次端到端验证：本地仓库内容与工作区一致、脱敏扫描为 0 命中、
`README` 内图片与链接在仓库内可达；推送后 SHALL 在新目录 `git clone` 一次并抽查内容完整。

#### Scenario: clone 回来仍然完整

- GIVEN 仓库已推送
- WHEN 在空目录执行 `git clone`
- THEN 目录结构与 README 一致
- AND README 引用的截图文件都存在
- AND `git status` 干净

#### Scenario: 推送失败不留半成品

- GIVEN 推送过程中网络失败
- WHEN 重试
- THEN 本地提交保持不变，重试后成功
- AND 不产生分叉或强推覆盖他人提交

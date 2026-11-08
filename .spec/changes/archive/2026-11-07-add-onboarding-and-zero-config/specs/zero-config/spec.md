# Delta：zero-config

## Purpose

让程序在**任意 Windows 机器**上解压即用，不依赖作者这台机器的目录结构、网卡和端口。这是开源的硬前提。

## ADDED Requirements

### Requirement: 端口自适应

系统 SHALL 不把服务端口写死。启动时若首选端口被占用，SHALL 自动改用可用的备用端口并继续启动，而不是启动失败。
实际使用的端口 SHALL 在桌面应用界面上明确展示，且手机端 SHALL 能通过局域网自动发现拿到该端口。

#### Scenario: 首选端口被占用

- GIVEN 8765 端口已被其它程序占用
- WHEN 用户启动桌面应用
- THEN 服务改用其它可用端口成功启动
- AND 界面上显示的是实际端口
- AND 不出现「服务启动超时（端口未就绪）」

#### Scenario: 手机自动发现拿到正确端口

- GIVEN 服务运行在非默认端口上
- WHEN 手机在同一局域网执行自动发现
- THEN 能发现该电脑
- AND 拿到的端口与实际监听端口一致

### Requirement: 连接地址自动探测

系统 SHALL 自动列出本机所有可用于手机连接的地址，并按「Tailscale → 局域网 → 其它」排序展示，用户不需要手工查 IP。
系统 SHALL NOT 在界面或代码里写死任何具体 IP 地址或域名。

#### Scenario: 多网卡环境

- GIVEN 电脑同时有 Tailscale、有线与无线网卡
- WHEN 用户查看连接信息
- THEN 三个地址都被列出
- AND Tailscale 地址排在第一位

#### Scenario: 只有局域网

- GIVEN 电脑没有安装 Tailscale
- WHEN 用户查看连接信息
- THEN 正常显示局域网地址
- AND 不提示 Tailscale 相关的错误

### Requirement: 数据目录可移植

系统 SHALL 把所有运行数据（配置、配对凭据、日志）存放在**可执行文件同级**的 `data` 目录，不写系统盘、不写用户目录、不依赖安装位置。
以源码方式运行时 SHALL 使用项目内的 `server/data`。
当可执行文件所在目录不可写时，系统 SHALL 退回用户目录并在界面上说明实际使用的位置。

#### Scenario: 换机器解压即用

- GIVEN 用户把整个程序目录复制到 D 盘另一个位置
- WHEN 用户启动应用
- THEN 在新位置正常创建并使用新的 data 目录
- AND 不读取旧路径的数据，也不因路径变化报错

#### Scenario: 放在只读位置

- GIVEN 程序被解压到需要管理员权限的只读目录
- WHEN 用户启动应用
- THEN 退回用户目录存放数据
- AND 界面上明确显示实际数据目录位置

### Requirement: 公网隧道稳定

系统 SHALL 在同一会话内维持**一个**公网隧道，SHALL NOT 因监控逻辑重复启动多个 tunnel 进程。
隧道意外退出时 SHALL 只重启一次并通知用户地址已变化。
公网地址变化后 SHALL NOT 静默让手机继续使用旧地址。

#### Scenario: 正常建立隧道

- GIVEN 服务已启动且网络可用
- WHEN 隧道建立成功
- THEN 日志里只有一次「已启动 cloudflared」
- AND 界面上显示一个稳定的公网地址

#### Scenario: 隧道进程意外退出

- GIVEN 隧道已建立
- WHEN cloudflared 进程意外退出
- THEN 系统重启恰好一个隧道进程
- AND 界面提示「公网地址已变化，请用新地址重新连接」

#### Scenario: 用户关闭隧道

- GIVEN 隧道正在运行
- WHEN 用户关闭应用或主动停止服务
- THEN 隧道进程被清理，不残留后台进程

### Requirement: 缺失 cloudflared 的降级

系统 SHALL 在找不到 cloudflared 时仍能正常提供局域网连接，并说明公网功能不可用及其原因。
系统 SHALL 提供获取 cloudflared 的官方链接，不静默失败。

#### Scenario: 没有 cloudflared

- GIVEN 程序目录中不存在 cloudflared.exe
- WHEN 用户启动应用
- THEN 服务正常启动，局域网地址可用
- AND 界面上说明「未找到 cloudflared，公网访问不可用」并给出下载链接
- AND 不影响局域网内的手机连接

### Requirement: 内置说明文档

系统 SHALL 在桌面应用中提供可直接打开的说明文档，内容至少包括：使用前需要准备什么、每项依赖的官网、如何连接手机、常见故障怎么排查。
系统 SHALL 提供对外的公开文档地址（README），供未安装软件的人阅读。

#### Scenario: 从界面打开说明

- GIVEN 桌面应用正在运行
- WHEN 用户点击「帮助 / 说明」
- THEN 打开本地说明文档
- AND 文档中的官网链接可点击

#### Scenario: 说明文档内容完整

- GIVEN 新用户拿到程序目录
- WHEN 他打开 README
- THEN 能看到「先装 MAA / MuMu / BetterGI」这类前置要求
- AND 每项都附有官网地址

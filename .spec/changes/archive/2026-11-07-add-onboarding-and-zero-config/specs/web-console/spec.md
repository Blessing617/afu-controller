# Delta：web-console

## Purpose

服务跑起来后，除了手机 APP，用户还应能用浏览器直接看状态、配对、排障。这是零安装的备用入口，也是给新用户「打开网页看看」最直观的体验。

## ADDED Requirements

### Requirement: 内置网页控制台

系统 SHALL 在服务端提供一个可直接在浏览器打开的网页控制台。
该页面 SHALL 在**离线、无外网**的环境下完整渲染，SHALL NOT 依赖任何境外 CDN 才能显示内容。

#### Scenario: 断网打开网页

- GIVEN 电脑没有连接互联网
- WHEN 用户在浏览器打开本地服务地址的首页
- THEN 页面样式与内容完整显示
- AND 不出现白屏或样式错乱

#### Scenario: 从桌面应用打开

- GIVEN 桌面应用正在运行
- WHEN 用户点击「打开网页」
- THEN 浏览器打开的是可用的控制台页面，而不是白屏

#### Scenario: 页面不要求先配对

- GIVEN 尚未配对任何设备
- WHEN 用户打开网页控制台首页
- THEN 能看到当前配对码与连接地址
- AND 不需要先输入 token 才能看到这些信息

### Requirement: API 文档可离线访问

系统 SHALL 保留 API 文档入口，并 SHALL 保证文档页面的静态资源随应用一起分发，不依赖外网 CDN。

#### Scenario: 内网机器查看接口文档

- GIVEN 电脑只有局域网、无外网
- WHEN 用户打开 API 文档页
- THEN 接口列表与「试一试」功能正常可用
- AND 样式完整加载

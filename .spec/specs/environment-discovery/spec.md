# environment-discovery

## Purpose

电脑端自己搞清楚「游戏和三个小助手装在哪」，用户不用手工翻目录；同时保留手动纠正的能力。

## Requirements

### Requirement: 自动探测游戏路径

系统 SHALL 通过注册表与常见目录扫描自动定位《原神》与《崩坏：星穹铁道》的游戏可执行文件。

#### Scenario: 注册表命中

- GIVEN 游戏由官方安装器安装并写入了注册表
- WHEN 执行路径探测
- THEN 从注册表读取安装记录并解析出游戏可执行文件所在位置
- AND 校验该可执行文件确实存在才采纳

#### Scenario: 注册表不可用时扫描

- GIVEN 注册表没有可用记录（绿色版、迁移过的安装）
- WHEN 执行路径探测
- THEN 在各磁盘根目录按「原神 / 星穹铁道 / Genshin / StarRail / miHoYo」等关键词做有限深度的目录扫描
- AND 只把命中且校验通过的结果作为候选

#### Scenario: 全部未命中

- GIVEN 自动探测没有找到某个游戏
- WHEN 探测结束
- THEN 该项标记为「未找到」而不是报错
- AND 其余已找到的项目照常可用

### Requirement: 自动探测自动化工具

系统 SHALL 自动定位 MAA、BetterGI、三月七小助手的入口可执行文件。

#### Scenario: 通过已知登记文件命中

- GIVEN 三月七小助手曾被运行过并写入了安装登记
- WHEN 执行路径探测
- THEN 从登记文件读出安装目录
- AND 校验其命令行入口存在才采纳

#### Scenario: 通过特征文件名扫描命中

- GIVEN MAA 是绿色版、没有任何注册表记录
- WHEN 执行路径探测
- THEN 在候选目录中按特征文件名（MAA.exe / BetterGI.exe / m7a.exe）匹配
- AND 校验通过才采纳

#### Scenario: 同名文件夹误命中

- GIVEN 扫描到名字相似但实际不含目标可执行文件的目录
- WHEN 校验该候选
- THEN 直接丢弃，不作为结果

### Requirement: 探测结果持久化与人工覆盖

系统 SHALL 保存探测结果，并允许用户手动修改；手动指定的值优先于自动探测。

#### Scenario: 手动指定后不被覆盖

- GIVEN 用户为某个工具手动填写了路径
- WHEN 再次执行自动探测
- THEN 保留用户手动指定的路径
- AND 只更新未被手动指定的项目

#### Scenario: 重新探测

- GIVEN 用户更换了游戏或工具的安装位置
- WHEN 用户在 APP 中触发「重新探测」
- THEN 系统重新执行探测并回报更新了哪些项目

#### Scenario: 手动路径无效

- GIVEN 用户填写的路径不存在或不包含目标可执行文件
- WHEN 保存该路径
- THEN 拒绝保存并提示「该路径下没有找到 XXX」

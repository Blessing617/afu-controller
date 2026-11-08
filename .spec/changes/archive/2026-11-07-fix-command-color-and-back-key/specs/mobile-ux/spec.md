# Delta：mobile-ux

## MODIFIED Requirements

### Requirement: 连接设置页的返回行为

连接设置页 SHALL 响应系统返回操作（返回键与左右边缘滑动手势），返回后回到主界面，SHALL NOT 因此退出 APP。

**未配对时也 SHALL NOT 因返回而退出 APP。** 此时没有可回的主界面，
系统 SHALL 给出一句可读的提示（例如「还没连上电脑」），而不是让 APP 消失。

已配对且停留在主界面时，SHALL 允许返回键正常退出 APP。

#### Scenario: 已配对后从主界面进连接页

- GIVEN 用户已配对并从主界面进入了连接设置页
- WHEN 用户按系统返回键
- THEN 回到主界面
- AND APP 不退出
- AND 停留在进入前的那个游戏页

#### Scenario: 左右边缘滑动

- GIVEN 用户停留在连接设置页
- WHEN 用户从屏幕左右边缘向内滑动
- THEN 回到主界面
- AND APP 不退出

#### Scenario: 未配对时按返回（本次修复）

- GIVEN 用户尚未成功配对任何电脑（首次使用）
- WHEN 用户在连接页按返回键或边缘滑动
- THEN 停留在连接页，APP 不退出到桌面
- AND 给出一句提示，告诉用户还需要填地址和配对码

#### Scenario: 主界面按返回

- GIVEN 用户已配对且停留在某个游戏页
- WHEN 用户按返回键
- THEN APP 正常退出（这是系统的默认行为，不应被拦截）

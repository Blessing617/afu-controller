# Delta：desktop-shell

## ADDED Requirements

### Requirement: 界面文字对比度

界面中所有带背景色的文字区域 SHALL 保证文字与背景有足够对比度，
SHALL NOT 出现「文字与背景同色导致看不见」的情况。

设置背景色的控件 SHALL 同时显式设置文字颜色，SHALL NOT 依赖默认值。

#### Scenario: 命令提示框

- GIVEN 「连接」页显示一条可复制的命令
- WHEN 用户查看它
- THEN 命令文字清晰可见
- AND 在深色与浅色主题下都能看清

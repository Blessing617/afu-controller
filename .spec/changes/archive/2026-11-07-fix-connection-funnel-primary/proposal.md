# 变更：修正连接方案为 Funnel 主路

## 动机

上一轮做手机端时，我把 Tailscale 的两种用法**主次搞反了**：

原设计（`docs/07-实时画面验证.md`）写得很清楚：

> **最终对外方案：Tailscale Funnel（固定域名）**
> 手机端**不用装任何 App**，电脑端只开「游戏编排器」。

而我写成了「手机和电脑都要装 Tailscale、填 `100.x` 地址」——
`100.x` 是 tailnet 内网地址，**手机必须装 Tailscale 并登录**才能用，
这直接违背了「手机端不用装任何 App」这个核心约束。

同时暴露了两个次生问题：

1. **电脑端根本没显示 Funnel 的固定域名** —— 用户得自己去命令行敲
   `tailscale funnel status` 才知道手机该填什么，等于没给。
2. **解析 Funnel 域名的正则写错了** —— 只考虑 `xx.ts.net` 两段，
   而实际域名是 `host.tailxxxxxx.ts.net` 四段，导致永远解析不出来。

## 范围

在范围内：

- README 的连接方案说明改成 Funnel 主路
- 手机端连接页文案改回「手机不用装任何软件」
- 电脑端新增「公网固定地址（Funnel）」卡片，显示固定域名
- 修 Funnel 域名解析正则
- 处理 `tailscale funnel status` 需要管理员权限的情况

不在范围内：

- 移除 `100.x` 支持（它仍然可用，只是降级为进阶选项）
- 服务端接口改动

## 方法

在电脑端加一张卡片专门显示 Funnel 的固定域名，用
`tailscale funnel status` 的输出解析。

要注意这个命令连的是
`\\.\pipe\ProtectedPrefix\Administrators\Tailscale\tailscaled`，
**普通权限会拿到 Access is denied**——所以要区分「没开 Funnel」和
「没权限查」，否则会误导用户以为没配。

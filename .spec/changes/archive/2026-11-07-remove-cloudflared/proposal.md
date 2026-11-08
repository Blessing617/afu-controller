# 变更：移除 cloudflared 临时隧道

## 动机

设计文档 `docs/07-实时画面验证.md` 里对 cloudflared 的定位是：

> 期间也试过 Cloudflare 快速隧道（`cloudflared`，2.1s、**地址每次变**），
> 已集成进 exe 作为**备用**。

它是探索期留下的备用方案。但实际界面把它摆在了「连接」页的显著位置，
标题叫「公网隧道」，而真正的固定地址（Tailscale Funnel）反而要另找。

用户实测时直接照着那个 `trycloudflare.com` 地址填，结果连不上——
因为它每次重启都变，和固定地址完全是两回事。

用户明确要求：**这个东西不该留下。**

## 范围

在范围内：

- 删除 `desktop/main.py` 中的 `TunnelHost` 类与全部调用
- 删除 `qt_ui.py` 中的隧道卡片、信号、轮询逻辑
- 删除打包配置里的 cloudflared.exe（省 53MB）
- 删除仓库里的 `cloudflared.exe`
- 从 `server/app/deps.py` 的依赖清单移除 cloudflared 条目
- 删除对应测试
- README 移除 cloudflared 相关内容

不在范围内：

- Tailscale Funnel 的行为（不变）
- 局域网 / `100.x` 两种连接方式（不变）

## 方法

公网访问从此只有 **Tailscale Funnel 一条路**（固定地址）。
移除后打包体积从 155.7MB 降到 102.9MB。

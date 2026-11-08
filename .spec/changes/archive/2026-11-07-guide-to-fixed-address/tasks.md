# 任务

## 1. 四步检查表

- [x] 1.1 新增 `_tailscale_setup_state()`：一次返回 installed / logged_in / funnel_on / url / port — 验证：调用后能拿到 `{'installed': True, 'funnel_on': True, 'url': 'https://host.tailxxxxxx.ts.net'}`
- [x] 1.2 连接页「公网固定地址」卡片改成四步检查表（①注册 ②安装 ③登录 ④开启 Funnel） — 验证：界面上四条状态行
- [x] 1.3 每步按检测结果显示绿色完成 / 红色待办，并写明去点哪里 — 验证：代码分支覆盖四种组合
- [x] 1.4 卡片顶部说明「这个网址不是编的，是做完四步后 Tailscale 给你的」 — 验证：说明文字存在
- [x] 1.5 地址出现后大字显示 — 验证：15px 粗体等宽

## 2. 临时隧道移出主路径

- [x] 2.1 从「连接」页删除 cloudflared 卡片 — 验证：连接页只剩固定地址相关内容
- [x] 2.2 移到「设置」页，标题写明「临时公网隧道（备用，地址会变）」 — 验证：设置页有该卡片
- [x] 2.3 说明文字写明缺点「地址每次重启都会变，手机要重新填」 — 验证：文案存在
- [x] 2.4 `_poll_tunnel` 里对 tunnel_state 做存在性判断，控件不在时不崩 — 验证：`getattr(self, "tunnel_state", None)`

## 3. 启动期缓存域名

- [x] 3.1 新增 `_cache_funnel_domain()`：启动时调 `tailscale status --json` 读 DNSName 写进 config — 验证：config.json 的 public_url 被填充
- [x] 3.2 读取失败时保留已有缓存，不覆盖成空 — 验证：代码分支 `if out.returncode != 0: return`
- [x] 3.3 config 默认值加 `public_url` 字段 — 验证：新数据目录会生成

## 4. 文档

- [x] 4.1 README 加「这个网址到底是怎么来的？」四步表格 — 验证：注册/安装/登录/开启 Funnel 四行
- [x] 4.2 说明「第 ④ 步做完，地址才会出现」 — 验证：加粗提示
- [x] 4.3 说明「第 ④ 步只做一次，以后不变」 — 验证：提示块
- [x] 4.4 加「本程序会帮你盯到哪一步」的四行示例 — 验证：代码块展示检查表样式
- [x] 4.5 保留域名结构拆解表与「不能照抄」警告 — 验证：原有内容保留

## 5. 验证

- [x] 5.1 桌面端语法检查通过 — 验证：ast.parse 无异常
- [x] 5.2 `_tailscale_setup_state()` 实测返回正确字段 — 验证：Python 调用输出
- [x] 5.3 打包成功并替换到正式目录，保留用户 data — 验证：data 下文件齐全
- [x] 5.4 启动后 config 里 public_url 有值 — 验证：读 config.json

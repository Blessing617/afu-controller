# 设计：定时执行

## 为什么放在服务端

定时必须由**电脑端**执行：手机可能不在线、APP 可能被系统杀掉、网络可能中断。
手机端只负责「改配置」和「看状态」，这一点和现有编排一致。

## 数据结构

`data/schedule.json`（与 `chain.json` 并列，单独文件便于整份替换与备份）：

```json
{
  "enabled": true,
  "times": ["08:00", "20:00"],
  "weekdays": [1, 2, 3, 4, 5],
  "last_fired": { "2026-11-08T08:00": "2026-11-08T08:00:12" }
}
```

- `weekdays` 空数组 = 每天
- `last_fired` 记录「某个日期+时间点」上次触发的时刻，用来做「同一天只跑一次」；
  保留最近 16 条即可，不需要清理逻辑。

## 调度循环

`core/scheduler.py` 起一个守护线程，每 **20 秒**检查一次：

```python
now = datetime.now()
for slot in times:
    key = f"{now:%Y-%m-%d}T{slot}"
    if not enabled: continue
    if weekdays and now.isoweekday() not in weekdays: continue
    if key in last_fired: continue
    if now.hour == hh and now.minute == mm:
        fire(slot, key)
```

几个刻意的设计：

1. **用「当前分钟匹配」而不是「越过某个时间点」**。这样电脑休眠醒来时如果刚好是
   08:00 那一分钟内会正常触发；错过之后（09:00 才醒）就自然不补跑，
   不需要额外的「错过判定」逻辑。
2. **20 秒一次**：分钟级精度足够，又不至于空转。检查本身只是几次比较，几乎不耗 CPU。
3. **触发前先记 `last_fired` 再启动**：避免 ORCH 启动失败后下一轮又试一次（同一个分钟里重试两次没有意义，
   而且会掩盖错误）。

## 触发动作：先重置，再从头跑

```python
def fire(slot):
    # 1) 停掉正在跑的链（等待收敛，最多 60 秒）
    if ORCH.is_running():
        ORCH.request_stop()
        wait_until(lambda: not ORCH.is_running(), 60)
    # 2) 停掉单步任务
    if RUNNER.current() is not None:
        core_tasks.stop_current()
    # 3) 全量清理：游戏、MAA、MuMu、BetterGI、三月七
    cleanup_all()
    # 4) 从头开始一条新链
    ORCH.start(load_chain())
```

**为什么不是「有任务在跑就跳过」**：用户明确要求「到点强制重置，全部软件进程关掉，然后从头开始」。
实际收益也很明显——残留的游戏/模拟器会抢前台键鼠并占掉十几 GB 内存，
不清理直接跑，下一个引擎大概率起不来（2026-11-08 就出过 `OpenCV Insufficient memory`）。

代价是**会关掉用户正在玩的游戏**。这一点在编排页的定时卡片上要写明，用户开定时即视为接受。

每次触发都往 `schedule.log.json` 记一条（最近 20 条）：触发时间、重置时关掉了哪些进程、是否成功。

## 强制停止

`POST /api/schedule/stop`：

1. `ORCH.request_stop()`（若链在跑）
2. 等链线程收敛（最多 30 秒）
3. `core.tasks.stop_current()`（若还有单步任务）
4. `cleanup_all()`（关 MAA / MuMu / BetterGI / 游戏）
5. 返回实际关闭的进程列表

界面侧：关闭定时开关时，如果 `ORCH.is_running()` 或 `RUNNER.current()` 不为空，
弹出「同时停止正在运行的任务？」选项，默认勾选（用户的需求是「关定时就要收干净」），
但也允许只关定时。

## 手机端

编排页顶部加一张「定时」卡片：

```
⏰ 定时执行                    [开关]
   08:00   ✕        20:00   ✕        [+ 添加时间]
   周一 周二 周三 周四 周五 周六 周日
   下次运行：明天 08:00
```

- 时间点用系统时间选择器（`TimePickerDialog`）
- 星期用一排可点击的胶囊
- 每次改动立即 `PUT /api/schedule`（沿用编排页「改了就存」的习惯）
- 断网时沿用编排页的本地暂存逻辑（已有）

## 与 MAA 的取舍

| MAA 的做法 | 我们的选择 | 原因 |
|---|---|---|
| `Timers.List` 8 个时间点，各自可启用 | `times` 列表，加/删 | 更直观；不需要「预留 8 个空位」 |
| `UseWeeklySchedule` 按星期 | `weekdays` | 同 |
| `ForceScheduledStart` 到点强制启动 | **不做**：有任务在跑就跳过 | 强插会打断用户正在跑的任务，风险比收益大 |
| `ScheduledWakeUp` 定时唤醒 | **不做** | 要改电源策略，失败时会把电脑弄成睡不醒 |
| 提前 N 分钟通知 | 不做 | 手机通知不在本项目范围内 |

"""核心层：任务生命周期、日志流、编排与配置。

依赖方向：`api → core → engine → platform`。core 是任务状态的唯一持有者，
engine 只上报事件，platform 不依赖上层。
"""

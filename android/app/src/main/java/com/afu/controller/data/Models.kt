package com.afu.controller.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// ---------- 服务端接口模型 ----------

@Serializable
data class Health(
    val ok: Boolean = false,
    val version: String = "",
    @SerialName("pairing_pending") val pairingPending: Boolean = false,
    @SerialName("server_time") val serverTime: String = "",
    @SerialName("uptime_seconds") val uptimeSeconds: Int = 0,
)

@Serializable
data class PairRequest(val code: String, val device: String = "android")

@Serializable
data class PairResponse(val token: String = "", val paired: Boolean = false)

@Serializable
data class PathEntry(
    val path: String = "",
    val found: Boolean = false,
    val source: String = "none",
    val label: String = "",
)

@Serializable
data class GameInfo(
    val label: String = "",
    val ready: Boolean = false,
    val requires: List<String> = emptyList(),
)

@Serializable
data class GamesResponse(
    val games: Map<String, GameInfo> = emptyMap(),
    val paths: Map<String, PathEntry> = emptyMap(),
)

@Serializable
data class TaskRun(
    @SerialName("run_id") val runId: String = "",
    val game: String = "",
    val title: String = "",
    val state: String = "queued",
    @SerialName("started_at") val startedAt: Double = 0.0,
    @SerialName("ended_at") val endedAt: Double? = null,
    @SerialName("duration_seconds") val durationSeconds: Double = 0.0,
    @SerialName("exit_code") val exitCode: Int? = null,
    val error: String = "",
    @SerialName("log_tail") val logTail: List<String> = emptyList(),
    @SerialName("chain_id") val chainId: String = "",
    val tasks: List<String> = emptyList(),
    /** 引擎给出的进度标记，比如 stage=11/13、task=2/4、phase=战斗中 */
    val progress: Map<String, String> = emptyMap(),
    /** 进展快照：距上次进展多久、是否已判卡死 */
    val stall: StallInfo = StallInfo(),
)

/** 任务进展快照。用来区分「跑得久」和「卡住了」——这两件事对用户完全不同。 */
@Serializable
data class StallInfo(
    val state: String = "ok",
    @SerialName("idle_seconds") val idleSeconds: Double? = null,
    @SerialName("elapsed_seconds") val elapsedSeconds: Double = 0.0,
)

@Serializable
data class CurrentTask(
    val current: TaskRun? = null,
    val history: List<TaskRun> = emptyList(),
)

@Serializable
data class CleanupResult(
    val game: String = "",
    val killed: List<String> = emptyList(),
    val message: String = "",
)

@Serializable
data class ErrorDetail(
    val error: String = "",
    val message: String = "",
    /** FastAPI 的 HTTPException 会把内容包在 detail 里，两种格式都要能读 */
    val detail: ErrorDetail? = null,
) {
    /** 优先拿最内层的 message（服务端自己写的人话文案） */
    fun humanMessage(): String {
        val inner = detail?.humanMessage()
        return if (!inner.isNullOrBlank()) inner else message
    }
}

/** 一张游戏画面：JPEG 字节 + 服务端给的元信息（不落盘，用完就丢）。 */
data class ScreenFrame(
    val bytes: ByteArray,
    val capturedAt: String = "",
    val width: Int = 0,
    val height: Int = 0,
    val captureMs: Double = 0.0,
)

/** 统一的调用结果：成功带数据，失败带人话。 */
sealed interface ApiResult<out T> {
    data class Ok<T>(val data: T) : ApiResult<T>
    data class Err(val message: String, val code: Int = 0) : ApiResult<Nothing>
}

// ---------- 编排 ----------

/** 任务链的一步。 */
@Serializable
data class ChainStep(
    val game: String = "",
    val enabled: Boolean = true,
    val tasks: List<String> = emptyList(),
    val label: String = "",
    @SerialName("display_name") val displayName: String = "",
)

/** 任务链。 */
@Serializable
data class Chain(
    val steps: List<ChainStep> = emptyList(),
    val policy: String = "skip",
) {
    companion object {
        val DEFAULT = Chain(
            steps = listOf(
                ChainStep(game = "arknights", displayName = "明日方舟"),
                ChainStep(game = "genshin", displayName = "原神"),
                ChainStep(game = "starrail", displayName = "星穹铁道"),
            ),
        )
    }
}

@Serializable
data class ChainResponse(val chain: Chain = Chain())

/** 引擎能执行的一个子任务。 */
@Serializable
data class EngineTask(
    val id: String = "",
    val name: String = "",
    val enabled: Boolean = true,
    val note: String = "",
)

/** 一个引擎的能力清单。source: engine / fallback / error */
@Serializable
data class Capability(
    val game: String = "",
    val source: String = "fallback",
    val detail: String = "",
    val items: List<EngineTask> = emptyList(),
) {
    /** 是否来自引擎的实际配置（false 表示用的内置默认清单）。 */
    val fromEngine: Boolean get() = source == "engine"
}

/** 链里某一步的执行结果。 */
@Serializable
data class ChainStepResult(
    val index: Int = 0,
    val game: String = "",
    val name: String = "",
    val state: String = "pending",
    @SerialName("duration_seconds") val durationSeconds: Double = 0.0,
    val error: String = "",
    @SerialName("run_id") val runId: String = "",
    val tasks: List<String> = emptyList(),
)

/** 整条链的执行状态。 */
@Serializable
data class ChainRun(
    @SerialName("chain_id") val chainId: String = "",
    val state: String = "running",
    val policy: String = "skip",
    @SerialName("current_index") val currentIndex: Int = -1,
    val total: Int = 0,
    val steps: List<ChainStepResult> = emptyList(),
    val summary: Map<String, Int> = emptyMap(),
    val error: String = "",
)

@Serializable
data class CleanupAllResult(
    val killed: List<String> = emptyList(),
    val message: String = "",
)

@Serializable
data class ChainStatus(
    val running: Boolean = false,
    val chain: ChainRun? = null,
)

// ---------------- 定时执行 ----------------

/** 保存定时配置时提交给电脑端的内容。 */
@Serializable
data class ScheduleConfig(
    val enabled: Boolean = false,
    val times: List<String> = emptyList(),
    /** 1=周一 … 7=周日；空表示每天 */
    val weekdays: List<Int> = emptyList(),
)

/** 一次定时触发的记录。 */
@Serializable
data class ScheduleRun(
    val slot: String = "",
    val at: String = "",
    val killed: List<String> = emptyList(),
    val error: String = "",
)

/** 电脑端返回的定时状态。 */
@Serializable
data class ScheduleInfo(
    val enabled: Boolean = false,
    val times: List<String> = emptyList(),
    val weekdays: List<Int> = emptyList(),
    @SerialName("next_run") val nextRun: String? = null,
    @SerialName("scheduler_running") val schedulerRunning: Boolean = false,
    @SerialName("last_runs") val lastRuns: List<ScheduleRun> = emptyList(),
) {
    fun toConfig() = ScheduleConfig(enabled = enabled, times = times, weekdays = weekdays)
}

/** 强制停止定时任务后，电脑端回收了哪些进程。 */
@Serializable
data class ScheduleStopResult(
    val killed: List<String> = emptyList(),
    val error: String = "",
    val message: String = "",
)

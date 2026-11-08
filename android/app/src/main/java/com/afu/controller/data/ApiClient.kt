package com.afu.controller.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import okhttp3.Dns
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.net.Inet4Address
import java.net.Inet6Address
import java.net.InetAddress
import java.util.concurrent.TimeUnit

/**
 * 与服务端通信。所有方法都返回 ApiResult，UI 只处理「成功」和「人话错误」。
 */
class ApiClient(
    private val baseUrl: String,
    private val token: String = "",
) {
    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        encodeDefaults = true
    }

    /**
     * 强制优先 IPv4。
     *
     * 实测问题（2026-11-08）：手机走 5G 访问 Funnel 域名时，系统 DNS 同时返回
     * IPv6（2403:2500:400:20::e8e）和 IPv4（103.84.155.153）。OkHttp 默认按返回顺序
     * 先试 IPv6，而移动网络的 IPv6 到 Tailscale ingress 是超时的 ——
     * 表现为「电脑端明明在跑、手机却一直未连接」，并最终报 InterruptedIOException。
     * 把 IPv4 排到前面即可稳定连上（ping IPv4 只有 220ms）。
     */
    private val ipv4First = object : Dns {
        private val system = Dns.SYSTEM
        override fun lookup(hostname: String): List<InetAddress> {
            val all = system.lookup(hostname)
            val v4 = all.filterIsInstance<Inet4Address>()
            val v6 = all.filterIsInstance<Inet6Address>()
            // IPv4 优先；没有 IPv4 时才用 IPv6
            return if (v4.isNotEmpty()) v4 + v6 else all
        }
    }

    private val client = OkHttpClient.Builder()
        .dns(ipv4First)
        // callTimeout 之前没设：connectTimeout 只管 TCP 建连，
        // DNS 解析 / TLS 握手 / 代理探测这些阶段卡住时它不生效，
        // 结果就是请求无限期挂着、界面一直「未连接」。
        .callTimeout(20, TimeUnit.SECONDS)
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(210, TimeUnit.SECONDS)   // 启动任务可能等很久
        .writeTimeout(30, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    // 画面请求要短超时：卡住就重来一张，不能拖住界面
    private val screenClient = OkHttpClient.Builder()
        .dns(ipv4First)
        .callTimeout(15, TimeUnit.SECONDS)
        .connectTimeout(6, TimeUnit.SECONDS)
        .readTimeout(12, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    private val jsonMedia = "application/json; charset=utf-8".toMediaType()

    /**
     * 打开服务端的事件推送通道（`/ws?token=...`）。
     *
     * 有推送时就不需要高频轮询了：状态变化由服务端主动发过来，
     * 轮询退化成「兜底探活」。连接失败返回 null，调用方保持轮询即可。
     */
    fun openEventSocket(listener: WebSocketListener): WebSocket? {
        return try {
            val scheme = if (baseUrl.startsWith("https")) "wss" else "ws"
            val rest = baseUrl.substringAfter("://").trimEnd('/')
            val url = "$scheme://$rest/ws?token=$token"
            client.newWebSocket(Request.Builder().url(url).build(), listener)
        } catch (e: Exception) {
            null
        }
    }

    private suspend fun <T> call(
        path: String,
        body: String? = null,
        put: Boolean = false,
        parse: (String) -> T,
    ): ApiResult<T> = withContext(Dispatchers.IO) {
        try {
            val builder = Request.Builder().url(baseUrl.trimEnd('/') + path)
            if (token.isNotEmpty()) builder.header("Authorization", "Bearer $token")
            when {
                body == null -> builder.get()
                put -> builder.put(body.toRequestBody(jsonMedia))
                else -> builder.post(body.toRequestBody(jsonMedia))
            }

            client.newCall(builder.build()).execute().use { resp ->
                val text = resp.body?.string().orEmpty()
                if (!resp.isSuccessful) {
                    val msg = runCatching {
                        json.decodeFromString(ErrorDetail.serializer(), text).humanMessage()
                    }.getOrNull().orEmpty()
                    return@withContext ApiResult.Err(
                        msg.ifBlank { friendlyHttp(resp.code) },
                        resp.code,
                    )
                }
                ApiResult.Ok(parse(text))
            }
        } catch (e: Exception) {
            android.util.Log.w("AfuConn", "call failed: ${e.javaClass.simpleName}: ${e.message}")
            ApiResult.Err(e.message ?: "网络错误")
        }
    }

    private fun friendlyHttp(code: Int): String = when (code) {
        401 -> "未配对或配对已失效，请重新配对"
        409 -> "已有任务在运行"
        404 -> "接口不存在（服务端版本不匹配？）"
        else -> "HTTP $code"
    }

    suspend fun health(): ApiResult<Health> =
        call("/api/health") { json.decodeFromString(Health.serializer(), it) }

    suspend fun pair(code: String): ApiResult<PairResponse> {
        val body = json.encodeToString(PairRequest.serializer(), PairRequest(code))
        return call("/api/pair", body) { json.decodeFromString(PairResponse.serializer(), it) }
    }

    suspend fun games(): ApiResult<GamesResponse> =
        call("/api/games") { json.decodeFromString(GamesResponse.serializer(), it) }

    suspend fun current(): ApiResult<CurrentTask> =
        call("/api/tasks/current") { json.decodeFromString(CurrentTask.serializer(), it) }

    /**
     * 启动某个游戏的任务。
     *
     * `tasks` 为空 = 按引擎当前配置全跑；非空 = 只跑这些子任务（并按该顺序）。
     * 这样游戏页的「开始」和编排页选的子任务是同一套语义。
     */
    suspend fun run(game: String, tasks: List<String> = emptyList()): ApiResult<TaskRun> {
        val body = buildString {
            append("{\"tasks\":[")
            tasks.forEachIndexed { i, t ->
                if (i > 0) append(",")
                append("\"").append(t.replace("\\", "\\\\").replace("\"", "\\\"")).append("\"")
            }
            append("]}")
        }
        return call("/api/tasks/$game/run", body) {
            json.decodeFromString(TaskRun.serializer(), it)
        }
    }

    suspend fun stop(): ApiResult<TaskRun> =
        call("/api/tasks/stop", "{}") { json.decodeFromString(TaskRun.serializer(), it) }

    suspend fun cleanup(game: String): ApiResult<CleanupResult> =
        call("/api/games/$game/cleanup", "{}") { json.decodeFromString(CleanupResult.serializer(), it) }

    // ---------- 编排 ----------
    suspend fun chain(): ApiResult<ChainResponse> =
        call("/api/chain") { json.decodeFromString(ChainResponse.serializer(), it) }

    suspend fun saveChain(chain: Chain): ApiResult<Unit> {
        val body = json.encodeToString(Chain.serializer(), chain)
        return call("/api/chain", body, put = true) { }
    }

    suspend fun engineTasks(game: String): ApiResult<Capability> =
        call("/api/engines/$game/tasks") { json.decodeFromString(Capability.serializer(), it) }

    suspend fun runChain(): ApiResult<ChainRun> =
        call("/api/chain/run", "{}") { json.decodeFromString(ChainRun.serializer(), it) }

    suspend fun stopChain(): ApiResult<ChainRun> =
        call("/api/chain/stop", "{}") { json.decodeFromString(ChainRun.serializer(), it) }

    suspend fun chainStatus(): ApiResult<ChainStatus> =
        call("/api/chain/status") { json.decodeFromString(ChainStatus.serializer(), it) }

    // ---------------- 定时执行 ----------------
    suspend fun schedule(): ApiResult<ScheduleInfo> =
        call("/api/schedule") { json.decodeFromString(ScheduleInfo.serializer(), it) }

    suspend fun saveSchedule(config: ScheduleConfig): ApiResult<ScheduleInfo> {
        val body = json.encodeToString(ScheduleConfig.serializer(), config)
        return call("/api/schedule", body, put = true) {
            json.decodeFromString(ScheduleInfo.serializer(), it)
        }
    }

    /** 强制停止：停链 → 停任务 → 关掉所有游戏与工具。 */
    suspend fun stopSchedule(): ApiResult<ScheduleStopResult> =
        call("/api/schedule/stop", "{}") {
            json.decodeFromString(ScheduleStopResult.serializer(), it)
        }

    /** 关闭所有游戏与自动化工具（编排页用）。 */
    suspend fun cleanupAll(): ApiResult<CleanupAllResult> =
        call("/api/cleanup/all", "{}") { json.decodeFromString(CleanupAllResult.serializer(), it) }

    suspend fun rediscover(): ApiResult<GamesResponse> =
        call("/api/discover", "{}") { json.decodeFromString(GamesResponse.serializer(), it) }

    /**
     * 取一张游戏画面。失败时服务端会给顶层 {"error","message"}，这里直接拿 message，
     * 不套用 friendlyHttp（409 在画面场景里是「窗口被最小化/画面全黑」，不是「已有任务」）。
     */
    suspend fun fetchScreen(game: String, quality: Int = 70): ApiResult<ScreenFrame> =
        withContext(Dispatchers.IO) {
            try {
                val builder = Request.Builder()
                    .url(baseUrl.trimEnd('/') + "/api/screen/$game?quality=$quality")
                    .header("Accept", "image/jpeg")
                if (token.isNotEmpty()) builder.header("Authorization", "Bearer $token")

                screenClient.newCall(builder.build()).execute().use { resp ->
                    if (!resp.isSuccessful) {
                        val text = resp.body?.string().orEmpty()
                        val msg = runCatching {
                            json.decodeFromString(ErrorDetail.serializer(), text).humanMessage()
                        }.getOrNull().orEmpty()
                        return@withContext ApiResult.Err(
                            msg.ifBlank { "画面请求失败（HTTP ${resp.code}）" },
                            resp.code,
                        )
                    }
                    val bytes = resp.body?.bytes()
                    if (bytes == null || bytes.isEmpty()) {
                        return@withContext ApiResult.Err("服务端返回了空画面")
                    }
                    ApiResult.Ok(
                        ScreenFrame(
                            bytes = bytes,
                            capturedAt = resp.header("X-Captured-At").orEmpty(),
                            width = resp.header("X-Image-Width")?.toIntOrNull() ?: 0,
                            height = resp.header("X-Image-Height")?.toIntOrNull() ?: 0,
                            captureMs = resp.header("X-Capture-Ms")?.toDoubleOrNull() ?: 0.0,
                        )
                    )
                }
            } catch (e: Exception) {
                ApiResult.Err(e.message ?: "网络错误")
            }
        }
}

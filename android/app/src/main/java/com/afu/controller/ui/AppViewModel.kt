package com.afu.controller.ui

import android.graphics.BitmapFactory
import android.util.Log
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.afu.controller.data.ApiClient
import com.afu.controller.data.ScheduleConfig
import com.afu.controller.data.ScheduleInfo
import com.afu.controller.data.ApiResult
import com.afu.controller.data.Chain
import com.afu.controller.data.Capability
import com.afu.controller.data.ChainRun
import com.afu.controller.data.DEFAULT_PORT
import com.afu.controller.data.GameInfo
import com.afu.controller.data.Health
import com.afu.controller.data.SettingsRepo
import com.afu.controller.data.TaskRun
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** 一个游戏的画面区状态。只保留最新一帧，旧帧随引用替换被回收。 */
data class GameScreen(
    val image: ImageBitmap? = null,
    val capturedAt: String = "",
    val error: String = "",
    val loading: Boolean = false,
    val captureMs: Double = 0.0,
)

/**
 * 整体界面状态。
 *
 * **性能约定**：这是一个 `data class`，界面层用 `equals` 判断「有没有变化」。
 * 轮询拿到的数据与当前相等时**不发射新状态**，否则每 3~5 秒整棵界面树都会重组一次
 * —— 那正是之前「手机很卡」的主因。
 *
 * 画面帧**不在**这里：它单独一个 `screen` flow，来一张新图只让画面区重组，
 * 不会连带任务卡与主操作栏一起重组。
 */
data class UiState(
    val address: String = "",
    val connected: Boolean = false,
    val paired: Boolean = false,
    val health: Health? = null,
    val games: Map<String, GameInfo> = emptyMap(),
    val current: TaskRun? = null,
    val history: List<TaskRun> = emptyList(),
    val busyGame: String = "",
    val toast: String = "",
    /** 正在尝试连接（按钮显示转圈，避免用户反复点） */
    val connecting: Boolean = false,
    /**
     * 最近一次连接失败的原因，常驻显示在输入框下方。
     *
     * 为什么不用 toast：toast 会自己消失，而且容易被输入法挡住；
     * 连接失败是用户最需要反复看的信息，必须留在页面上。
     */
    val connectError: String = "",
    /** 正在配对（按钮转圈） */
    val pairing: Boolean = false,
    /** 配对失败原因，常驻显示 */
    val pairError: String = "",
    // ---------- 编排 ----------
    /** 任务链（手机上编辑的就是它） */
    val chain: Chain = Chain.DEFAULT,
    /** 各引擎的能力清单，按 game 索引 */
    val capabilities: Map<String, Capability> = emptyMap(),
    /** 链执行状态（服务端返回的最近一次） */
    val chainRun: ChainRun? = null,
    /** 正在保存 / 加载链 */
    val chainBusy: Boolean = false,
    // ---------- 定时 ----------
    /** 电脑端的定时配置与状态 */
    val schedule: ScheduleInfo = ScheduleInfo(),
    /** 正在保存定时配置 */
    val scheduleBusy: Boolean = false,
)

class AppViewModel(internal val repo: SettingsRepo) : ViewModel() {

    internal val json = kotlinx.serialization.json.Json { ignoreUnknownKeys = true }

    internal val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()

    /**
     * 画面单独一条流：三个游戏共用同一张全屏截图，所以只有一份。
     * 放在 UiState 里会让「来一张新图」= 「整页重组」，这是刻意的分离。
     */
    internal val _screen = MutableStateFlow(GameScreen())
    val screen: StateFlow<GameScreen> = _screen.asStateFlow()

    internal var api: ApiClient? = null
    internal var pollJob: Job? = null
    internal var retryJob: Job? = null
    internal var screenJob: Job? = null
    internal var loadingTimeout: Job? = null

    /** 当前停留的游戏页；为空表示不在任何游戏页（进后台/切页时保留，用于恢复） */
    internal var screenGame: String = ""

    private val GAME_ORDER = listOf("arknights", "genshin", "starrail")
    val gameOrder: List<String> get() = GAME_ORDER

    internal companion object {
        const val TAG = "AfuViewModel"

        /**
         * 画面刷新间隔：出门用公网隧道时网络慢，低频抓图更顺（20 秒一张）。
         * 用户要的是「能看到进度」，不追求实时；随时可以手动点「刷新一张」。
         */
        const val SCREEN_INTERVAL_MS = 20_000L

        /** 有任务时的状态轮询间隔 */
        const val TASK_POLL_MS = 3000L

        /** 有 WebSocket 推送时的兜底轮询间隔：只用来探活，不必频繁拉全量 */
        const val WS_POLL_MS = 15_000L

        /** 空闲时探活间隔：电脑端关掉后，最多这么久就会显示「已断开」 */
        const val IDLE_POLL_MS = 5000L
    }

    init {
        viewModelScope.launch {
            val (address, token) = repo.load()
            _state.value = _state.value.copy(address = address, paired = token.isNotEmpty())
            if (address.isNotBlank()) {
                api = ApiClient(address, token)
                tryConnect(silent = true)
            }
            startAutoRetry()
        }
    }


    // ---------- 拆分出去的两组逻辑（保留同名转发，调用点不变）----------
    private val conn by lazy { ConnectionController(this) }
    private val chainCtl by lazy { ChainController(this) }

    fun setAddress(value: String) = conn.setAddress(value)
    fun connect() = conn.connect()
    fun pair(code: String) = conn.pair(code)
    private fun tryConnect(silent: Boolean) = conn.tryConnect(silent)
    internal fun startAutoRetry() = conn.startAutoRetry()
    internal fun startPolling() = conn.startPolling()
    internal fun normalize(input: String) = conn.normalize(input)

    fun refreshChain() = chainCtl.refreshChain()
    fun refreshCapabilities(force: Boolean = false) = chainCtl.refreshCapabilities(force)
    fun refreshChainStatus() = chainCtl.refreshChainStatus()
    fun saveChain(chain: Chain, onDone: (Boolean) -> Unit = {}) =
        chainCtl.saveChain(chain, onDone)
    fun runChain() = chainCtl.runChain()
    fun stopChain() = chainCtl.stopChain()

    fun refreshSchedule() = chainCtl.refreshSchedule()
    fun saveSchedule(config: ScheduleConfig, onDone: (Boolean) -> Unit = {}) =
        chainCtl.saveSchedule(config, onDone)
    fun stopScheduleNow(onDone: (String) -> Unit = {}) = chainCtl.stopScheduleNow(onDone)
    internal suspend fun flushPendingChain() = chainCtl.flushPendingChain()


    private val screenCtl by lazy { ScreenController(this) }

    fun enterGameScreen(game: String) = screenCtl.enterGameScreen(game)
    fun leaveGameScreen(game: String) = screenCtl.leaveGameScreen(game)
    fun pauseScreen() = screenCtl.pauseScreen()
    fun resumeScreen() = screenCtl.resumeScreen()
    fun refreshScreenOnce(game: String) = screenCtl.refreshScreenOnce(game)
    internal fun restartScreenLoop() = screenCtl.restartScreenLoop()
    private fun finishScreenLoop(game: String) = screenCtl.finishScreenLoop(game)

    // ---------- 内部工具 ----------
    /**
     * 只在内容真的变了时才发射新状态。
     *
     * `StateFlow` 自身用 `equals` 去重，但调用方常常已经 `copy()` 出新实例再赋值；
     * 这里先算出来再比较，可以把「构造新实例」这一步也省掉。
     */
    internal inline fun update(block: (UiState) -> UiState) {
        val before = _state.value
        val after = block(before)
        if (after != before) _state.value = after
    }

    internal inline fun updateScreen(block: (GameScreen) -> GameScreen) {
        val before = _screen.value
        val after = block(before)
        if (after != before) _screen.value = after
    }

    // ---------- 连接 ----------


    // ---------- 数据 ----------
    fun refreshAll() {
        val client = api ?: return
        viewModelScope.launch {
            when (val g = client.games()) {
                is ApiResult.Ok -> {
                    val wasDisconnected = !_state.value.connected
                    update { it.copy(games = g.data.games, connected = true) }
                    // 断线恢复后把当前页的画面刷新接回去
                    if (wasDisconnected) restartScreenLoop()
                }
                is ApiResult.Err -> {
                    if (g.code == 401) {
                        // 电脑端不认这个 token 了（比如重装过 exe、换过数据目录）。
                        // 不把「缺少或无效的 token」这种技术字眼丢给用户，
                        // 直接说明情况并引导去重新配对。
                        update {
                            it.copy(
                                paired = false,
                                connectError = "电脑端需要重新配对一次（电脑重装或换过数据目录后会这样）。\n" +
                                    "请重新填一次配对码即可，地址不用改。",
                            )
                        }
                    } else {
                        markDisconnected()
                    }
                }
            }
            when (val c = client.current()) {
                is ApiResult.Ok -> {
                    val before = _state.value.current
                    update { it.copy(current = c.data.current, history = c.data.history) }
                    // 当前停留页对应的任务状态变化：开始 → 跟随刷新；结束 → 停刷新
                    val game = screenGame
                    if (game.isNotBlank()) {
                        val wasMine = before?.game == game
                        val isMine = c.data.current?.game == game
                        if (wasMine && !isMine) {
                            finishScreenLoop(game)
                        } else if (isMine && before?.runId != c.data.current?.runId) {
                            restartScreenLoop()
                        }
                    }
                }
                is ApiResult.Err -> if (c.code != 401) markDisconnected()
            }
        }
    }

    /** 任务结束：立刻停掉刷新（不依赖循环自己下一轮发现）。 */
    /** 电脑端不可达：立刻反映成「已断开」，交给自动重试去恢复。 */
    internal fun markDisconnected() {
        if (!_state.value.connected) return
        // 连不上时不能继续展示旧的「组件齐全」，否则界面自相矛盾
        update { it.copy(connected = false, games = emptyMap()) }
    }

    /** 关闭所有游戏与工具（编排页的「关闭游戏和工具」）。 */
    fun cleanupAll() {
        val client = api ?: run { toast("请先连接电脑"); return }
        viewModelScope.launch {
            when (val r = client.cleanupAll()) {
                is ApiResult.Ok -> toast(r.data.message.ifBlank { "已关闭" })
                is ApiResult.Err -> toast(r.message)
            }
            refreshAll()
        }
    }

    fun rediscover() {
        val client = api ?: return
        viewModelScope.launch {
            when (val g = client.rediscover()) {
                is ApiResult.Ok -> {
                    update { it.copy(games = g.data.games) }
                    toast("已重新探测")
                }
                is ApiResult.Err -> toast("探测失败：${g.message}")
            }
        }
    }

    // ---------- 任务 ----------
    fun start(game: String) {
        val client = api ?: run { toast("请先连接电脑"); return }
        if (_state.value.current != null) {
            toast("已有任务在运行")
            return
        }
        // 游戏页的「开始」也用编排里给这个游戏选的子任务。
        // 用户可能在这个游戏上排了好几次（比如「原神一条龙 → 收尾」），
        // 把每次选的子任务合并去重后一起传下去。
        val picked = _state.value.chain.steps
            .filter { it.game == game && it.enabled }
            .flatMap { it.tasks }
            .distinct()

        update { it.copy(busyGame = game) }
        viewModelScope.launch {
            when (val r = client.run(game, picked)) {
                is ApiResult.Ok -> {
                    update { it.copy(current = r.data, busyGame = "") }
                    toast("已启动：${r.data.title}")
                    if (screenGame == game) restartScreenLoop()
                }
                is ApiResult.Err -> {
                    update { it.copy(busyGame = "") }
                    toast(r.message)
                }
            }
            refreshAll()
        }
    }

    fun stop() {
        val client = api ?: return
        viewModelScope.launch {
            when (val r = client.stop()) {
                is ApiResult.Ok -> {
                    toast("已停止")
                    val game = screenGame
                    update { it.copy(current = null) }
                    if (game.isNotBlank()) finishScreenLoop(game)
                }
                is ApiResult.Err -> toast(r.message)
            }
            refreshAll()
        }
    }

    fun cleanup(game: String) {
        val client = api ?: run { toast("请先连接电脑"); return }
        viewModelScope.launch {
            when (val r = client.cleanup(game)) {
                is ApiResult.Ok -> toast(r.data.message.ifBlank { "已释放" })
                is ApiResult.Err -> toast("释放失败：${r.message}")
            }
            refreshAll()
        }
    }

    /** 断开连接（保留地址与 token，方便下次直接连）。 */
    fun disconnect() {
        conn.closeWs()
        pollJob?.cancel()
        screenJob?.cancel()
        screenJob = null
        api = null
        update { it.copy(connected = false, current = null) }
        toast("已断开连接")
    }




    /** 弹一条短暂提示。界面层也可以用（例如返回键没地方可回时提醒用户）。 */
    fun toast(msg: String) {
        update { it.copy(toast = msg) }
    }

    fun consumeToast() {
        update { it.copy(toast = "") }
    }


    class Factory(private val repo: SettingsRepo) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T =
            AppViewModel(repo) as T
    }
}
package com.afu.controller.ui

import android.graphics.BitmapFactory
import android.util.Log
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.afu.controller.data.ApiClient
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


/**
 * 连接相关：填写地址、建立连接、配对、自动重试与轮询。
 *
 * 从 AppViewModel 拆出来是因为它占了这个类一半的行数，而它与界面状态之间
 * 只通过 `_state` / `api` 几个入口交互。AppViewModel 保留同名方法转发，
 * 界面层的调用点不变。
 */
internal class ConnectionController(private val vm: AppViewModel) {

    fun setAddress(value: String) {
        vm.update { it.copy(address = value) }
    }

    fun connect() {
        val address = normalize(vm._state.value.address)
        if (address.isBlank()) {
            vm.toast("请先填写电脑地址")
            return
        }
        vm.update { it.copy(address = address) }
        tryConnect(silent = false)
    }

    /** 尝试建立连接；silent=true 时失败不弹提示（用于自动重试）。 */
    internal fun tryConnect(silent: Boolean) {
        val address = normalize(vm._state.value.address)
        if (address.isBlank()) return
        vm.viewModelScope.launch {
            if (!silent) {
                vm.update { it.copy(connecting = true, connectError = "") }
            }
            vm.repo.saveAddress(address)
            val token = vm.repo.load().second
            val client = ApiClient(address, token)
            when (val r = client.health()) {
                is ApiResult.Ok -> {
                    vm.api = client
                    vm.update {
                        it.copy(
                            address = address,
                            connected = true,
                            health = r.data,
                            connecting = false,
                            connectError = "",
                        )
                    }
                    if (!silent) vm.toast("已连接电脑（v${r.data.version}）")
                    if (token.isNotEmpty()) {
                        vm.flushPendingChain()   // 先把断网期间的改动补发给电脑
                        vm.refreshAll()
                        // 游戏页的「选子任务」要能力清单，连上就预取一次，
                        // 否则第一次点开面板会显示「正在读取… 没有可选项」。
                        vm.refreshChain()
                        vm.refreshCapabilities(force = true)
                        startPolling()
                        vm.restartScreenLoop()
                        vm.api?.let { openWs(it) }
                    }
                }
                is ApiResult.Err -> {
                    vm.update {
                        it.copy(
                            connected = false,
                            connecting = false,
                            connectError = explainConnectFailure(address, r.message),
                        )
                    }
                }
            }
        }
    }

    /**
     * 把底层的网络错误翻译成用户能照着做的话。
     *
     * 只说「连接失败：timeout」没有意义 —— 用户需要知道
     * 「是地址填错了、还是电脑没开、还是你在外面需要 Tailscale」。
     */
    internal fun explainConnectFailure(address: String, raw: String): String {
        // 注意：不能直接 substringBefore(':')，https:// 里本身就有冒号，
        // 那样会把主机名截成 "https"。先剥协议，再按最后一个冒号取端口。
        val afterScheme = address.substringAfter("://", address)
        val hostPart = afterScheme.substringBefore('/')
        val host = if (hostPart.contains(':')) hostPart.substringBeforeLast(':') else hostPart

        val inHomeLan = host.startsWith("192.168.") ||
            host.startsWith("10.") ||
            Regex("""^172\.(1[6-9]|2\d|3[01])\.""").containsMatchIn(host)
        val isTailscaleIp = host.startsWith("100.")
        val isPublicHttps = address.startsWith("https://")

        return when {
            isPublicHttps ->
                "连不上 $host。请确认：\n" +
                    "1. 电脑上的「阿福代肝控制器」正在运行\n" +
                    "2. 电脑端 Funnel 还开着（在电脑上执行 tailscale funnel status 查看）\n" +
                    "3. 网址不要带端口号，Funnel 走的是 443\n" +
                    "详情：$raw"

            isTailscaleIp ->
                "连不上 $host。这是 Tailscale 私有地址，需要手机上也为 Tailscale 登录同一账号。\n" +
                    "如果你手机没装 Tailscale，请改用电脑窗口「公网地址」那个 https:// 网址。\n" +
                    "详情：$raw"

            inHomeLan ->
                "连不上 $host。这个像是家里局域网的地址，需要手机和电脑连同一个 WiFi。\n" +
                    "如果你在外面，请改用电脑窗口「公网地址」那个 https:// 开头的网址。"

            else ->
                "连不上 $address。请确认地址没填错、电脑上的「阿福代肝控制器」正在运行。\n详情：$raw"
        }
    }

    fun pair(code: String) {
        val client = vm.api ?: run {
            vm.update { it.copy(pairError = "还没连上电脑，请先点上面的「连接」") }
            return
        }
        if (code.length != 6) {
            vm.update { it.copy(pairError = "配对码是 6 位数字") }
            return
        }
        vm.viewModelScope.launch {
            vm.update { it.copy(pairing = true, pairError = "") }
            when (val r = client.pair(code)) {
                is ApiResult.Ok -> {
                    vm.repo.saveToken(r.data.token)
                    vm.api = ApiClient(vm._state.value.address, r.data.token)
                    vm.update { it.copy(paired = true, pairing = false, pairError = "") }
                    vm.toast("配对成功")
                    vm.refreshAll()
                    startPolling()
                    vm.restartScreenLoop()
                }
                is ApiResult.Err -> {
                    vm.update {
                        it.copy(
                            pairing = false,
                            pairError = when {
                                r.code == 400 ->
                                    "配对码无效或已过期。请在电脑端窗口上重新生成一个，再输入。"
                                r.code == 401 ->
                                    "电脑不认这个连接，请回到上面重新点一次「连接」。"
                                else -> "配对失败：${r.message.ifBlank { "网络异常" }}"
                            },
                        )
                    }
                }
            }
        }
    }

    /** 每 5 秒重试一次，解决「先开 APP、后启动电脑端」连不上的问题。 */
    internal fun startAutoRetry() {
        vm.retryJob?.cancel()
        vm.retryJob = vm.viewModelScope.launch {
            while (true) {
                delay(5000)
                val s = vm._state.value
                if (!s.connected && s.address.isNotBlank()) {
                    tryConnect(silent = true)
                    if (vm._state.value.connected) {
                        vm.refreshAll()
                        startPolling()
                        vm.restartScreenLoop()
                        vm.api?.let { openWs(it) }
                    }
                }
            }
        }
    }

    // ---------- 轮询 ----------

    // ---------- 事件推送（WebSocket）----------
    private var ws: okhttp3.WebSocket? = null
    private var wsConnected = false

    /**
     * 打开推送通道。
     *
     * 服务端只在状态变化时发消息，所以拿到推送就把轮询放宽到 15 秒兜底；
     * 推送断开（或某些代理不支持升级）时自动退回 5 秒轮询，功能不受影响。
     */
    internal fun openWs(client: ApiClient) {
        closeWs()
        ws = client.openEventSocket(object : okhttp3.WebSocketListener() {
            override fun onOpen(webSocket: okhttp3.WebSocket, response: okhttp3.Response) {
                wsConnected = true
            }

            override fun onMessage(webSocket: okhttp3.WebSocket, text: String) {
                handleEvent(text)
            }

            override fun onClosed(webSocket: okhttp3.WebSocket, code: Int, reason: String) {
                wsConnected = false
            }

            override fun onFailure(webSocket: okhttp3.WebSocket, t: Throwable, response: okhttp3.Response?) {
                wsConnected = false
            }
        })
    }

    internal fun closeWs() {
        wsConnected = false
        runCatching { ws?.close(1000, "bye") }
        ws = null
    }

    /** 服务端事件：{"type":"task"|"chain"|"hello", "event":..., "task"/"chain":{...}} */
    private fun handleEvent(text: String) {
        val root = runCatching {
            vm.json.parseToJsonElement(text).jsonObject
        }.getOrNull() ?: return

        when (root["type"]?.jsonPrimitive?.contentOrNull) {
            "task" -> {
                val task = root["task"]?.let {
                    runCatching { vm.json.decodeFromString<TaskRun>(it.toString()) }.getOrNull()
                } ?: return
                val event = root["event"]?.jsonPrimitive?.contentOrNull
                if (event == "finished") {
                    // 结束事件之后要拉一次全量：历史记录和游戏状态都变了
                    vm.update { it.copy(current = null) }
                    vm.refreshAll()
                } else {
                    vm.update { it.copy(current = task) }
                }
            }

            "chain" -> {
                val chain = root["chain"]?.let {
                    runCatching { vm.json.decodeFromString<ChainRun>(it.toString()) }.getOrNull()
                } ?: return
                vm.update { it.copy(chainRun = chain) }
            }
        }
    }

    internal fun startPolling() {
        vm.pollJob?.cancel()
        vm.pollJob = vm.viewModelScope.launch {
            while (true) {
                delay(
                    when {
                        vm._state.value.current != null -> AppViewModel.TASK_POLL_MS
                        wsConnected -> AppViewModel.WS_POLL_MS   // 有推送时只做兜底探活
                        else -> AppViewModel.IDLE_POLL_MS
                    }
                )
                if (vm.api == null) continue
                // 有任务时拉状态；空闲时也要拉：既能探活，也能发现从别处（命令行/另一台手机）启动的任务
                vm.refreshAll()
            }
        }
    }

    internal fun normalize(input: String): String {
        var s = input.trim()
        if (s.isEmpty()) return ""
        if (!s.startsWith("http")) s = "http://$s"

        // https 地址（Tailscale Funnel 那种公网域名）**不能补端口**：
        // 它走 443，补上 :8765 反而连不上。只有 http/裸地址才补默认端口。
        if (s.startsWith("https://")) return s

        val afterScheme = s.substringAfter("://", "")
        val hostPart = afterScheme.substringBefore('/')
        if (!hostPart.contains(":")) {
            s = if (afterScheme.contains('/')) {
                s.replaceFirst(hostPart, "$hostPart:${DEFAULT_PORT}")
            } else {
                "$s:${DEFAULT_PORT}"
            }
        }
        return s
    }
}

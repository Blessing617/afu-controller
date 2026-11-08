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
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext


/**
 * 编排相关：任务链的读取、保存、执行与状态轮询。
 *
 * 与 ConnectionController 同理——单文件超过 300 行后，
 * 把职责独立的整块搬出去比继续堆在一个类里更容易维护。
 */
internal class ChainController(private val vm: AppViewModel) {

    // ---------- 编排 ----------
    /** 拉取任务链与三份能力清单。断网时保持现有状态不动。 */
    fun refreshChain() {
        val client = vm.api ?: return
        vm.viewModelScope.launch {
            vm.update { it.copy(chainBusy = true) }
            when (val r = client.chain()) {
                is ApiResult.Ok -> vm.update { it.copy(chain = r.data.chain) }
                is ApiResult.Err -> if (r.code != 401) vm.toast("读取任务链失败：${r.message}")
            }
            val caps = vm._state.value.capabilities.toMutableMap()
            for (g in vm.gameOrder) {
                when (val c = client.engineTasks(g)) {
                    is ApiResult.Ok -> caps[g] = c.data
                    is ApiResult.Err -> Unit   // 单个引擎失败不影响其他
                }
            }
            vm.update { it.copy(capabilities = caps, chainBusy = false) }
            refreshChainStatus()
        }
    }

    /** 只拉能力清单（游戏页的「选子任务」用；不需要整条链）。 */
    fun refreshCapabilities(force: Boolean = false) {
        val client = vm.api ?: return
        val missing = vm.gameOrder.filter { force || vm._state.value.capabilities[it] == null }
        if (missing.isEmpty()) return
        vm.viewModelScope.launch {
            val caps = vm._state.value.capabilities.toMutableMap()
            for (g in missing) {
                when (val c = client.engineTasks(g)) {
                    is ApiResult.Ok -> caps[g] = c.data
                    is ApiResult.Err -> Unit
                }
            }
            vm.update { it.copy(capabilities = caps) }
        }
    }

    fun refreshChainStatus() {
        val client = vm.api ?: return
        vm.viewModelScope.launch {
            when (val r = client.chainStatus()) {
                is ApiResult.Ok -> vm.update { it.copy(chainRun = r.data.chain) }
                is ApiResult.Err -> Unit
            }
        }
    }

    /** 保存任务链。成功返回 true。 */
    /** 保存任务链。成功返回 true；断网时本地暂存，重连后自动补发。 */
    fun saveChain(chain: Chain, onDone: (Boolean) -> Unit = {}) {
        vm.viewModelScope.launch {
            // 界面立刻反映改动，不管能不能联网：用户先看到自己改的东西
            vm.update { it.copy(chain = chain, chainBusy = true) }

            val client = vm.api
            if (client == null) {
                stashChain(chain)
                vm.update { it.copy(chainBusy = false) }
                vm.toast("未连接电脑，改动已暂存，重连后自动同步")
                onDone(false)
                return@launch
            }

            val ok = when (val r = client.saveChain(chain)) {
                is ApiResult.Ok -> {
                    vm.repo.clearPendingChain()
                    true
                }
                is ApiResult.Err -> {
                    // 断网 / 服务端不可达 / 网关错误：都当作「暂时同步不了」，
                    // 先暂存起来等重连再补发，别让用户的改动白丢。
                    // 只有服务端**明确拒绝改动内容**（400/409）才不暂存、直接报错。
                    val transient = r.code == 0 || r.code >= 500
                    if (transient) {
                        stashChain(chain)
                        vm.toast("网络不稳，改动已暂存，重连后自动同步")
                    } else {
                        vm.toast("保存失败：${r.message}")
                    }
                    false
                }
            }
            vm.update { it.copy(chainBusy = false) }
            onDone(ok)
        }
    }

    /** 把任务链写进本地，等重连后补发。 */
    private suspend fun stashChain(chain: Chain) {
        runCatching {
            vm.repo.savePendingChain(vm.json.encodeToString(Chain.serializer(), chain))
        }
    }

    /** 重连成功后调用：把暂存的任务链补发给电脑端。 */
    internal suspend fun flushPendingChain() {
        val pending = vm.repo.pendingChain()
        if (pending.isBlank()) return
        val client = vm.api ?: return
        val chain = runCatching { vm.json.decodeFromString(Chain.serializer(), pending) }
            .getOrNull() ?: run { vm.repo.clearPendingChain(); return }
        when (client.saveChain(chain)) {
            is ApiResult.Ok -> {
                vm.repo.clearPendingChain()
                vm.update { it.copy(chain = chain) }
                vm.toast("已把离线修改同步到电脑")
            }
            else -> Unit   // 还是不通，留着下次再试
        }
    }

    fun runChain() {
        val client = vm.api ?: run { vm.toast("请先连接电脑"); return }
        vm.viewModelScope.launch {
            when (val r = client.runChain()) {
                is ApiResult.Ok -> {
                    vm.update { it.copy(chainRun = r.data) }
                    vm.toast("开始执行任务链")
                }
                is ApiResult.Err -> vm.toast(r.message)
            }
            refreshChainStatus()
        }
    }

    fun stopChain() {
        val client = vm.api ?: return
        vm.viewModelScope.launch {
            when (val r = client.stopChain()) {
                is ApiResult.Ok -> vm.update { it.copy(chainRun = r.data) }
                is ApiResult.Err -> vm.toast(r.message)
            }
        }
    }

    // ---------------- 定时执行 ----------------
    internal fun refreshSchedule() {
        val client = vm.api ?: return
        vm.viewModelScope.launch {
            when (val r = client.schedule()) {
                is ApiResult.Ok -> vm.update { it.copy(schedule = r.data) }
                // 定时是可选功能：拉不到就保持现状，不打扰用户
                is ApiResult.Err -> if (r.code == 401) vm.markDisconnected()
            }
        }
    }

    internal fun saveSchedule(config: ScheduleConfig, onDone: (Boolean) -> Unit = {}) {
        val client = vm.api ?: run { onDone(false); return }
        vm.update { it.copy(scheduleBusy = true) }
        vm.viewModelScope.launch {
            val ok = when (val r = client.saveSchedule(config)) {
                is ApiResult.Ok -> {
                    vm.update { it.copy(schedule = r.data) }
                    true
                }
                is ApiResult.Err -> {
                    if (r.code == 401) vm.markDisconnected()
                    vm.toast("保存定时失败：${r.message}")
                    false
                }
            }
            vm.update { it.copy(scheduleBusy = false) }
            onDone(ok)
        }
    }

    /** 强制停止：停链 → 停任务 → 关掉所有游戏与工具。 */
    internal fun stopScheduleNow(onDone: (String) -> Unit = {}) {
        val client = vm.api ?: run { onDone("未连接电脑"); return }
        vm.viewModelScope.launch {
            when (val r = client.stopSchedule()) {
                is ApiResult.Ok -> {
                    vm.update { it.copy(current = null, chainRun = null) }
                    vm.refreshAll()
                    onDone(r.data.message)
                }
                is ApiResult.Err -> {
                    if (r.code == 401) vm.markDisconnected()
                    onDone("停止失败：${r.message}")
                }
            }
        }
    }
}

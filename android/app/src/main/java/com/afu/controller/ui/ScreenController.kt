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
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext


/**
 * 画面相关：进/出游戏页、按页请求截图、后台解码与循环刷新。
 *
 * 单独拆出来有两个原因：一是它占了这个类三分之一的行数；
 * 二是「来一张新图只让画面区重组」是明确约定（见 UiState 的注释），
 * 把这条链路的代码放在一起更容易守住它。
 */
internal class ScreenController(private val vm: AppViewModel) {

    internal fun finishScreenLoop(game: String) {
        vm.screenJob?.cancel()
        vm.screenJob = null
        // 旧快照标记由界面层按「有图、但这一页的任务没在跑」推导，见 Screens.kt
    }


    // ---------- 画面 ----------
    /** 进入游戏页：有图就直接用，任务在跑时才开始循环刷新。 */
    fun enterGameScreen(game: String) {
        vm.screenGame = game
        val hasImage = vm._screen.value.image != null
        val running = vm._state.value.current?.game == game
        if (!hasImage || running) restartScreenLoop()
    }

    /** 离开游戏页：停掉刷新。 */
    fun leaveGameScreen(game: String) {
        if (vm.screenGame != game) return
        vm.screenGame = ""
        vm.screenJob?.cancel()
        vm.screenJob = null
    }

    /** APP 进后台：停刷新，但记住当前页，回到前台再继续。 */
    fun pauseScreen() {
        vm.screenJob?.cancel()
        vm.screenJob = null
    }

    /** APP 回到前台：恢复当前页的刷新。 */
    fun resumeScreen() {
        restartScreenLoop()
    }

    /** 手动刷新一张：不启动循环，未运行任务时也能看一眼。 */
    fun refreshScreenOnce(game: String) {
        requestScreen(game)
    }

    internal fun restartScreenLoop() {
        vm.screenJob?.cancel()
        vm.screenJob = null
        val game = vm.screenGame
        if (game.isBlank()) return
        vm.screenJob = vm.viewModelScope.launch {
            if (vm.api == null) {
                setScreenError(game, "未连接电脑")
                return@launch
            }
            // 进入页面先出图，不等第一个间隔
            requestScreen(game)
            while (isActive) {
                if (vm._state.value.current?.game != game) break
                delay(AppViewModel.SCREEN_INTERVAL_MS)
                if (!isActive) break
                if (vm._state.value.current?.game != game) break
                requestScreen(game)
            }
        }
    }

    internal fun requestScreen(game: String) {
        val client = vm.api
        if (client == null) {
            setScreenError(game, "未连接电脑")
            return
        }
        if (vm._screen.value.loading) return

        vm.updateScreen { it.copy(loading = true) }
        // 传输慢时别一直转圈：1.5 秒后自动停（图到了会覆盖，图没到也不至于转很久）
        vm.loadingTimeout?.cancel()
        vm.loadingTimeout = vm.viewModelScope.launch {
            delay(1500)
            if (vm._screen.value.loading) vm.updateScreen { it.copy(loading = false) }
        }
        vm.viewModelScope.launch {
            when (val r = client.fetchScreen(game)) {
                is ApiResult.Ok -> {
                    // 解码放在 IO 线程：Main 线程解码一张 960 宽的 JPEG 会掉帧。
                    // 用 inSampleSize 按需降采样，位图内存只有原图三分之一左右。
                    val bitmap = withContext(Dispatchers.IO) {
                        decodeScaled(r.data.bytes, targetWidth = 960)?.asImageBitmap()
                    }
                    if (bitmap == null) {
                        setScreenError(game, "画面解码失败")
                    } else {
                        vm.loadingTimeout?.cancel()
                        // 只保留这一张：旧的 ImageBitmap 失去引用后由 GC 回收
                        vm.updateScreen {
                            it.copy(
                                image = bitmap,
                                capturedAt = r.data.capturedAt,
                                error = "",
                                loading = false,
                                captureMs = r.data.captureMs,
                            )
                        }
                    }
                }
                is ApiResult.Err -> {
                    if (r.code == 0) vm.markDisconnected()
                    setScreenError(game, r.message)
                }
            }
        }
    }

    /** 失败只显示原因，不清掉上一张成功的图（用户还能看到卡在哪一步）。 */
    internal fun setScreenError(game: String, message: String) {
        vm.loadingTimeout?.cancel()
        vm.updateScreen { it.copy(error = message, loading = false) }
    }

    internal fun decodeScaled(bytes: ByteArray, targetWidth: Int): android.graphics.Bitmap? {
        return try {
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
            var sample = 1
            if (bounds.outWidth > targetWidth * 2) sample = 2
            if (bounds.outWidth > targetWidth * 4) sample = 4
            val opts = BitmapFactory.Options().apply {
                inSampleSize = sample
                inPreferredConfig = android.graphics.Bitmap.Config.RGB_565
            }
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, opts)
        } catch (e: OutOfMemoryError) {
            Log.w(AppViewModel.TAG, "画面过大，解码失败", e)
            null
        } catch (e: Exception) {
            Log.w(AppViewModel.TAG, "画面解码失败", e)
            null
        }
    }
}

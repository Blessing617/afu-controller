package com.afu.controller.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.rounded.ChevronRight
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.ripple
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.launch
import com.afu.controller.R
import com.afu.controller.data.ChainStep
import com.afu.controller.data.GameInfo
import com.afu.controller.data.TaskRun


// ---- 主界面与游戏页骨架 ----

internal val GAME_LABELS = mapOf(
    "arknights" to "明日方舟",
    "genshin" to "原神",
    "starrail" to "星穹铁道",
)
internal val GAME_TITLES = mapOf(
    "arknights" to "一键长草",
    "genshin" to "一条龙",
    "starrail" to "日常",
)

/**
 * 每个游戏的图标资源。
 *
 * 用的是**官方游戏图标**（用户自己电脑上已安装的游戏里提取的图），辨识度最高。
 * 项目自带的原创矢量图形（ic_game_*）保留作兜底。
 */
internal val GAME_ICONS = mapOf(
    "arknights" to R.drawable.game_arknights,
    "genshin" to R.drawable.game_genshin,
    "starrail" to R.drawable.game_starrail,
)

internal val GAMES = listOf("arknights", "genshin", "starrail")

/**
 * 主界面。
 *
 * 结构（见 .spec/specs/mobile-ux 的「主界面信息层级」）：
 *
 *   Scaffold
 *    ├ topBar        顶部状态条（连接状态 + 设置图标）   ← 固定，不随游戏页重建
 *    ├ 内容区        游戏相关的内容（状态行、次要按钮）   ← 只随 tab 变
 *    ├ 画面卡         画面区                              ← 固定，切页不闪
 *    ├ 主操作栏       开始 / 停止                          ← 固定
 *    └ bottomBar     三个游戏
 *
 * 之所以把画面卡与主操作栏提到「固定层」：三个游戏共用同一张全屏截图，
 * 切 tab 时重建它们只会带来「刷新一下」的观感，没有任何信息增量。
 */
@Composable
fun MainScreen(vm: AppViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    var tab by remember { mutableIntStateOf(0) }
    var direction by remember { mutableIntStateOf(1) }
    var showSettings by remember { mutableStateOf(false) }
    var showConnect by remember { mutableStateOf(false) }
    var showChain by remember { mutableStateOf(false) }
    // 用户主动把「未配对自动弹出的连接页」关掉后，别再弹回来。
    // 否则他每次关掉、只要状态刷新一次就又冒出来，等于还是出不去。
    var skipAutoConnect by remember { mutableStateOf(false) }
    // 从游戏页快速改「这个游戏要跑哪些子任务」。非空时弹出面板。
    var quickEditGame by remember { mutableStateOf("") }

    // 打开子任务面板时，如果这个游戏的能力清单还没拉过，立刻拉一次
    LaunchedEffect(quickEditGame) {
        if (quickEditGame.isNotBlank() && state.capabilities[quickEditGame] == null) {
            vm.refreshCapabilities()
        }
    }
    val snackbar = remember { SnackbarHostState() }

    LaunchedEffect(state.toast) {
        if (state.toast.isNotEmpty()) {
            snackbar.showSnackbar(state.toast)
            vm.consumeToast()
        }
    }

    // 配对成功后自动关掉连接页。
    //
    // 「连上了却退不出连接页」的根因：配对成功时 state.paired 变 true，
    // 但 showConnect 没人置回 false，于是连接页一直盖在上面。
    LaunchedEffect(state.paired) {
        if (state.paired) showConnect = false
    }

    // 返回处理（越靠前的层级越先关）：
    //   连接设置 → 编排 → 设置 → 主界面
    //
    // **连不上也必须能回主界面。** 早先这里强制「未配对就锁在连接页」，
    // 结果电脑没开机 / 网络不对的时候用户被关在里面出不去 —— 这是设计错误：
    // 连接页只是主界面之上的一层，任何时候都该能关掉。断线本身有绿色/红色
    // 状态条和「重新连接」按钮提示，不需要靠锁死页面来强调。
    // 连接页有两条显示路径：手动打开（showConnect）与「还没配对时自动弹出」。
    // 返回拦截必须同时认这两条，否则首次使用（未配对）时返回手势会直接退出 APP
    // —— 这正是用户反馈的「从连接页滑动边缘退出变成了关掉 APP」。
    val connectVisible = showConnect || (!state.paired && !skipAutoConnect)
    val blockBack = connectVisible || showChain || showSettings
    BackHandler(enabled = blockBack) {
        when {
            connectVisible -> {
                showConnect = false
                skipAutoConnect = true
            }
            showChain -> showChain = false
            showSettings -> showSettings = false
        }
    }

    Surface(color = MaterialTheme.colorScheme.background) {
        Scaffold(snackbarHost = { SnackbarHost(snackbar) }) { pad ->
            Box(Modifier.padding(pad).fillMaxSize()) {
                // 主界面永远渲染。没配对时它顶上会显示「未连接」，
                // 但至少用户能看、能切页、能进设置 —— 不会被锁死。
                // 编排页打开时**不再渲染游戏页**。
                //
                // 之前是用 SlideUpScreen 盖在上面，但游戏页的主操作栏（开始/停止）
                // 和编排页自己的操作栏在同一个位置，看起来就是「两个停止键」，
                // 而且上面那个属于游戏页、点了没反应。
                // 直接二选一渲染，从根上避免叠层与误触。
                // 编排不再单独弹一页：它是 GameShell 里的第 4 个标签，
                // 和三个游戏共用顶栏（已连接 + 设置）与底部四栏，
                // 中间那块同样是「上面画面、下面内容」。
                GameShell(
                    vm = vm,
                    state = state,
                    games = GAMES,
                    tab = tab,
                    direction = direction,
                    onSelectTab = { index ->
                        if (index != tab) {
                            direction = if (index > tab) 1 else -1
                            tab = index
                        }
                        // 点游戏标签时退出编排视图
                        if (showChain) showChain = false
                    },
                    onOpenSettings = { showSettings = true },
                    onOpenChain = { showChain = !showChain },
                    onQuickEditTasks = { g -> quickEditGame = g },
                    showChainPage = showChain,
                    onCloseChain = { showChain = false },
                )

                // 设置（整屏从底部滑入）
                SlideUpScreen(open = showSettings) {
                    SettingsScreen(
                        vm = vm,
                        onBack = { showSettings = false },
                        onOpenConnect = { showConnect = true },
                        onOpenChain = { showChain = true },
                    )
                }
                // （子任务快捷编辑面板在 Surface 之后统一挂载，见函数末尾）

                // 连接设置：手动打开，或首次使用（还没配对）时自动弹出。
                // 注意这里只是「显示条件」，用户随时可以关掉它回到主界面。
                SlideUpScreen(open = connectVisible) {
                    ConnectScreen(
                        vm = vm,
                        modifier = Modifier.fillMaxSize(),
                        canGoBack = true,
                        onBack = { showConnect = false; skipAutoConnect = true },
                    )
                }
            }
        }
    }

    // ---------- 游戏页的「选子任务」快捷面板 ----------
    // 和编排页共用同一份数据（state.chain），改完立刻保存到电脑端。
    if (quickEditGame.isNotBlank()) {
        val g = quickEditGame
        // 该游戏在链里所有启用步骤的子任务合并（同一游戏可能排了多次）
        val currentTasks = state.chain.steps
            .filter { it.game == g && it.enabled }
            .flatMap { it.tasks }
            .distinct()
        TaskPickerSheet(
            game = g,
            capability = state.capabilities[g],
            selected = currentTasks,
            onConfirm = { picked ->
                quickEditGame = ""
                // 把选择写回该游戏的第一条启用步骤；没有就新建一条
                val steps = state.chain.steps.toMutableList()
                val idx = steps.indexOfFirst { it.game == g && it.enabled }
                if (idx >= 0) {
                    steps[idx] = steps[idx].copy(tasks = picked)
                } else {
                    steps.add(ChainStep(game = g, tasks = picked))
                }
                vm.saveChain(state.chain.copy(steps = steps))
            },
            onDismiss = { quickEditGame = "" },
        )
    }
}

/**
 * 主界面骨架：顶部状态条 + 随标签变化的内容 + 固定的画面卡与主操作栏。
 */

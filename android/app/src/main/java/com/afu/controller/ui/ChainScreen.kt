package com.afu.controller.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.ripple
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.afu.controller.data.Chain
import com.afu.controller.data.ChainRun
import com.afu.controller.data.ChainStep
import com.afu.controller.data.ChainStepResult
import com.afu.controller.data.Capability
import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.zIndex
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.ui.graphics.graphicsLayer
import kotlin.math.roundToInt


// ---- 编排主页面 ----

internal val GAME_NAMES = mapOf(
    "arknights" to "明日方舟",
    "genshin" to "原神",
    "starrail" to "星穹铁道",
)
internal val GAME_COLORS = mapOf(
    "arknights" to Color(0xFF4A9E8F),
    "genshin" to Color(0xFFE0A030),
    "starrail" to Color(0xFF7B5CFF),
)

/**
 * 编排页：编辑任务链 + 一键跑完整条链。
 *
 * 布局：
 *   顶部：返回 + 标题 + 刷新
 *   中部：步骤列表（可上移/下移/删除/开关/点进选子任务）
 *   底部：策略切换 + 「一键跑完整条链」
 *
 * 运行中整页转成只读，底部换成进度 + 停止按钮。
 */
@Composable
fun ChainScreen(
    vm: AppViewModel,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val state by vm.state.collectAsStateWithLifecycle()
    val chainRun = state.chainRun
    val running = chainRun?.state == "running"

    // 进页面就拉一次：链 + 能力清单 + 当前状态
    LaunchedEffect(Unit) { vm.refreshChain() }

    // 运行中每 2 秒刷新一次链状态
    LaunchedEffect(running) {
        while (running) {
            kotlinx.coroutines.delay(2000)
            vm.refreshChainStatus()
        }
    }

    var editingIndex by remember { mutableStateOf(-1) }

    // 编排页自己的返回处理：
    //   有对话框 → 先关对话框（不要直接退页）
    //   没对话框 → 交给外层的 BackHandler 退到设置页
    // 不写这一段的话，对话框弹出时返回键会被 Dialog 的窗口吞掉，
    // 外层 BackHandler 收不到 → 用户会感觉「卡在编排页出不去」。
    androidx.activity.compose.BackHandler(enabled = editingIndex != -1) {
        editingIndex = -1
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .then(modifier),
    ) {
        // ---------- 顶栏 ----------
        Row(
            Modifier
                .fillMaxWidth()
                .padding(start = 4.dp, end = 8.dp, top = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
            }
            Text(
                "编排",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
            )
            Spacer(Modifier.width(8.dp))
            if (running) {
                Text(
                    "执行中",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            Spacer(Modifier.weight(1f))
            IconButton(onClick = { vm.refreshChain() }, enabled = !state.chainBusy) {
                Icon(Icons.Default.Refresh, contentDescription = "刷新")
            }
        }

        // ---------- 画面（始终显示，和游戏页保持一致） ----------
        //
        // 结构对齐游戏页：顶部状态 → 画面卡 → 内容 → 底部操作。
        // 之前只在运行时才显示画面，平时是纯列表，和旁边几个页面看起来不像一家人。
        // 画面跟「当前正在跑的游戏」；没在跑时跟随列表里选中的第一个启用步骤。
        val focusGame = (if (running) {
            chainRun?.steps?.getOrNull(chainRun.currentIndex)?.game
        } else null) ?: state.chain.steps.firstOrNull { it.enabled }?.game.orEmpty()

        if (focusGame.isNotBlank()) {
            val screen by vm.screen.collectAsStateWithLifecycle()
            LaunchedEffect(focusGame, state.connected) {
                if (state.connected) vm.enterGameScreen(focusGame)
            }
            DisposableEffect(focusGame) {
                onDispose { vm.pauseScreen() }
            }
            Box(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                ScreenCard(
                    screen = screen,
                    stale = screen.image != null && !running,
                    onRefresh = { vm.refreshScreenOnce(focusGame) },
                )
            }
        }

        // 运行中额外给一条总进度（第几步 / 共几步）
        if (running && chainRun != null) {
            ChainProgress(chainRun)
        }

        // ---------- 步骤列表（长按拖动排序） ----------
        //
        // 用 Column + verticalScroll 而不是 LazyColumn：步骤最多 10 个，
        // 全部组合出来没有性能问题，而拖拽换位能直接按「行高 / 偏移」算目标位置，
        // 不用处理 LazyColumn 的可见区与复用（那会让拖到边界时行为很怪）。
        // 这与阿福记账资产页的账户排序是同一套做法。
        Column(
            Modifier
                .weight(1f)
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            ReorderableSteps(
                steps = state.chain.steps,
                chainRun = chainRun,
                enabled = !running,
                capabilityName = { game, id ->
                    state.capabilities[game]?.items?.firstOrNull { it.id == id }?.name ?: id
                },
                onToggle = { idx, checked ->
                    vm.saveChain(
                        state.chain.copy(
                            steps = state.chain.steps.toMutableList().also {
                                it[idx] = it[idx].copy(enabled = checked)
                            }
                        )
                    )
                },
                onDelete = { idx ->
                    vm.saveChain(
                        state.chain.copy(
                            steps = state.chain.steps.toMutableList().also { it.removeAt(idx) }
                        )
                    )
                },
                onEditTasks = { idx -> editingIndex = idx },
                onMove = { from, to ->
                    vm.saveChain(state.chain.copy(steps = move(state.chain.steps, from, to)))
                },
                listModifier = Modifier.fillMaxWidth(),
            )

            if (state.chain.steps.isEmpty()) {
                    Text(
                        "还没有步骤。点下面的「添加步骤」开始编排。",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(vertical = 24.dp),
                    )
            }

            if (!running) {
                    OutlinedButton(
                        onClick = { editingIndex = -2 },
                        modifier = Modifier.fillMaxWidth().height(48.dp),
                        shape = RoundedCornerShape(14.dp),
                    ) {
                        Icon(Icons.Default.Add, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("添加步骤")
                    }
                    // 失败策略
                    val isSkip = state.chain.policy != "stop"
                    Row(
                        Modifier.fillMaxWidth().padding(top = 4.dp, bottom = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text("失败后继续", style = MaterialTheme.typography.bodyMedium)
                            Text(
                                if (isSkip) "某一步失败就跳过，继续跑后面的"
                                else "某一步失败就中止整条链",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        CandySwitch(
                            checked = isSkip,
                            onCheckedChange = { on ->
                                vm.saveChain(state.chain.copy(policy = if (on) "skip" else "stop"))
                            },
                        )
                    }
                }
        }

        // ---------- 底栏 ----------
        ChainActionBar(
            running = running,
            total = state.chain.steps.count { it.enabled },
            busy = state.chainRun?.steps?.any { it.state == "running" } == true,
            onRun = { vm.runChain() },
            onStop = { vm.stopChain() },
        )
    }

    // ---------- 子任务选择 / 添加步骤 ----------
    if (editingIndex == -2) {
        AddStepDialog(
            onPick = { game ->
                editingIndex = -1
                vm.saveChain(
                    state.chain.copy(steps = state.chain.steps + ChainStep(game = game))
                )
            },
            onDismiss = { editingIndex = -1 },
        )
    } else if (editingIndex >= 0) {
        val step = state.chain.steps.getOrNull(editingIndex)
        if (step != null) {
            TaskPickerSheet(
                game = step.game,
                capability = state.capabilities[step.game],
                selected = step.tasks,
                onConfirm = { picked ->
                    // 注意顺序：必须先用 editingIndex 定位，再重置它。
                    // 之前先置 -1 再 it[-1]=... 会直接数组越界崩溃。
                    val idx = editingIndex
                    editingIndex = -1
                    if (idx >= 0 && idx < state.chain.steps.size) {
                        vm.saveChain(
                            state.chain.copy(
                                steps = state.chain.steps.toMutableList().also {
                                    it[idx] = step.copy(tasks = picked)
                                }
                            )
                        )
                    }
                },
                onDismiss = { editingIndex = -1 },
            )
        }
    }
}

internal fun move(list: List<ChainStep>, from: Int, to: Int): List<ChainStep> {
    val m = list.toMutableList()
    val item = m.removeAt(from)
    m.add(to, item)
    return m
}

/** 运行中的总进度条：第几步 / 共几步 + 各步状态点。 */
@Composable
internal fun ChainProgress(run: ChainRun) {
    val done = run.steps.count {
        it.state in listOf("success", "failed", "skipped", "stopped", "not_run")
    }
    Column(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 6.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                "第 ${(run.currentIndex + 1).coerceAtLeast(1)}/${run.total} 步",
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.weight(1f))
            Text(
                "${done}/${run.steps.size} 已完成",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            run.steps.forEach { s ->
                Box(
                    Modifier
                        .weight(1f)
                        .height(4.dp)
                        .clip(CircleShape)
                        .background(stepStateColor(s.state))
                )
            }
        }
    }
}

internal fun stepStateColor(state: String): Color = when (state) {
    "running" -> Color(0xFF2F6FED)
    "success" -> Color(0xFF3BA55D)
    "failed" -> Color(0xFFE5484D)
    "stopped" -> Color(0xFFE0A030)
    "skipped", "not_run" -> Color(0xFFB0B8C4)
    else -> Color(0xFFE0E4EA)
}

internal fun stepStateLabel(state: String): String = when (state) {
    "pending" -> "等待中"
    "running" -> "运行中"
    "success" -> "成功"
    "failed" -> "失败"
    "stopped" -> "已停止"
    "skipped" -> "已跳过"
    "not_run" -> "未执行"
    else -> state
}


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


// ---- 链内容与操作区 ----

@Composable
internal fun ChainContent(
    vm: AppViewModel,
    modifier: Modifier = Modifier,
) {
    val state by vm.state.collectAsStateWithLifecycle()
    val chainRun = state.chainRun
    val running = chainRun?.state == "running"
    var editingIndex by remember { mutableStateOf(-1) }

    LaunchedEffect(Unit) { vm.refreshChain() }

    Column(modifier, verticalArrangement = Arrangement.spacedBy(10.dp)) {
        // 运行中的总进度
        if (running && chainRun != null) {
            ChainProgress(chainRun)
        }

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

            // 关闭游戏和工具：任务没在跑、但有游戏还留在后台占内存时用。
            // 和游戏页那个按钮同源，只是这里一次清全部（编排面向整体）。
            OutlinedButton(
                onClick = { vm.cleanupAll() },
                modifier = Modifier.fillMaxWidth().height(46.dp),
                shape = RoundedCornerShape(14.dp),
            ) {
                Icon(Icons.Default.Delete, null, Modifier.size(18.dp))
                Spacer(Modifier.width(6.dp))
                Text("关闭游戏和工具（全部）")
            }

            val isSkip = state.chain.policy != "stop"
            Row(
                Modifier.fillMaxWidth().padding(top = 4.dp),
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

        // 定时执行：不管链路是否在跑都要能看和改
        ScheduleCard(vm)
    }

    // 子任务选择 / 添加步骤
    if (editingIndex == -2) {
        AddStepDialog(
            onPick = { game ->
                editingIndex = -1
                vm.saveChain(state.chain.copy(steps = state.chain.steps + ChainStep(game = game)))
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

/** 编排的**底部操作栏**：没在跑就「一键跑完整条链」，在跑就「停止整条链」。 */
@Composable
internal fun ChainActionSection(vm: AppViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    val chainRun = state.chainRun
    val running = chainRun?.state == "running"

    ChainActionBar(
        running = running,
        total = state.chain.steps.count { it.enabled },
        busy = chainRun?.steps?.any { it.state == "running" } == true,
        onRun = { vm.runChain() },
        onStop = { vm.stopChain() },
    )
}

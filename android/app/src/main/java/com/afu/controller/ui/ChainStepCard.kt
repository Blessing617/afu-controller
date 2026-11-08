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


// ---- 步骤卡片与操作条 ----

@Composable
internal fun StepCard(
    index: Int,
    step: ChainStep,
    result: ChainStepResult?,
    enabled: Boolean,
    total: Int,
    taskName: (String) -> String,
    onToggle: (Boolean) -> Unit,
    onDelete: () -> Unit,
    onEditTasks: () -> Unit,
    // 拖动状态：由外层 ReorderableSteps 注入
    modifier: Modifier = Modifier,
) {
    val color = GAME_COLORS[step.game] ?: MaterialTheme.colorScheme.primary
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(RADIUS_CARD.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                // 序号 + 游戏色条
                Box(
                    Modifier
                        .size(28.dp)
                        .clip(CircleShape)
                        .background(color.copy(alpha = 0.18f)),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        "${index + 1}",
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.Bold,
                        color = color,
                    )
                }
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        step.displayName.ifBlank { GAME_NAMES[step.game] ?: step.game },
                        style = MaterialTheme.typography.bodyLarge,
                        fontWeight = FontWeight.SemiBold,
                    )
                    val summary = if (step.tasks.isEmpty()) {
                        "按引擎当前配置全跑"
                    } else {
                        step.tasks.take(3).joinToString("、") { taskName(it) } +
                            if (step.tasks.size > 3) " 等 ${step.tasks.size} 项" else ""
                    }
                    Text(
                        summary,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                if (result != null && result.state != "pending") {
                    Text(
                        stepStateLabel(result.state),
                        style = MaterialTheme.typography.labelMedium,
                        color = stepStateColor(result.state),
                        fontWeight = FontWeight.SemiBold,
                    )
                    Spacer(Modifier.width(8.dp))
                }
                CandySwitch(
                    checked = step.enabled,
                    onCheckedChange = onToggle,
                    enabled = enabled,
                )
            }

            if (result?.error?.isNotBlank() == true) {
                Text(
                    result.error,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = onEditTasks, enabled = enabled) {
                    Text("选子任务", fontSize = 13.sp)
                }
                Spacer(Modifier.weight(1f))
                // 拖拽手柄：整行都能长按拖，这里只是给个视觉提示
                Icon(
                    Icons.Default.Menu, "长按拖动排序",
                    Modifier.size(20.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(
                        alpha = if (enabled) 0.7f else 0.25f
                    ),
                )
                Spacer(Modifier.width(8.dp))
                IconButton(onClick = onDelete, enabled = enabled) {
                    Icon(
                        Icons.Default.Delete, "删除", Modifier.size(18.dp),
                        tint = MaterialTheme.colorScheme.error,
                    )
                }
            }
        }
    }
}

@Composable
internal fun ChainActionBar(
    running: Boolean,
    total: Int,
    busy: Boolean,
    onRun: () -> Unit,
    onStop: () -> Unit,
) {
    Surface(
        color = MaterialTheme.colorScheme.background,
        tonalElevation = 0.dp,
        shadowElevation = 0.dp,
        shape = RoundedCornerShape(topStart = 22.dp, topEnd = 22.dp),
    ) {
        Column(
            Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 10.dp),
        ) {
            if (running) {
                CandyButton(
                    text = "停止整条链",
                    onClick = onStop,
                    modifier = Modifier.fillMaxWidth().height(56.dp),
                    kind = CandyKind.Danger,
                    fontSize = 17.sp,
                )
            } else {
                CandyButton(
                    text = when {
                        busy -> "启动中…"
                        total > 0 -> "一键跑完整条链（$total 步）"
                        else -> "没有可执行的步骤"
                    },
                    onClick = onRun,
                    modifier = Modifier.fillMaxWidth().height(56.dp),
                    kind = CandyKind.Primary,
                    enabled = total > 0 && !busy,
                    fontSize = 17.sp,
                )
            }
        }
    }
}

/** 选游戏来新增一步。 */
@Composable
internal fun AddStepDialog(onPick: (String) -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        shape = RoundedCornerShape(RADIUS_CARD.dp),
        containerColor = MaterialTheme.colorScheme.surface,
        onDismissRequest = onDismiss,
        title = { Text("添加步骤") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                GAME_NAMES.forEach { (game, name) ->
                    Surface(
                        shape = RoundedCornerShape(12.dp),
                        color = MaterialTheme.colorScheme.surfaceVariant,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(12.dp))
                            .clickable { onPick(game) },
                    ) {
                        Text(name, Modifier.padding(16.dp))
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

/**
 * 子任务面板：选 + 排序。
 *
 * 上半部分是**已选**的任务，长按可以拖动排序 —— 因为 MAA 的 TaskQueue
 * 本身就是有序队列，排在前面的先执行；BetterGI / 三月七同理（三月七按传入顺序串行）。
 * 下半部分是**未选**的，点一下加进已选。
 *
 * 为什么分成两块而不是一个大列表：用户关心的是「我这次要跑什么、按什么顺序」，
 * 已选区才是重点；未选区只是任务库。混在一起时拖动会误触到没选中的项。
 */

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


// ---- 可拖拽排序的步骤列表 ----

@Composable
internal fun ReorderableSteps(
    steps: List<ChainStep>,
    chainRun: ChainRun?,
    enabled: Boolean,
    capabilityName: (String, String) -> String,
    onToggle: (Int, Boolean) -> Unit,
    onDelete: (Int) -> Unit,
    onEditTasks: (Int) -> Unit,
    onMove: (Int, Int) -> Unit,
    listModifier: Modifier = Modifier,
) {
    var draggingIndex by remember { mutableStateOf<Int?>(null) }
    var dragOffset by remember { mutableFloatStateOf(0f) }
    var rowHeightPx by remember { mutableFloatStateOf(0f) }

    val density = LocalDensity.current
    val gapPx = with(density) { 10.dp.toPx() }

    Column(listModifier, verticalArrangement = Arrangement.spacedBy(10.dp)) {
        steps.forEachIndexed { index, step ->
            val from = draggingIndex
            val target = if (from == null || rowHeightPx <= 0f) {
                from
            } else {
                (from + (dragOffset / rowHeightPx).roundToInt()).coerceIn(0, steps.lastIndex)
            }
            val neighborOffset = when {
                from == null || target == null -> 0f
                index in (from + 1)..target -> -rowHeightPx
                index in target until from -> rowHeightPx
                else -> 0f
            }
            val animatedNeighbor by animateFloatAsState(
                targetValue = if (from == null) 0f else neighborOffset,
                animationSpec = Motion.springy(),
                label = "step-shift",
            )
            val translation = if (index == from) dragOffset else animatedNeighbor
            val lifted = index == from

            StepCard(
                index = index,
                step = step,
                result = chainRun?.steps?.getOrNull(index),
                enabled = enabled,
                total = steps.size,
                taskName = { id -> capabilityName(step.game, id) },
                onToggle = { checked -> onToggle(index, checked) },
                onDelete = { onDelete(index) },
                onEditTasks = { onEditTasks(index) },
                modifier = Modifier
                    .zIndex(if (lifted) 1f else 0f)
                    .graphicsLayer {
                        translationY = translation
                        val scale = if (lifted) 1.02f else 1f
                        scaleX = scale
                        scaleY = scale
                        if (lifted) shadowElevation = 12f
                    }
                    .onGloballyPositioned { coords ->
                        if (rowHeightPx <= 0f) {
                            rowHeightPx = coords.size.height + gapPx
                        }
                    }
                    .pointerInput(step, index, steps.size, enabled) {
                        if (!enabled) return@pointerInput
                        detectDragGesturesAfterLongPress(
                            onDragStart = {
                                draggingIndex = index
                                dragOffset = 0f
                            },
                            onDrag = { change, dragAmount ->
                                change.consume()
                                dragOffset += dragAmount.y
                            },
                            onDragEnd = {
                                val startI = draggingIndex
                                if (startI != null && rowHeightPx > 0f) {
                                    val to = (startI + (dragOffset / rowHeightPx).roundToInt())
                                        .coerceIn(0, steps.lastIndex)
                                    if (to != startI) onMove(startI, to)
                                }
                                draggingIndex = null
                                dragOffset = 0f
                            },
                            onDragCancel = {
                                draggingIndex = null
                                dragOffset = 0f
                            },
                        )
                    },
            )
        }
    }
}

/**
 * 编排的**中间内容区**：步骤列表 + 添加入口 + 失败策略。
 *
 * 从 ChainScreen 里拆出来，是为了让编排能嵌进和游戏页同一套外壳
 * （共用顶栏「已连接 + 设置」和底栏四个标签），而不是单独弹一个页面。
 */

package com.afu.controller.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
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


// ---- 子任务选择面板 ----

@Composable
internal fun TaskPickerSheet(
    game: String,
    capability: Capability?,
    selected: List<String>,
    onConfirm: (List<String>) -> Unit,
    onDismiss: () -> Unit,
) {
    // 已选：保持用户排的顺序
    var picked by remember { mutableStateOf(selected) }
    val allItems = capability?.items ?: emptyList()
    val byId = allItems.associateBy { it.id }
    val unselected = allItems.filter { it.id !in picked }

    var draggingIndex by remember { mutableStateOf<Int?>(null) }
    var dragOffset by remember { mutableFloatStateOf(0f) }
    var rowHeightPx by remember { mutableFloatStateOf(0f) }
    val density = LocalDensity.current
    val gapPx = with(density) { 6.dp.toPx() }

    AlertDialog(
        shape = RoundedCornerShape(RADIUS_CARD.dp),
        containerColor = MaterialTheme.colorScheme.surface,
        onDismissRequest = onDismiss,
        title = {
            Column {
                Text("${GAME_NAMES[game] ?: game} · 选子任务")
                Text(
                    when {
                        capability == null -> "正在读取引擎能力…"
                        capability.fromEngine -> capability.detail
                        else -> capability.detail.ifBlank { "以下是默认清单" }
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = if (capability?.fromEngine == true) {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    } else {
                        MaterialTheme.colorScheme.error
                    },
                )
            }
        },
        text = {
            Column(Modifier.height(420.dp).fillMaxWidth()) {
                if (allItems.isEmpty()) {
                    Text("没有可选项", style = MaterialTheme.typography.bodyMedium)
                    return@Column
                }

                // -------- 已选（可拖动排序） --------
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        "已选 ${picked.size} 项",
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Spacer(Modifier.width(6.dp))
                    if (picked.size > 1) {
                        Text(
                            "长按可拖动排序",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.primary,
                        )
                    }
                }

                if (picked.isEmpty()) {
                    Text(
                        "还没选。不选任何一项 = 按引擎当前配置全跑",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(vertical = 8.dp),
                    )
                } else {
                    Column(
                        Modifier
                            .weight(1f, fill = false)
                            .verticalScroll(rememberScrollState())
                            .padding(vertical = 4.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        picked.forEachIndexed { index, id ->
                            val from = draggingIndex
                            val target = if (from == null || rowHeightPx <= 0f) from
                            else (from + (dragOffset / rowHeightPx).roundToInt())
                                .coerceIn(0, picked.lastIndex)
                            val neighborOffset = when {
                                from == null || target == null -> 0f
                                index in (from + 1)..target -> -rowHeightPx
                                index in target until from -> rowHeightPx
                                else -> 0f
                            }
                            val animatedNeighbor by animateFloatAsState(
                                targetValue = if (from == null) 0f else neighborOffset,
                                animationSpec = Motion.springy(),
                                label = "task-shift",
                            )
                            val translation = if (index == from) dragOffset else animatedNeighbor
                            val lifted = index == from

                            PickedTaskRow(
                                order = index + 1,
                                name = byId[id]?.name ?: id,
                                note = byId[id]?.note ?: "",
                                onRemove = { picked = picked.filterIndexed { i, _ -> i != index } },
                                modifier = Modifier
                                    .zIndex(if (lifted) 1f else 0f)
                                    .graphicsLayer {
                                        translationY = translation
                                        val sc = if (lifted) 1.02f else 1f
                                        scaleX = sc; scaleY = sc
                                        if (lifted) shadowElevation = 10f
                                    }
                                    .onGloballyPositioned { c ->
                                        if (rowHeightPx <= 0f) rowHeightPx = c.size.height + gapPx
                                    }
                                    .pointerInput(id, index, picked.size) {
                                        detectDragGesturesAfterLongPress(
                                            onDragStart = { draggingIndex = index; dragOffset = 0f },
                                            onDrag = { change, amount ->
                                                change.consume(); dragOffset += amount.y
                                            },
                                            onDragEnd = {
                                                val start = draggingIndex
                                                if (start != null && rowHeightPx > 0f) {
                                                    val to = (start + (dragOffset / rowHeightPx).roundToInt())
                                                        .coerceIn(0, picked.lastIndex)
                                                    if (to != start) {
                                                        picked = picked.toMutableList().also {
                                                            val it0 = it.removeAt(start)
                                                            it.add(to, it0)
                                                        }
                                                    }
                                                }
                                                draggingIndex = null; dragOffset = 0f
                                            },
                                            onDragCancel = { draggingIndex = null; dragOffset = 0f },
                                        )
                                    },
                            )
                        }
                    }
                }

                HorizontalDivider(
                    Modifier.padding(vertical = 8.dp),
                    color = MaterialTheme.colorScheme.outline.copy(alpha = 0.4f),
                )

                // -------- 未选（点一下加入） --------
                if (unselected.isNotEmpty()) {
                    Text(
                        "可添加（点一下加进已选）",
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.SemiBold,
                    )
                    LazyColumn(Modifier.weight(1f)) {
                        itemsIndexed(unselected) { _, item ->
                            Row(
                                Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(8.dp))
                                    .clickable(
                                        interactionSource = remember { MutableInteractionSource() },
                                        indication = ripple(),
                                    ) { picked = picked + item.id }
                                    .padding(vertical = 8.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Icon(
                                    Icons.Default.Add, null, Modifier.size(16.dp),
                                    tint = MaterialTheme.colorScheme.primary,
                                )
                                Spacer(Modifier.width(8.dp))
                                Column {
                                    Text(item.name, style = MaterialTheme.typography.bodyMedium)
                                    if (item.note.isNotBlank()) {
                                        Text(
                                            item.note,
                                            style = MaterialTheme.typography.labelSmall,
                                            color = MaterialTheme.colorScheme.error,
                                        )
                                    }
                                }
                            }
                            HorizontalDivider(
                                color = MaterialTheme.colorScheme.outline.copy(alpha = 0.25f)
                            )
                        }
                    }
                } else {
                    Spacer(Modifier.weight(1f))
                }
            }
        },
        confirmButton = {
            CandyButton(
                text = "保存",
                onClick = { onConfirm(picked) },
                kind = CandyKind.Primary,
                contentPadding = PaddingValues(horizontal = 20.dp, vertical = 8.dp),
                fontSize = 14.sp,
            )
        },
        dismissButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                CandyButton(
                    text = "全不选",
                    onClick = { picked = emptyList() },
                    kind = CandyKind.Ghost,
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
                    fontSize = 13.sp,
                )
                CandyButton(
                    text = "取消",
                    onClick = onDismiss,
                    kind = CandyKind.Ghost,
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
                    fontSize = 13.sp,
                )
            }
        },
    )
}

/** 已选任务的一行：序号 + 名称 + 移除按钮，长按可拖。 */

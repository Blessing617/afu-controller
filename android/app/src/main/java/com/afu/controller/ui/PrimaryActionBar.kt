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
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
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


@Composable
internal fun PrimaryActionBar(
    vm: AppViewModel,
    state: UiState,
    game: String,
    pickedTaskNames: List<String> = emptyList(),
    onEditTasks: () -> Unit = {},
) {
    val info = state.games[game]
    val current = state.current
    val running = current != null && current.game == game
    val anyRunning = current != null
    val busy = state.busyGame == game

    val canStart = state.connected && info?.ready == true && !anyRunning && !busy
    val hint = when {
        !state.connected -> "未连接电脑"
        info == null -> "正在读取组件状态…"
        info.ready -> ""
        else -> "缺少 ${missingNames(info)}"
    }

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
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            if (running) {
                // 运行中：只给「停止」，不给「开始」；外圈加一层呼吸光晕，
                // 让「正在跑」这件事在远处也能一眼看到。停止后这层自然消失。
                val glowTransition = rememberInfiniteTransition(label = "running-glow")
                val glow by glowTransition.animateFloat(
                    initialValue = 0f,
                    targetValue = 1f,
                    animationSpec = infiniteRepeatable(
                        animation = tween(1600, easing = LinearEasing),
                        repeatMode = RepeatMode.Reverse,
                    ),
                    label = "running-glow-alpha",
                )
                Box(Modifier.fillMaxWidth().height(56.dp)) {
                    Box(
                        Modifier
                            .matchParentSize()
                            .graphicsLayer {
                                scaleX = 1.03f
                                scaleY = 1.10f
                                alpha = 0.16f + glow * 0.20f
                            }
                            .clip(RoundedCornerShape(50))
                            .background(MaterialTheme.colorScheme.error)
                    )
                    CandyButton(
                        text = "停止任务",
                        onClick = vm::stop,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(56.dp),
                        kind = CandyKind.Danger,
                        fontSize = 17.sp,
                    )
                }
            } else {
                // 按钮文字要如实反映「这次会跑什么」：
                // 没选子任务 → 「开始一键长草」（按引擎配置全跑）
                // 选了 N 项     → 「开始（N 项）」，并在上面列出具体是哪几项
                val pickedNames = pickedTaskNames
                // 按钮就写「开始」：动作细节交给上面那行摘要，不拼成「开始一键长草」这种病句
                val label = when {
                    pickedNames.isEmpty() -> "开始"
                    else -> "开始（${pickedNames.size} 项）"
                }

                // 已选子任务摘要：让用户点下去之前就知道会跑什么
                if (pickedNames.isNotEmpty()) {
                    Row(
                        Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            pickedNames.take(4).joinToString(" · ") +
                                if (pickedNames.size > 4) " 等 ${pickedNames.size} 项" else "",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.primary,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.weight(1f),
                        )
                        TextButton(
                            onClick = onEditTasks,
                            enabled = !running,
                            contentPadding = androidx.compose.foundation.layout.PaddingValues(
                                horizontal = 8.dp
                            ),
                        ) {
                            Text("修改", fontSize = 12.sp)
                        }
                    }
                } else {
                    Row(
                        Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            "按引擎当前配置全跑",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.weight(1f),
                        )
                        TextButton(
                            onClick = onEditTasks,
                            enabled = !running,
                            contentPadding = androidx.compose.foundation.layout.PaddingValues(
                                horizontal = 8.dp
                            ),
                        ) {
                            Text("选子任务", fontSize = 12.sp)
                        }
                    }
                }

                CandyButton(
                    text = if (busy) "启动中…" else label,
                    onClick = { vm.start(game) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(56.dp),
                    kind = CandyKind.Primary,
                    enabled = canStart,
                    fontSize = 17.sp,
                )
            }

            val reason = when {
                running -> ""
                hint.isNotBlank() -> hint
                anyRunning -> "另一个任务正在运行，请先等它结束"
                else -> ""
            }
            if (reason.isNotBlank()) {
                Text(
                    reason,
                    color = if (anyRunning && hint.isBlank()) {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    } else {
                        MaterialTheme.colorScheme.error
                    },
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
    }
}

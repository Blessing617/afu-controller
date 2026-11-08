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


// ---- 状态卡片与小组件 ----

@Composable
internal fun ScreenCard(screen: GameScreen, stale: Boolean, onRefresh: () -> Unit) {
    val image = screen.image
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(RADIUS_CARD.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("画面", fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                if (stale) {
                    Text(
                        "旧快照",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier
                            .background(
                                MaterialTheme.colorScheme.surface,
                                RoundedCornerShape(6.dp),
                            )
                            .padding(horizontal = 6.dp, vertical = 2.dp),
                    )
                }
            }

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(
                        if (image != null && image.height > 0) {
                            image.width.toFloat() / image.height
                        } else {
                            16f / 9f
                        }
                    )
                    .background(Color(0xFF101820), RoundedCornerShape(10.dp)),
                contentAlignment = Alignment.Center,
            ) {
                if (image != null) {
                    Image(
                        bitmap = image,
                        contentDescription = "游戏画面",
                        modifier = Modifier.fillMaxSize(),
                        contentScale = ContentScale.Fit,
                    )
                } else {
                    Text(
                        "还没有画面",
                        color = Color(0xFF9AA4B2),
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                if (screen.loading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(26.dp),
                        strokeWidth = 2.dp,
                        color = Color.White,
                    )
                }
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    if (screen.capturedAt.isNotBlank()) {
                        "截图于 ${clockText(screen.capturedAt)}"
                    } else {
                        "未获取到画面"
                    },
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.weight(1f),
                )
                androidx.compose.material3.OutlinedButton(
                    onClick = onRefresh,
                    enabled = !screen.loading,
                ) {
                    Icon(Icons.Default.Refresh, null, Modifier.size(16.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("刷新一张", fontSize = 12.sp)
                }
            }

            if (screen.error.isNotBlank()) {
                Text(
                    screen.error,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}

/** 服务端给的是 ISO 本地时间，只取时分秒（避免手机与电脑时钟差带来的困惑）。 */
internal fun clockText(iso: String): String {
    val time = iso.substringAfter('T', "")
    return if (time.length >= 8) time.substring(0, 8) else iso
}

@Composable
internal fun StatusLine(ok: Boolean, text: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            Modifier
                .size(10.dp)
                .background(if (ok) OK else WARN, CircleShape)
        )
        Spacer(Modifier.width(8.dp))
        Text(text, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
internal fun TaskCard(task: TaskRun) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        ),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(task.title, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                Text(stateLabel(task.state), color = stateColor(task.state), fontWeight = FontWeight.Bold)
            }
            Text("已运行 ${task.durationSeconds.toInt()} 秒", style = MaterialTheme.typography.bodySmall)
            // 进度与「距上次进展」要一起给：只看到「已运行 40 分钟」没法判断是在推进还是卡死了
            progressText(task)?.let {
                Text(it, style = MaterialTheme.typography.bodySmall)
            }
            task.stall.idleSeconds?.takeIf { it >= 60 && task.state == "running" }?.let {
                Text(
                    "距上次进展 ${(it / 60).toInt()} 分钟",
                    style = MaterialTheme.typography.bodySmall,
                    color = if (it >= 600) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (task.error.isNotBlank()) {
                Text(
                    task.error,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            task.logTail.lastOrNull()?.let {
                Text(it.take(120), style = MaterialTheme.typography.bodySmall, maxLines = 2)
            }
            // 停止按钮不放在这里：底栏的主操作栏已经有「停止任务」了，
            // 同一屏两个停止键既重复又容易点错。任务卡只负责显示状态与日志。
        }
    }
}

internal fun stateLabel(state: String) = when (state) {
    "running" -> "运行中"
    "success" -> "成功"
    "failed" -> "失败"
    "stopped" -> "已停止"
    "timeout" -> "超时"
    else -> state
}

internal fun stateColor(state: String): Color = when (state) {
    "running" -> Color(0xFF2F6FED)
    "success" -> Color(0xFF3BA55D)
    "failed", "timeout" -> Color(0xFFE5484D)
    else -> Color(0xFF888888)
}

/** 把引擎进度拼成一句人话：阶段 11/13 · 战斗中；一条龙 2/4。 */
internal fun progressText(task: TaskRun): String? {
    val p = task.progress
    if (p.isEmpty()) return null
    val parts = buildList {
        p["stage"]?.let { add("阶段 $it") }
        p["task"]?.let { add("任务 $it") }
        p["phase"]?.let { add(it) }
    }
    return parts.takeIf { it.isNotEmpty() }?.joinToString(" · ")
}

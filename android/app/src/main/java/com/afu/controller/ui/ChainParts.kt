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
internal fun ChainTopBar(
    running: Boolean,
    busy: Boolean,
    onBack: () -> Unit,
    onRefresh: () -> Unit,
) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(start = 4.dp, end = 8.dp, top = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconButton(onClick = onBack) {
            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
        }
        Text("编排", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
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
        IconButton(onClick = onRefresh, enabled = !busy) {
            Icon(Icons.Default.Refresh, contentDescription = "刷新")
        }
    }
}

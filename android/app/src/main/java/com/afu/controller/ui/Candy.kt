package com.afu.controller.ui

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties

/**
 * 糖果风格的基础组件。
 *
 * 为什么不直接用 Material3 的 Button / Card / AlertDialog：
 * 默认外观（方形输入框、扁平按钮、圆形时钟盘）和本项目的圆角 + 果冻观感不是一套语言。
 * 这里只重做「外观与按压手感」，交互语义（点击、返回、取消、确认）保持和 Material 一致。
 */

enum class CandyKind { Primary, Accent, Soft, Ghost, Danger }

private val Capsule = RoundedCornerShape(50)

@Composable
fun CandyButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    kind: CandyKind = CandyKind.Soft,
    enabled: Boolean = true,
    contentPadding: PaddingValues = PaddingValues(horizontal = 20.dp, vertical = 12.dp),
    fontSize: androidx.compose.ui.unit.TextUnit = 15.sp,
) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (pressed && enabled) 0.96f else 1f,
        animationSpec = spring(dampingRatio = 0.42f, stiffness = 900f),
        label = "candy-press",
    )
    val cs = MaterialTheme.colorScheme
    // 禁用时统一成「浅灰底 + 灰字」：比整体调透明度更清楚它点不了
    val base = when {
        !enabled -> cs.surfaceVariant
        kind == CandyKind.Primary -> BRAND
        kind == CandyKind.Accent -> ACCENT
        kind == CandyKind.Soft -> cs.surfaceVariant
        else -> Color.Transparent
    }
    val top = when {
        !enabled -> base
        kind == CandyKind.Primary -> Color(0xFF4B7CF5)
        kind == CandyKind.Accent -> Color(0xFFFF9A82)
        else -> base
    }
    val fg = when {
        !enabled -> cs.onSurfaceVariant.copy(alpha = 0.75f)
        kind == CandyKind.Primary || kind == CandyKind.Accent -> Color.White
        kind == CandyKind.Danger -> cs.error
        kind == CandyKind.Ghost -> cs.onSurfaceVariant
        else -> cs.onSurface
    }
    // 不用「底部厚度 + 淡色打底」那一套了：两个主按钮要长得一模一样，
    // 那层打底会看起来像两层叠在一起。
    val thick = false
    val brush = when (kind) {
        CandyKind.Primary, CandyKind.Accent -> Brush.verticalGradient(listOf(top, base))
        else -> Brush.verticalGradient(listOf(base, base))
    }

    val thickPx = 0f
    Box(
        modifier
            .graphicsLayer { scaleX = scale; scaleY = scale }
            .clip(Capsule)
            .background(Color.Transparent)
            .drawBehind {
                val bodyH = size.height - thickPx
                drawRoundRect(
                    brush = brush,
                    size = androidx.compose.ui.geometry.Size(size.width, bodyH),
                    cornerRadius = androidx.compose.ui.geometry.CornerRadius(bodyH / 2f),
                )
            }
            .clickable(
                interactionSource = interaction,
                indication = null,
                enabled = enabled,
                onClick = onClick,
            )
            .padding(contentPadding),
        contentAlignment = Alignment.Center,
    ) {
        Box(contentAlignment = Alignment.Center) {
            Text(
                text = text,
                color = fg,
                fontFamily = CandyFontFamily,
                fontSize = fontSize,
                fontWeight = if (thick) FontWeight.Normal else FontWeight.Medium,
                textAlign = TextAlign.Center,
            )
        }
    }
}

@Composable
fun CandyCard(
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(RADIUS_CARD.dp),
        color = MaterialTheme.colorScheme.surface,
        tonalElevation = 0.dp,
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(GAP_M.dp)) {
            content()
        }
    }
}

@Composable
fun CandyPill(text: String, color: Color = OK, modifier: Modifier = Modifier) {
    Row(
        modifier
            .clip(Capsule)
            .background(color.copy(alpha = 0.14f))
            .padding(horizontal = 11.dp, vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Box(Modifier.size(6.dp).clip(RoundedCornerShape(50)).background(color))
        Text(text, fontSize = 12.sp, color = color)
    }
}

/** 时间点胶囊：点文字编辑，点右侧 × 删除。 */
@Composable
fun CandyChip(
    text: String,
    onDelete: () -> Unit,
    modifier: Modifier = Modifier,
    onClick: () -> Unit = {},
) {
    Row(
        modifier
            .clip(Capsule)
            .background(BRAND.copy(alpha = 0.12f))
            .clickable(onClick = onClick)
            .padding(start = 14.dp, end = 6.dp, top = 6.dp, bottom = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(
            text,
            fontFamily = CandyFontFamily,
            fontSize = 16.sp,
            color = BRAND_DEEP,
        )
        Box(
            Modifier
                .size(18.dp)
                .clip(RoundedCornerShape(50))
                .clickable(onClick = onDelete),
            contentAlignment = Alignment.Center,
        ) {
            Text("×", fontSize = 14.sp, color = BRAND_DEEP.copy(alpha = 0.55f))
        }
    }
}

@Composable
fun CandySwitch(checked: Boolean, onCheckedChange: (Boolean) -> Unit, enabled: Boolean = true) {
    val track by animateColorAsState(
        targetValue = if (checked) BRAND else MaterialTheme.colorScheme.outline,
        label = "switch-track",
    )
    val offset by animateDpAsState(targetValue = if (checked) 20.dp else 0.dp, label = "switch-dot")
    Box(
        Modifier
            .size(width = 48.dp, height = 28.dp)
            .clip(Capsule)
            .background(track)
            .clickable(enabled = enabled) { onCheckedChange(!checked) }
            .padding(3.dp),
        contentAlignment = Alignment.CenterStart,
    ) {
        Box(
            Modifier
                .offset(x = offset)
                .size(22.dp)
                .clip(RoundedCornerShape(50))
                .background(Color.White),
        )
    }
}

@Composable
fun CandyDialog(
    title: String,
    message: String,
    confirmText: String,
    dismissText: String,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
    danger: Boolean = false,
) {
    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Box(Modifier.fillMaxWidth().padding(horizontal = 28.dp), contentAlignment = Alignment.Center) {
            Surface(
                shape = RoundedCornerShape(RADIUS_CARD.dp),
                color = MaterialTheme.colorScheme.surface,
            ) {
                Column(
                    Modifier.padding(22.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    Text(title, style = MaterialTheme.typography.titleMedium)
                    Text(
                        message,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        CandyButton(
                            dismissText,
                            onDismiss,
                            Modifier.weight(1f),
                            CandyKind.Ghost,
                        )
                        CandyButton(
                            confirmText,
                            onConfirm,
                            Modifier.weight(1f),
                            if (danger) CandyKind.Accent else CandyKind.Primary,
                        )
                    }
                }
            }
        }
    }
}

/** 七个星期的自绘选择按钮。 */
@Composable
fun WeekdayRow(
    selected: List<Int>,
    onToggle: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val labels = listOf(1 to "一", 2 to "二", 3 to "三", 4 to "四", 5 to "五", 6 to "六", 7 to "日")
    Row(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        labels.forEach { (day, label) ->
            val on = selected.isEmpty() || day in selected
            Box(
                Modifier
                    .weight(1f)
                    .height(38.dp)
                    .clip(RoundedCornerShape(13.dp))
                    .background(if (on) BRAND else MaterialTheme.colorScheme.surfaceVariant)
                    .clickable { onToggle(day) },
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    label,
                    fontSize = 13.sp,
                    color = if (on) Color.White else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

/** 行内小按钮（Ghost 样式），给「其它地址」这类次要操作。 */
@Composable
fun RowScope.CandyInlineButton(text: String, onClick: () -> Unit) {
    CandyButton(text, onClick, Modifier, CandyKind.Ghost, contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp))
}

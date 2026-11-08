package com.afu.controller.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.snapping.rememberSnapFlingBehavior
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val ITEM_H = 44.dp
private val WHEEL_H = ITEM_H * 3

/**
 * 底部弹层的糖果时间选择器：小时与分钟两列滚动数字 + 实时预览。
 *
 * 替代 Material3 的 TimePicker（圆形时钟盘）：功能一样（选时分），
 * 但外观是项目的圆体大数字 + 胶囊按钮。
 */
@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun WheelColumn(
    count: Int,
    initial: Int,
    onSelected: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val state = rememberLazyListState(initialFirstVisibleItemIndex = initial)
    val fling = rememberSnapFlingBehavior(lazyListState = state)
    val selected = state.firstVisibleItemIndex.coerceIn(0, count - 1)
    LaunchedEffect(selected) { onSelected(selected) }

    LazyColumn(
        state = state,
        flingBehavior = fling,
        contentPadding = PaddingValues(vertical = ITEM_H),
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = modifier.height(WHEEL_H),
    ) {
        items(count) { index ->
            val on = index == selected
            Box(
                Modifier.height(ITEM_H).fillMaxWidth(),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = "%02d".format(index),
                    fontFamily = CandyFontFamily,
                    fontSize = if (on) 40.sp else 22.sp,
                    color = if (on) {
                        MaterialTheme.colorScheme.onSurface
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.35f)
                    },
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CandyTimePickerSheet(
    initial: String,
    title: String,
    onConfirm: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    val parts = initial.split(":")
    val startHour = parts.getOrNull(0)?.toIntOrNull()?.coerceIn(0, 23) ?: 8
    val startMinute = parts.getOrNull(1)?.toIntOrNull()?.coerceIn(0, 59) ?: 0

    var hour by remember { mutableIntStateOf(startHour) }
    var minute by remember { mutableIntStateOf(startMinute) }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        shape = RoundedCornerShape(topStart = 30.dp, topEnd = 30.dp),
        containerColor = MaterialTheme.colorScheme.background,
        dragHandle = null,
        scrimColor = Color.Black.copy(alpha = 0.42f),
    ) {
        Column(
                    Modifier
                        .padding(horizontal = 20.dp, vertical = 10.dp)
                        .navigationBarsPadding(),
                    verticalArrangement = Arrangement.spacedBy(GAP_S.dp),
                ) {
                    Box(
                        Modifier
                            .align(Alignment.CenterHorizontally)
                            .size(width = 44.dp, height = 5.dp)
                            .clip(RoundedCornerShape(50))
                            .background(MaterialTheme.colorScheme.outline)
                    )
                    Row(
                        Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(title, style = MaterialTheme.typography.titleLarge)
                        Box(Modifier.weight(1f))
                        Text(
                            "取消",
                            fontSize = 13.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier
                                .clip(RoundedCornerShape(50))
                                .clickable(onClick = onDismiss)
                                .padding(horizontal = 12.dp, vertical = 8.dp),
                        )
                    }

                    // 两列滚动数字 + 中间高亮框：必须撑满宽度再居中，
                    // 否则 Column 默认左对齐，整组会贴在左边
                    Box(
                        Modifier.fillMaxWidth(),
                        contentAlignment = Alignment.Center,
                    ) {
                        Box(
                            Modifier
                                .width(248.dp)
                                .height(54.dp)
                                .clip(RoundedCornerShape(16.dp))
                                .background(MaterialTheme.colorScheme.surface)
                                .border(
                                    2.dp,
                                    BRAND.copy(alpha = 0.22f),
                                    RoundedCornerShape(16.dp),
                                )
                        )
                        Row(
                            horizontalArrangement = Arrangement.spacedBy(6.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            WheelColumn(24, startHour, { hour = it }, Modifier.width(96.dp))
                            Text(
                                ":",
                                fontFamily = CandyFontFamily,
                                fontSize = 40.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            WheelColumn(60, startMinute, { minute = it }, Modifier.width(96.dp))
                        }
                    }

                    Text(
                        "上下滑动数字 · 24 小时制",
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.align(Alignment.CenterHorizontally),
                    )

                    val preview = "%02d:%02d".format(hour, minute)
            CandyButton(
                "确定 · $preview",
                onClick = { onConfirm(preview) },
                modifier = Modifier.fillMaxWidth(),
                kind = CandyKind.Accent,
                contentPadding = PaddingValues(vertical = 14.dp),
            )
        }
    }
}

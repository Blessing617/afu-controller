package com.afu.controller.ui

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.ContentTransform
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import android.provider.Settings
import android.content.Context

/**
 * 转场组件：把「有方向、有纵深」的两条规则集中在这里，页面里不再各写一套。
 *
 * 参考阿福记账的动效语言：
 *   - 同级（标签之间）：新页面从它在导航里的相对方位进入，位移 ≤ 屏宽 12%，并带缩放收敛
 *   - 层级（标签页 → 二级页）：二级页从底部整屏滑入，底层缩小并压暗
 *   - 系统关闭动画时退化为直切
 */

/** 系统是否关闭了动画（读设置项的动画缩放比例）。 */
@Composable
fun animationsEnabled(): Boolean {
    val ctx = LocalView.current.context
    val scale = runCatching {
        Settings.Global.getFloat(ctx.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f)
    }.getOrDefault(1f)
    val transition = runCatching {
        Settings.Global.getFloat(ctx.contentResolver, Settings.Global.TRANSITION_ANIMATION_SCALE, 1f)
    }.getOrDefault(1f)
    return scale > 0f && transition > 0f
}

/**
 * 同级切换：底部标签之间。
 *
 * direction: +1 表示往右切（新页从右侧进来），-1 反之。
 * 位移幅度 = 屏宽 × Motion.SWITCH_SLIDE_RATIO，绝不整屏平移。
 */
@Composable
fun TabTransition(direction: Int): ContentTransform {
    val enabled = animationsEnabled()
    if (!enabled) {
        return EnterTransition.None togetherWith ExitTransition.None
    }
    val widthPx = with(LocalDensity.current) {
        LocalConfiguration.current.screenWidthDp.dp.toPx() * Motion.SWITCH_SLIDE_RATIO
    }.toInt()

    val enter = slideInHorizontally(
        initialOffsetX = { (widthPx * direction) },
        animationSpec = Motion.slideSpec(),
    ) + fadeIn(tween(Motion.SWITCH_MS))
    val exit = slideOutHorizontally(
        targetOffsetX = { -widthPx * direction / 2 },
        animationSpec = tween(Motion.SWITCH_MS),
    ) + fadeOut(tween(Motion.SWITCH_MS / 2))
    return enter togetherWith exit
}

/** 同级切换的内容容器：自动判断方向。 */
@Composable
fun <T> DirectionalTabContent(
    targetState: T,
    direction: Int,
    modifier: Modifier = Modifier,
    content: @Composable (T) -> Unit,
) {
    // 转场配置必须在组合阶段算好：transitionSpec 的 lambda 不是 @Composable，
    // 在它里面读 LocalConfiguration 会直接编译失败。
    val transform = TabTransition(direction)
    AnimatedContent(
        targetState = targetState,
        transitionSpec = { transform },
        label = "tab",
        modifier = modifier,
    ) { value ->
        content(value)
    }
}

/**
 * 层级进入：二级页整屏从底部滑入，同时底层缩小并压暗。
 *
 * 用法：
 *
 *     LayeredScreen(open = showSettings, onClose = { showSettings = false }) {
 *         // 底层整屏内容
 *     } then = {
 *         SettingsScreen(onBack = { showSettings = false })
 *     }
 */

@Composable
fun LayeredScreen(
    open: Boolean,
    background: @Composable BoxScope.() -> Unit,
    foreground: @Composable BoxScope.() -> Unit,
) {
    val enabled = animationsEnabled()
    val progress by animateFloatAsState(
        targetValue = if (open) 1f else 0f,
        animationSpec = if (enabled) tween(Motion.ENTER_MS) else tween(0),
        label = "layer",
    )
    val scale by animateFloatAsState(
        targetValue = if (open) Motion.PUSH_BACK_SCALE else 1f,
        animationSpec = if (enabled) tween(Motion.ENTER_MS) else tween(0),
        label = "layerScale",
    )
    val shift by animateDpAsState(
        targetValue = if (open) (-16).dp else 0.dp,
        animationSpec = if (enabled) tween(Motion.ENTER_MS) else tween(0),
        label = "layerShift",
    )

    Box(Modifier.fillMaxSize().clipToBounds()) {
        Box(
            Modifier
                .fillMaxSize()
                .graphicsLayer {
                    scaleX = scale
                    scaleY = scale
                    alpha = 1f - Motion.PUSH_BACK_DIM * progress
                }
                .padding(top = shift),
            content = background,
        )
        if (progress > 0.001f) {
            Box(
                Modifier
                    .fillMaxSize()
                    .graphicsLayer {
                        translationY = (1f - progress) * size.height
                    },
                content = foreground,
            )
        }
    }
}

/**
 * 进入二级页时的「整屏滑入」包装（不压暗底层）。
 * 用在设置 → 连接设置这种：二级页整屏覆盖，包括底部导航。
 */
@Composable
fun SlideUpScreen(open: Boolean, content: @Composable () -> Unit) {
    val enabled = animationsEnabled()

    // 关键：位移量必须来自**已知的屏幕高度**，不能用 graphicsLayer 里的 size。
    // 那里第一次组合时 size 还是 0，translationY 算出来永远是 0 —— 页面会直接
    // 贴到最终位置，「滑入」完全没有发生，多层页面就这样堆在一起了。
    val screenHeightPx = with(LocalDensity.current) {
        LocalConfiguration.current.screenHeightDp.dp.toPx()
    }

    val progress = remember { Animatable(if (open) 1f else 0f) }
    var visible by remember { mutableStateOf(open) }

    LaunchedEffect(open) {
        if (open) {
            // 先把 progress 压到 0（= 完全在屏幕下方），再滑上来
            visible = true
            progress.snapTo(0f)
            progress.animateTo(
                targetValue = 1f,
                animationSpec = if (enabled) tween(Motion.ENTER_MS) else tween(0),
            )
        } else {
            progress.animateTo(
                targetValue = 0f,
                animationSpec = if (enabled) tween(Motion.ENTER_MS) else tween(0),
            )
            // 动画跑完才真正移除，避免「滑到一半突然消失」
            visible = false
        }
    }

    if (!visible) return

    // 1) clipToBounds：滑到一半的页面必须被裁在屏幕里，否则会「漏」到下面去
    // 2) 不透明底色：二级页是整屏覆盖，不能让人看见下层的字
    Box(
        Modifier
            .fillMaxSize()
            .clipToBounds()
            .graphicsLayer { translationY = (1f - progress.value) * screenHeightPx }
            .background(MaterialTheme.colorScheme.background),
    ) {
        content()
    }
}

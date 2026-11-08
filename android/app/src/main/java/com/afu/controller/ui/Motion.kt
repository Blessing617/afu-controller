package com.afu.controller.ui

import androidx.compose.animation.core.Easing
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.FiniteAnimationSpec
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.VisibilityThreshold
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp

/**
 * 动效 token（参考阿福记账的那套动效语言）。
 *
 * 数值与电脑端 `desktop/motion.py` 同一套语义：
 *   - 有方向：同级切换时新页面从它在导航里的相对方位进入
 *   - 有纵深：离开的页面略微缩小、进入的页面由略大收敛到原尺寸
 *   - 有落位感：弹簧或减速曲线，不用线性匀速
 *
 * **所有转场都从这里取时长与曲线**，页面里不要写魔数。
 */
object Motion {

    // ---------------- 时长 ----------------
    /** 同级切换（底部标签之间）：≤ 200ms */
    const val SWITCH_MS = 220

    /** 层级进入/返回（标签页 → 二级页）：≤ 260ms */
    const val ENTER_MS = 260

    /** 面板/浮层出现的时长 */
    const val OVERLAY_MS = 260

    /** 微交互（按钮、卡片选中）的时长 */
    const val TAP_MS = 120

    // ---------------- 幅度 ----------------
    /**
     * 同级切换的水平位移占屏宽的比例。
     * 0.12 是上限：能看出方向，但不像整屏翻页。实际用 0.08。
     */
    const val SWITCH_SLIDE_RATIO = 0.08f

    /** 层级进入时，底层页面缩小到的比例（6% 的纵深） */
    const val PUSH_BACK_SCALE = 0.94f

    /** 进入页自己的缩放起点：必须 ≥ 1.0，避免内缩时四周露出底色 */
    const val ENTER_SCALE_FROM = 1.04f

    /** 层级进入时底层的压暗程度 */
    const val PUSH_BACK_DIM = 0.5f

    // ---------------- 曲线 ----------------
    /** 减速曲线：用于「进入」，落位干净利落 */
    val decelerate: Easing = FastOutSlowInEasing

    /** 弹簧：同级切换有回弹感但不晃；damping 越大越不弹 */
    fun <T> springy(): FiniteAnimationSpec<T> = spring(
        dampingRatio = 0.86f,
        stiffness = Spring.StiffnessMediumLow,
    )

    /** 位移专用的弹簧（IntOffset 需要线程阈值，否则到不了终点会有 1px 抖动） */
    fun slideSpec(): FiniteAnimationSpec<IntOffset> = spring(
        dampingRatio = 0.9f,
        stiffness = Spring.StiffnessMediumLow,
        visibilityThreshold = IntOffset.VisibilityThreshold,
    )

    /** 层级进入：减速曲线，26ms 级别落位 */
    fun <T> enter(): FiniteAnimationSpec<T> = tween(durationMillis = ENTER_MS, easing = decelerate)

    /** 淡入淡出 / 微交互 */
    fun <T> fade(ms: Int = SWITCH_MS): FiniteAnimationSpec<T> = tween(ms, easing = decelerate)

    // ---------------- 尺寸 ----------------
    /** 底栏选中胶囊的宽度（与游戏图标比例相关） */
    val barIndicatorWidth = 56.dp
    val barIndicatorHeight = 36.dp
}

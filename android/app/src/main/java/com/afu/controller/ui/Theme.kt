package com.afu.controller.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import com.afu.controller.R

/**
 * 设计 token：与电脑端 desktop/tokens.py 一一对应。
 *
 * 常量名两边刻意保持相同，`scripts/check_design_tokens.py` 会逐项比对，
 * 只改一端会直接报错。改这里时同步改 tokens.py。
 */

// ---------------- 品牌色（深海奶油糖果） ----------------
val BRAND = Color(0xFF3A6FF0)
val BRAND_DEEP = Color(0xFF2750C8)
val BRAND_SOFT = Color(0xFF6D93FF)
val ACCENT = Color(0xFFFF7E6B)
val ACCENT_DEEP = Color(0xFFF0604B)

// ---------------- 状态色 ----------------
val OK = Color(0xFF3BA55D)
val WARN = Color(0xFFE0A030)
val DANGER = Color(0xFFE5484D)
val INFO = Color(0xFF3E9EF0)

// ---------------- 浅色：深海奶油糖果 ----------------
val LIGHT_BG = Color(0xFFFFF6EA)
val LIGHT_SURFACE = Color(0xFFFFFFFF)
val LIGHT_SURFACE_2 = Color(0xFFFFF1E0)
val LIGHT_LINE = Color(0xFFF2DFC6)
val LIGHT_TEXT = Color(0xFF1B2436)
val LIGHT_MUTED = Color(0xFF6B7488)

// ---------------- 深色：深夜海沟 ----------------
val DARK_BG = Color(0xFF0D1526)
val DARK_SURFACE = Color(0xFF16213A)
val DARK_SURFACE_2 = Color(0xFF1D2A47)
val DARK_LINE = Color(0xFF25334F)
val DARK_TEXT = Color(0xFFEDF2FF)
val DARK_MUTED = Color(0xFF94A3BF)

// ---------------- 形状 ----------------
const val RADIUS_CARD = 22
const val RADIUS_CONTROL = 999
const val RADIUS_CHIP = 12

// ---------------- 间距 ----------------
const val GAP_XS = 4
const val GAP_S = 8
const val GAP_M = 12
const val GAP_L = 20
const val GAP_XL = 28

// ---------------- 动效 ----------------
const val MOTION_SWITCH_MS = 220
const val MOTION_ENTER_MS = 220
const val MOTION_TAP_MS = 140
const val MOTION_SLIDE_RATIO = 0.06f

/** 标题、按钮文字、时间与数字用的圆体（随包分发，OFL 授权）。 */
val CandyFontFamily = FontFamily(Font(R.font.zcool_kuaile, FontWeight.Normal))

/**
 * 业务界面额外用到的颜色。
 *
 * Material3 的 colorScheme 没有「描边色」「次级卡片」这些槽位，
 * 但卡片式界面需要，所以单独放常量。
 */
object OrchColors {
    val success = OK
    val warning = WARN
    val danger = DANGER
    val running = INFO
}

private val LightColors = lightColorScheme(
    primary = BRAND,
    onPrimary = Color.White,
    secondary = ACCENT,
    tertiary = ACCENT,
    background = LIGHT_BG,
    onBackground = LIGHT_TEXT,
    surface = LIGHT_SURFACE,
    onSurface = LIGHT_TEXT,
    surfaceVariant = LIGHT_SURFACE_2,
    onSurfaceVariant = LIGHT_MUTED,
    outline = LIGHT_LINE,
    error = DANGER,
)

private val DarkColors = darkColorScheme(
    primary = BRAND_SOFT,
    onPrimary = Color(0xFF06111F),
    secondary = Color(0xFFFF9A82),
    tertiary = Color(0xFFFF9A82),
    background = DARK_BG,
    onBackground = DARK_TEXT,
    surface = DARK_SURFACE,
    onSurface = DARK_TEXT,
    surfaceVariant = DARK_SURFACE_2,
    onSurfaceVariant = DARK_MUTED,
    outline = DARK_LINE,
    error = Color(0xFFFF8A8E),
)

// 行高比默认略松：中文在手机上需要更宽的行距才好读
private val CandyTypography = Typography(
    headlineMedium = TextStyle(
        fontFamily = CandyFontFamily, fontSize = 24.sp, lineHeight = 32.sp,
    ),
    headlineSmall = TextStyle(
        fontFamily = CandyFontFamily, fontSize = 20.sp, lineHeight = 28.sp,
    ),
    titleMedium = TextStyle(
        fontFamily = CandyFontFamily, fontSize = 16.sp, lineHeight = 24.sp,
    ),
    titleLarge = TextStyle(
        fontFamily = CandyFontFamily, fontSize = 18.sp, lineHeight = 26.sp,
    ),
    bodyLarge = TextStyle(fontSize = 15.sp, lineHeight = 23.sp),
    bodyMedium = TextStyle(fontSize = 14.sp, lineHeight = 22.sp),
    bodySmall = TextStyle(fontSize = 12.5.sp, lineHeight = 19.sp),
    labelLarge = TextStyle(
        fontFamily = CandyFontFamily, fontSize = 15.sp, lineHeight = 20.sp,
    ),
    labelMedium = TextStyle(fontSize = 12.sp, lineHeight = 16.sp),
    labelSmall = TextStyle(fontSize = 11.sp, lineHeight = 15.sp),
)

@Composable
fun GameOrchTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (dark) DarkColors else LightColors,
        typography = CandyTypography,
        content = content,
    )
}

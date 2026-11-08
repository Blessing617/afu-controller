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


// ---- 游戏页外壳：状态条、底部操作条 ----

@Composable
internal fun GameShell(
    vm: AppViewModel,
    state: UiState,
    games: List<String>,
    tab: Int,
    direction: Int,
    onSelectTab: (Int) -> Unit,
    onOpenSettings: () -> Unit,
    onOpenChain: () -> Unit,
    onQuickEditTasks: (String) -> Unit,
    showChainPage: Boolean = false,
    onCloseChain: () -> Unit = {},
) {
    val game = games.getOrElse(tab) { games[0] }

    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        TopStatusBar(
            connected = state.connected,
            onOpenSettings = onOpenSettings,
        )

        // 画面区：**固定不滚动**。
        //
        // 之前它和内容一起塞进 verticalScroll，结果往上滑内容时画面跟着滚走了，
        // 用户要一边看画面一边点下面的按钮就很难受。现在画面钉在顶部，
        // 只有它下面的内容区滚动。
        //
        // 编排模式下画面跟「正在跑的那个游戏」而不是列表选中的 tab；
        // 没在跑时退回链上第一个启用的步骤。
        val screenGame = if (showChainPage) {
            val run = state.chainRun
            run?.steps?.getOrNull(run.currentIndex)?.game?.takeIf { it.isNotBlank() }
                ?: state.chain.steps.firstOrNull { it.enabled }?.game
                ?: game
        } else {
            game
        }
        Column(Modifier.padding(horizontal = 18.dp, vertical = 4.dp)) {
            ScreenSection(vm = vm, state = state, game = screenGame)
        }

        // 中间可滚动区：只放随标签变化的内容
        Column(
            Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 18.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {

            if (showChainPage) {
                // 编排内容：和游戏页同一块区域，共用顶栏与底栏
                ChainContent(vm = vm, modifier = Modifier.fillMaxWidth())
            } else {
                // 只随标签变化的部分：本游戏的可用性说明与次要操作
                DirectionalTabContent(
                    targetState = tab,
                    direction = direction,
                    modifier = Modifier.fillMaxWidth(),
                ) { index ->
                    GameExtraContent(
                        vm = vm,
                        state = state,
                        game = games.getOrElse(index) { games[0] },
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
        }

        // 固定层：主操作栏
        //
        // 这里把「这个游戏在编排里选了哪些子任务」算出来传给按钮，
        // 让用户点之前就知道会跑什么（而不是永远写「开始一键长草」）。
        val pickedIds = state.chain.steps
            .filter { it.game == game && it.enabled }
            .flatMap { it.tasks }
            .distinct()
        val pickedNames = pickedIds.map { id ->
            state.capabilities[game]?.items?.firstOrNull { it.id == id }?.name ?: id
        }
        if (showChainPage) {
            ChainActionSection(vm = vm)
        } else {
            PrimaryActionBar(
                vm = vm,
                state = state,
                game = game,
                pickedTaskNames = pickedNames,
                onEditTasks = { onQuickEditTasks(game) },
            )
        }

        // 底栏：三个游戏
        GameBottomBar(
            games = games,
            current = if (showChainPage) -1 else tab,
            readyMap = state.games,
            onSelect = onSelectTab,
            onOpenChain = onOpenChain,
            chainSelected = showChainPage,
        )
        Spacer(Modifier.navigationBarsPadding())
    }
}

/** 顶部状态条：连接状态 + 设置入口。 */
@Composable
internal fun TopStatusBar(connected: Boolean, onOpenSettings: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(start = 18.dp, end = 10.dp, top = 8.dp, bottom = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CandyPill(
            text = if (connected) "已连接" else "未连接",
            color = if (connected) OK else DANGER,
        )
        Spacer(Modifier.weight(1f))
        Box(
            Modifier
                .size(36.dp)
                .clip(RoundedCornerShape(50))
                .background(MaterialTheme.colorScheme.surface)
                .clickable(onClick = onOpenSettings),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                Icons.Default.Settings,
                contentDescription = "设置",
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(19.dp),
            )
        }
    }
}

/**
 * 底栏：三个游戏。
 *
 * 三个按键**始终都在**，缺依赖的游戏也能点进去看到「缺什么」，
 * 只是图标下面加一行小字标记，避免「少一个按键」这种让人困惑的界面。
 */
@Composable
internal fun GameBottomBar(
    games: List<String>,
    current: Int,
    readyMap: Map<String, GameInfo>,
    onSelect: (Int) -> Unit,
    onOpenChain: () -> Unit,
    chainSelected: Boolean = false,
) {
    Surface(
        color = MaterialTheme.colorScheme.background,
        tonalElevation = 0.dp,
        shadowElevation = 0.dp,
        shape = RoundedCornerShape(topStart = 22.dp, topEnd = 22.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 6.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            games.forEachIndexed { index, key ->
                val selected = current == index
                val ready = readyMap[key]?.ready == true
                val accent = MaterialTheme.colorScheme.primary
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .clip(RoundedCornerShape(16.dp))
                        .clickable(
                            interactionSource = remember { MutableInteractionSource() },
                            indication = ripple(),
                        ) { onSelect(index) }
                        .padding(vertical = 6.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(3.dp),
                ) {
                    Box(
                        modifier = Modifier
                            .size(52.dp, 36.dp)
                            .clip(RoundedCornerShape(50))
                            .background(
                                if (selected) accent.copy(alpha = 0.16f) else Color.Transparent
                            ),
                        contentAlignment = Alignment.Center,
                    ) {
                        Image(
                            painter = painterResource(GAME_ICONS.getValue(key)),
                            contentDescription = GAME_LABELS[key],
                            modifier = Modifier
                                .size(32.dp)
                                .clip(RoundedCornerShape(9.dp))
                                .graphicsLayer { alpha = if (ready) 1f else 0.45f },
                            contentScale = ContentScale.Crop,
                        )
                    }
                    Text(
                        GAME_LABELS[key] ?: key,
                        fontSize = 11.sp,
                        maxLines = 1,
                        fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
                        color = if (selected) accent else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    // 缺依赖的加一行小字：让用户一眼知道哪个现在点了也跑不了
                    if (!ready && readyMap.isNotEmpty()) {
                        Text(
                            "未就绪",
                            fontSize = 9.sp,
                            lineHeight = 10.sp,
                            color = MaterialTheme.colorScheme.error,
                            maxLines = 1,
                            overflow = TextOverflow.Clip,
                        )
                    } else {
                        Spacer(Modifier.height(10.dp))
                    }
                }
            }

            // 第 4 个：编排。用 APP 自己的图标，和三个游戏并列在底栏，
            // 而不是藏在「设置」里 —— 编排是本程序的核心功能之一，不该藏起来。
            val chainAccent = MaterialTheme.colorScheme.primary
            Column(
                modifier = Modifier
                    .weight(1f)
                    .clip(RoundedCornerShape(16.dp))
                    .clickable(
                        interactionSource = remember { MutableInteractionSource() },
                        indication = ripple(),
                    ) { onOpenChain() }
                    .padding(vertical = 6.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(3.dp),
            ) {
                Box(
                    modifier = Modifier
                        .size(52.dp, 36.dp)
                        .clip(RoundedCornerShape(50))
                        .background(
                            if (chainSelected) chainAccent.copy(alpha = 0.16f)
                            else Color.Transparent
                        ),
                    contentAlignment = Alignment.Center,
                ) {
                    // 用前景层 PNG 而不是 @mipmap/ic_launcher：
                    // 后者是 adaptive-icon 的 XML，Compose 的 painterResource 只认
                    // VectorDrawable 或位图，加载 XML 会直接崩（IllegalArgumentException）。
                    Image(
                        painter = painterResource(R.drawable.ic_launcher_foreground),
                        contentDescription = "编排",
                        modifier = Modifier
                            .size(32.dp)
                            .clip(RoundedCornerShape(9.dp)),
                        contentScale = ContentScale.Crop,
                    )
                }
                Text(
                    "编排",
                    fontSize = 11.sp,
                    maxLines = 1,
                    fontWeight = if (chainSelected) FontWeight.SemiBold else FontWeight.Normal,
                    color = if (chainSelected) chainAccent
                    else MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(10.dp))
            }
        }
    }
}


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


// ---- 连接页 ----

@Composable
internal fun ConnectScreen(
    vm: AppViewModel,
    modifier: Modifier = Modifier,
    canGoBack: Boolean = false,
    onBack: () -> Unit = {},
) {
    val state by vm.state.collectAsStateWithLifecycle()
    var code by remember { mutableStateOf("") }
    val scope = androidx.compose.runtime.rememberCoroutineScope()
    var searching by remember { mutableStateOf(false) }
    var found by remember { mutableStateOf<List<com.afu.controller.data.FoundHost>>(emptyList()) }
    var scanned by remember { mutableStateOf(false) }

    fun doScan(autoFill: Boolean) {
        scope.launch {
            searching = true
            val hosts = runCatching { com.afu.controller.data.Discovery.scan() }
                .getOrDefault(emptyList())
            found = hosts
            searching = false
            scanned = true
            if (autoFill && hosts.size == 1 && state.address.isBlank()) {
                vm.setAddress("${hosts[0].address}:${hosts[0].port}")
            }
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            // Scaffold 的 innerPadding 已经含系统栏高度，这里再加会多出一条空白
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (canGoBack) {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                }
            }
            Text(
                "连接电脑",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
            )
        }

        // 说明按「你现在在哪」分两种，而不是默认假设你在家。
        Text(
            "不管你在家还是在外面，都填电脑窗口上显示的地址。\n" +
                "在外面填「公网地址」那个 https:// 开头的固定网址（手机不用装任何软件），" +
                "在家可以点下面的搜索自动找。",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        androidx.compose.material3.OutlinedTextField(
            value = state.address,
            onValueChange = vm::setAddress,
            label = { Text("电脑地址") },
            placeholder = { Text("https://xxx.ts.net  或  192.168.x.x:${com.afu.controller.data.DEFAULT_PORT}") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Text(
            "这个地址显示在电脑端应用窗口的「手机怎么连上这台电脑」卡片里，直接照抄。",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        CandyButton(
            text = when {
                state.connecting -> "连接中…"
                state.connected -> "重新连接"
                else -> "连接"
            },
            onClick = vm::connect,
            enabled = !state.connecting,
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp),
            kind = CandyKind.Primary,
            fontSize = 17.sp,
        )

        // 连接失败原因常驻显示。放这里而不是用 toast：
        // 用户需要边看提示边改地址，toast 一闪就没了。
        if (state.connectError.isNotBlank()) {
            Surface(
                color = MaterialTheme.colorScheme.errorContainer,
                shape = RoundedCornerShape(12.dp),
            ) {
                Text(
                    state.connectError,
                    modifier = Modifier.padding(12.dp),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onErrorContainer,
                )
            }
        }

        HorizontalDivider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.4f))
        Text(
            "在同一个 WiFi 下？",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            "手机和电脑连同一个路由器时，可以自动搜到，不用手抄地址。",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        when {
            searching -> Row(verticalAlignment = Alignment.CenterVertically) {
                CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                Spacer(Modifier.width(8.dp))
                Text("正在搜索同一网络里的电脑…", style = MaterialTheme.typography.bodySmall)
            }
            found.isNotEmpty() -> Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(
                    "找到 ${found.size} 台电脑，点一下就能连：",
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Medium,
                    style = MaterialTheme.typography.bodySmall,
                )
                found.forEach { host ->
                    androidx.compose.material3.OutlinedButton(
                        onClick = {
                            vm.setAddress("${host.address}:${host.port}")
                            vm.connect()
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Icon(Icons.Default.Link, null, Modifier.size(16.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("${host.address}:${host.port}")
                    }
                }
            }
            scanned -> Text(
                "没搜到电脑。搜索只能在同一个 WiFi 下用——如果你在外面，" +
                    "请改用电脑窗口上「公网地址」那个 https:// 开头的网址。" +
                    "或者可能是电脑端没打开。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
            )
        }

        androidx.compose.material3.OutlinedButton(
            onClick = { doScan(false) },
            enabled = !searching,
            modifier = Modifier
                .fillMaxWidth()
                .height(46.dp),
        ) {
            Icon(Icons.Default.Refresh, null, Modifier.size(16.dp))
            Spacer(Modifier.width(6.dp))
            Text("搜索同一网络里的电脑")
        }

        if (state.connected) {
            HorizontalDivider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.4f))
            val health = state.health
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(9.dp).background(OK, CircleShape))
                Spacer(Modifier.width(8.dp))
                Text(
                    "已连上电脑 · 服务版本 ${health?.version ?: "-"}",
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Medium,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            androidx.compose.material3.OutlinedTextField(
                value = code,
                onValueChange = { input -> code = input.filter { it.isDigit() }.take(6) },
                label = { Text("配对码（6 位，显示在电脑窗口上）") },
                singleLine = true,
                keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(
                    keyboardType = androidx.compose.ui.text.input.KeyboardType.Number
                ),
                modifier = Modifier.fillMaxWidth(),
            )
            CandyButton(
                text = if (state.pairing) "配对中…" else "配对",
                onClick = { vm.pair(code) },
                enabled = code.length == 6 && !state.pairing,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp),
                kind = CandyKind.Accent,
                fontSize = 16.sp,
            )
            if (state.pairError.isNotBlank()) {
                Surface(
                    color = MaterialTheme.colorScheme.errorContainer,
                    shape = RoundedCornerShape(12.dp),
                ) {
                    Text(
                        state.pairError,
                        modifier = Modifier.padding(12.dp),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onErrorContainer,
                    )
                }
            }
            CandyButton(
                text = "断开连接",
                onClick = vm::disconnect,
                modifier = Modifier.fillMaxWidth(),
                kind = CandyKind.Ghost,
            )

            // 已配对时给一个明确的出口：不用找返回键/手势也能回去。
            // 用户反馈过「连上了却退不出连接页」，多一个显式按钮比只靠返回键靠谱。
            if (canGoBack) {
                CandyButton(
                    text = "完成，回到主界面",
                    onClick = onBack,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(56.dp),
                    kind = CandyKind.Primary,
                    fontSize = 17.sp,
                )
            }
        }

        HorizontalDivider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.4f))
        Surface(
            color = MaterialTheme.colorScheme.surfaceVariant,
            shape = RoundedCornerShape(12.dp),
        ) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(
                    "出门在外连不上？",
                    fontWeight = FontWeight.SemiBold,
                    style = MaterialTheme.typography.bodyMedium,
                )
                Text(
                    "电脑端要先开好 Funnel（一次性配置，地址固定不变）。\n" +
                        "开好后电脑窗口的「公网地址」会显示一个 https:// 开头的网址，" +
                        "把它填到上面即可——手机这边不需要装任何软件。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Spacer(Modifier.height(24.dp))
    }
}

/**
 * 设置页：通用能力的唯一入口。
 *
 * 「连接设置」在这里而不是每个游戏页里 —— 它是通用能力，和玩哪个游戏无关。
 */

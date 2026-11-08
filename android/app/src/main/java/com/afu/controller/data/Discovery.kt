package com.afu.controller.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import java.net.Inet4Address
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.net.Socket

/**
 * 服务端的首选端口。
 *
 * 放在顶层是因为 [FoundHost] 的默认值也要用到它；
 * 电脑上这个端口经常被别的程序占走，服务端会自动换一个邻近的（见 server 的 resolve_port）。
 */
const val DEFAULT_PORT = 8765

/** 同一网络里找到的一台电脑。 */
data class FoundHost(val address: String, val port: Int = DEFAULT_PORT)

/**
 * 自动发现电脑：扫本机所在的 /24 网段。
 *
 * 为什么用扫描而不是让用户填 IP：换电脑、换手机、路由器重新分配地址时，
 * 用户不该知道也不该记对方地址。服务端 `/api/health` 是公开接口，
 * 扫到端口后请求一次就能确认「这就是阿福代肝控制器」，不需要服务端配合。
 *
 * 端口为什么不写死：电脑上 8765 常被别的程序占走，服务端会自动改用邻近端口
 * （见 server 的 resolve_port）。所以这里对每台机器扫一小段端口，
 * 否则用户会遇到「电脑上明明跑着，手机上却搜不到」。
 */
object Discovery {
    /** 从默认端口往后试几个，要和服务端 pick_port 的跨度对得上。 */
    private const val PORT_SPAN = 20

    private const val CONCURRENCY = 48
    private const val CONNECT_TIMEOUT_MS = 220
    private const val READ_TIMEOUT_MS = 700

    /** 本机在局域网里的 IPv4 地址（优先私有网段）。 */
    fun localIpv4(): String? {
        return try {
            NetworkInterface.getNetworkInterfaces().toList()
                .filter { it.isUp && !it.isLoopback }
                .flatMap { it.inetAddresses.toList() }
                .filterIsInstance<Inet4Address>()
                .mapNotNull { it.hostAddress }
                .firstOrNull { isPrivate(it) }
        } catch (_: Exception) {
            null
        }
    }

    private fun isPrivate(ip: String): Boolean =
        ip.startsWith("192.168.") ||
            ip.startsWith("10.") ||
            ip.matches(Regex("""172\.(1[6-9]|2\d|3[01])\..*"""))

    /** 扫一遍本网段，返回所有跑着阿福代肝控制器的地址（含实际端口）。 */
    suspend fun scan(basePort: Int = DEFAULT_PORT): List<FoundHost> = withContext(Dispatchers.IO) {
        val local = localIpv4() ?: return@withContext emptyList()
        val prefix = local.substringBeforeLast('.', "")
        if (prefix.isEmpty()) return@withContext emptyList()

        val found = mutableListOf<FoundHost>()
        for (batch in (1..254).chunked(CONCURRENCY)) {
            coroutineScope {
                batch.map { last ->
                    async {
                        val ip = "$prefix.$last"
                        probeHost(ip, basePort)
                    }
                }.awaitAll().filterNotNull().forEach { found.add(it) }
            }
        }
        // 同一台机器只保留一个（理论上也只会命中一个端口）
        found.distinctBy { it.address }.sortedBy { it.address }
    }

    /** 对一台机器的端口段做探测，命中就返回。先试默认端口，再试邻近的。 */
    private fun probeHost(ip: String, basePort: Int): FoundHost? {
        for (offset in 0..PORT_SPAN) {
            val port = basePort + offset
            if (port > 65535) break
            if (probe(ip, port)) return FoundHost(ip, port)
        }
        return null
    }

    /** 连上端口，请求 /api/health，确认对方是我们的服务。 */
    private fun probe(ip: String, port: Int): Boolean {
        return try {
            Socket().use { socket ->
                socket.connect(InetSocketAddress(ip, port), CONNECT_TIMEOUT_MS)
                socket.soTimeout = READ_TIMEOUT_MS
                socket.getOutputStream().apply {
                    write(
                        "GET /api/health HTTP/1.0\r\nHost: $ip\r\nConnection: close\r\n\r\n"
                            .toByteArray()
                    )
                    flush()
                }
                val text = socket.getInputStream().readBytes().toString(Charsets.UTF_8)
                text.contains("\"ok\":true")
            }
        } catch (_: Exception) {
            false
        }
    }
}

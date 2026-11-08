package com.afu.controller.data

import android.content.Context
import androidx.datastore.core.handlers.ReplaceFileCorruptionHandler
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.emptyPreferences
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import java.io.IOException

/**
 * DataStore 实例。
 *
 * `corruptionHandler` 是必须的：文件一旦损坏（断电、存储异常、外部工具写坏），
 * 没有这个处理器时 DataStore 会抛 CorruptionException 直接把 APP 崩掉。
 * 有它则会丢掉坏数据、用空配置重建，用户最多重新填一次连接信息。
 */
private val Context.store by preferencesDataStore(
    name = "afu_controller",
    corruptionHandler = ReplaceFileCorruptionHandler { emptyPreferences() },
)

/** 本地保存连接信息：地址与 token。 */
class SettingsRepo(private val context: Context) {

    private object Keys {
        val ADDRESS = stringPreferencesKey("address")
        val TOKEN = stringPreferencesKey("token")
        // 断网时改的任务链暂存在这里，等重连后补发
        val PENDING_CHAIN = stringPreferencesKey("pending_chain")
    }

    /**
     * 读偏好。除了 corruptionHandler 兜底，这里再捕获一次 IOException：
     * 磁盘临时不可读时不要让界面直接崩，按「没有配置」处理即可。
     */
    private suspend fun prefs(): Preferences =
        try {
            context.store.data.first()
        } catch (_: IOException) {
            emptyPreferences()
        }

    suspend fun load(): Pair<String, String> {
        val p = prefs()
        return (p[Keys.ADDRESS] ?: "") to (p[Keys.TOKEN] ?: "")
    }

    suspend fun saveAddress(address: String) {
        context.store.edit { it[Keys.ADDRESS] = address }
    }

    suspend fun saveToken(token: String) {
        context.store.edit { it[Keys.TOKEN] = token }
    }

    suspend fun clearToken() {
        context.store.edit { it.remove(Keys.TOKEN) }
    }

    // ---------- 任务链的离线暂存 ----------
    /** 存一份「还没同步到电脑」的任务链 JSON。 */
    suspend fun savePendingChain(json: String) {
        context.store.edit { it[Keys.PENDING_CHAIN] = json }
    }

    /** 取出待同步的任务链（没有就是空串）。 */
    suspend fun pendingChain(): String {
        val p = prefs()
        return p[Keys.PENDING_CHAIN] ?: ""
    }

    /** 同步成功，清掉待发。 */
    suspend fun clearPendingChain() {
        context.store.edit { it.remove(Keys.PENDING_CHAIN) }
    }

    suspend fun addressFlow(): kotlinx.coroutines.flow.Flow<String> =
        context.store.data
            .catch { emit(emptyPreferences()) }
            .map { it[Keys.ADDRESS] ?: "" }
}

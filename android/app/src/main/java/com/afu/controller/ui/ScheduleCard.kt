package com.afu.controller.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.afu.controller.data.ScheduleConfig

private const val MAX_TIMES = 8

/**
 * 编排页的「定时执行」卡片。
 *
 * 设计取向：这里的每一次改动都立即保存到电脑端（和编排页「改了就存」的习惯一致），
 * 不做「保存」按钮——少一个步骤，也少一次「忘了点保存」。
 *
 * 关闭开关时如果正在跑，会先问一句「要不要连正在跑的一起停掉」：
 * 用户的原话是「关的时候电脑上要全部关掉」，所以默认就停，但要给个反悔的机会。
 */
@Composable
internal fun ScheduleCard(vm: AppViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    val schedule = state.schedule
    var pickerOpen by remember { mutableStateOf(false) }
    // 正在编辑的时间点；null 表示「新增」
    var editingSlot by remember { mutableStateOf<String?>(null) }
    var confirmStop by remember { mutableStateOf(false) }

    val running = state.current != null || state.chainRun?.state == "running"

    fun save(
        enabled: Boolean = schedule.enabled,
        times: List<String> = schedule.times,
        days: List<Int> = schedule.weekdays,
    ) {
        vm.saveSchedule(ScheduleConfig(enabled = enabled, times = times, weekdays = days))
    }

    fun commitSlot(slot: String) {
        val editing = editingSlot
        val next = when {
            editing == null -> schedule.times + slot
            editing == slot -> schedule.times
            else -> schedule.times.map { if (it == editing) slot else it }
        }
        save(times = next.distinct().sorted())
        pickerOpen = false
        editingSlot = null
    }

    CandyCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text("定时执行", style = MaterialTheme.typography.titleMedium)
                Text(
                    if (schedule.enabled) "到点会先关掉所有游戏和工具，再从头跑整条链"
                    else "开启后会按下面的时间自动跑整条链",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            CandySwitch(
                checked = schedule.enabled,
                enabled = !state.scheduleBusy,
                onCheckedChange = { on ->
                    if (!on && running) confirmStop = true else save(enabled = on)
                },
            )
        }

        if (schedule.enabled) {
            // ---- 时间点 ----
            if (schedule.times.isEmpty()) {
                Text(
                    "还没有时间点，点下面「添加时间」",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
            schedule.times.chunked(3).forEach { chunk ->
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    chunk.forEach { slot ->
                        CandyChip(
                            text = slot,
                            onDelete = { save(times = schedule.times - slot) },
                            onClick = {
                                editingSlot = slot
                                pickerOpen = true
                            },
                        )
                    }
                }
            }
            CandyButton(
                text = if (schedule.times.size >= MAX_TIMES) "最多 8 个时间点" else "＋ 添加时间",
                onClick = {
                    editingSlot = null
                    pickerOpen = true
                },
                kind = CandyKind.Ghost,
                enabled = schedule.times.size < MAX_TIMES,
            )

            // ---- 星期 ----
            WeekdayRow(
                selected = schedule.weekdays,
                onToggle = { day ->
                    val next = if (day in schedule.weekdays) {
                        schedule.weekdays - day
                    } else {
                        (schedule.weekdays + day).sorted()
                    }
                    save(days = next)
                },
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                CandyPill(
                    text = if (schedule.weekdays.isEmpty()) "每天执行" else "仅选中的星期",
                    color = if (schedule.weekdays.isEmpty()) OK else INFO,
                )
                schedule.nextRun?.let {
                    Text(
                        "  下次运行：$it",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }

    if (pickerOpen) {
        CandyTimePickerSheet(
            title = if (editingSlot == null) "添加时间" else "修改时间",
            initial = editingSlot ?: "08:00",
            onConfirm = { commitSlot(it) },
            onDismiss = {
                pickerOpen = false
                editingSlot = null
            },
        )
    }

    if (confirmStop) {
        CandyDialog(
            title = "关掉定时，要一起停掉正在跑的任务吗？",
            message = "选「停止并关闭」会停止当前任务，并关掉电脑上所有游戏与工具（含模拟器）。\n选「只关定时」则让这次跑完。",
            confirmText = "停止并关闭",
            dismissText = "只关定时",
            onConfirm = {
                confirmStop = false
                save(enabled = false)
                vm.stopScheduleNow { msg -> vm.toast(msg) }
            },
            onDismiss = {
                confirmStop = false
                save(enabled = false)
            },
            danger = true,
        )
    }
}

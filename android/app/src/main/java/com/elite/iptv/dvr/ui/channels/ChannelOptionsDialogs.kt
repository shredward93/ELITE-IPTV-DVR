package com.elite.iptv.dvr.ui.channels

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ButtonDefaults as MaterialButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.elite.iptv.dvr.api.Channel
import com.elite.iptv.dvr.ui.theme.EliteColors
import com.elite.iptv.dvr.viewmodel.MainViewModel
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun ChannelOptionsDialog(
    channel: Channel,
    onDismiss: () -> Unit,
    onWatchLive: () -> Unit,
    onTvGuide: () -> Unit,
    onRecordNow: () -> Unit,
    onScheduleLater: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Text(
                channel.name,
                color = EliteColors.paper,
                fontSize = 20.sp,
                fontWeight = FontWeight.SemiBold,
            )
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("Channel actions", color = EliteColors.paperMuted, fontSize = 14.sp)
                TextButton(
                    onClick = { onWatchLive(); onDismiss() },
                    colors = MaterialButtonDefaults.textButtonColors(contentColor = EliteColors.paper),
                ) { Text("▶  Watch live", fontSize = 16.sp) }
                TextButton(
                    onClick = { onTvGuide(); onDismiss() },
                    colors = MaterialButtonDefaults.textButtonColors(contentColor = EliteColors.signal),
                ) { Text("TV Guide (this channel)", fontSize = 16.sp) }
                TextButton(
                    onClick = { onRecordNow(); onDismiss() },
                    colors = MaterialButtonDefaults.textButtonColors(contentColor = EliteColors.signal),
                ) { Text("●  Record now…", fontSize = 16.sp) }
                TextButton(
                    onClick = { onScheduleLater(); onDismiss() },
                    colors = MaterialButtonDefaults.textButtonColors(contentColor = EliteColors.signal),
                ) { Text("Schedule later…", fontSize = 16.sp) }
            }
        },
        confirmButton = {},
        dismissButton = {
            TextButton(
                onClick = onDismiss,
                colors = MaterialButtonDefaults.textButtonColors(contentColor = EliteColors.paperMuted),
            ) { Text("Cancel") }
        },
        containerColor = EliteColors.surface2,
        titleContentColor = EliteColors.paper,
        textContentColor = EliteColors.paper,
    )
}

@Composable
fun RecordNowChannelDialog(
    channel: Channel,
    viewModel: MainViewModel,
    durationMins: Int,
    onDurationChange: (Int) -> Unit,
    onDismiss: () -> Unit,
    onResultNote: (String) -> Unit,
) {
    val scope = rememberCoroutineScope()
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Record now — ${channel.name}", color = EliteColors.paper) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Duration", color = EliteColors.paperMuted, fontSize = 14.sp)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(30, 60, 120, 180).forEach { mins ->
                        TextButton(
                            onClick = { onDurationChange(mins) },
                            colors = MaterialButtonDefaults.textButtonColors(
                                contentColor = if (durationMins == mins) EliteColors.signal else EliteColors.paper,
                            ),
                        ) { Text("${mins}m") }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    scope.launch {
                        runCatching {
                            viewModel.scheduleRecording(
                                channelId = channel.id,
                                channelName = channel.name,
                                startTime = "NOW",
                                durationMins = durationMins,
                            )
                        }.onSuccess {
                            onResultNote("Recording started (${durationMins} min).")
                        }.onFailure {
                            onResultNote("Record failed: ${it.message}")
                        }
                    }
                    onDismiss()
                },
                colors = MaterialButtonDefaults.textButtonColors(contentColor = EliteColors.signal),
            ) { Text("Start") }
        },
        dismissButton = {
            TextButton(
                onClick = onDismiss,
                colors = MaterialButtonDefaults.textButtonColors(contentColor = EliteColors.paperMuted),
            ) { Text("Cancel") }
        },
        containerColor = EliteColors.surface2,
        titleContentColor = EliteColors.paper,
        textContentColor = EliteColors.paper,
    )
}

@Composable
fun ScheduleLaterChannelDialog(
    channel: Channel,
    viewModel: MainViewModel,
    offsetMins: Int,
    onOffsetChange: (Int) -> Unit,
    durationMins: Int,
    onDurationChange: (Int) -> Unit,
    onDismiss: () -> Unit,
    onResultNote: (String) -> Unit,
) {
    val scope = rememberCoroutineScope()
    val startLabel = SimpleDateFormat("hh:mm a", Locale.US).format(
        Date(System.currentTimeMillis() + offsetMins.toLong() * 60_000L),
    )
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Schedule — ${channel.name}", color = EliteColors.paper) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Start in", color = EliteColors.paperMuted, fontSize = 13.sp)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(15, 30, 60, 120).forEach { off ->
                        TextButton(
                            onClick = { onOffsetChange(off) },
                            colors = MaterialButtonDefaults.textButtonColors(
                                contentColor = if (offsetMins == off) EliteColors.signal else EliteColors.paper,
                            ),
                        ) { Text("+$off m") }
                    }
                }
                Text("Duration", color = EliteColors.paperMuted, fontSize = 13.sp)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(30, 60, 120, 180).forEach { mins ->
                        TextButton(
                            onClick = { onDurationChange(mins) },
                            colors = MaterialButtonDefaults.textButtonColors(
                                contentColor = if (durationMins == mins) EliteColors.signal else EliteColors.paper,
                            ),
                        ) { Text("${mins}m") }
                    }
                }
                Text("Starts at $startLabel", color = EliteColors.paper2, fontSize = 13.sp)
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    scope.launch {
                        runCatching {
                            viewModel.scheduleRecording(
                                channelId = channel.id,
                                channelName = channel.name,
                                startTime = startLabel,
                                durationMins = durationMins,
                            )
                        }.onSuccess {
                            onResultNote("Scheduled $startLabel for ${durationMins} min.")
                        }.onFailure {
                            onResultNote("Schedule failed: ${it.message}")
                        }
                    }
                    onDismiss()
                },
                colors = MaterialButtonDefaults.textButtonColors(contentColor = EliteColors.signal),
            ) { Text("Schedule") }
        },
        dismissButton = {
            TextButton(
                onClick = onDismiss,
                colors = MaterialButtonDefaults.textButtonColors(contentColor = EliteColors.paperMuted),
            ) { Text("Cancel") }
        },
        containerColor = EliteColors.surface2,
        titleContentColor = EliteColors.paper,
        textContentColor = EliteColors.paper,
    )
}

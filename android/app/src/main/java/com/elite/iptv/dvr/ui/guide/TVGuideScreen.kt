@file:OptIn(ExperimentalTvMaterial3Api::class)

package com.elite.iptv.dvr.ui.guide

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ButtonDefaults as MaterialButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.BorderStroke
import androidx.tv.material3.Border
import androidx.tv.material3.Button
import androidx.tv.material3.ButtonDefaults
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.ExperimentalTvMaterial3Api
import androidx.tv.material3.OutlinedButton
import androidx.tv.material3.OutlinedButtonDefaults
import androidx.tv.material3.Surface
import com.elite.iptv.dvr.api.EpgListing
import com.elite.iptv.dvr.ui.theme.EliteColors
import com.elite.iptv.dvr.ui.theme.TvFocusDefaults
import com.elite.iptv.dvr.viewmodel.MainViewModel
import kotlinx.coroutines.launch

private data class TvGuideRenderItem(
    val listing: EpgListing,
    val startMs: Long,
    val stopMs: Long,
)

@Composable
fun TVGuideScreen(
    viewModel: MainViewModel,
    channelId: String,
    channelName: String,
    onPlayLive: () -> Unit,
    onBack: () -> Unit,
) {
    LaunchedEffect(channelId) { viewModel.loadEpgForChannel(channelId) }
    BackHandler { onBack() }

    val scope = rememberCoroutineScope()
    var scheduleDialog by remember { mutableStateOf<EpgListing?>(null) }
    var scheduleStatus by remember { mutableStateOf("") }
    var recordNowDurationDialog by remember { mutableStateOf(false) }
    var recordNowDurationMins by remember { mutableStateOf(120) }
    var futureScheduleDialog by remember { mutableStateOf(false) }
    var futureStartOffsetMins by remember { mutableStateOf(30) }
    var futureDurationMins by remember { mutableStateOf(120) }
    var quickScheduleStatus by remember { mutableStateOf("") }
    val anchorMs = remember(channelId) { System.currentTimeMillis() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(EliteColors.ink)
            .padding(24.dp),
    ) {
        // ── Header ────────────────────────────────────────────────────────────
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text(channelName, color = EliteColors.paper, fontSize = 24.sp, fontWeight = FontWeight.Bold)
                Text("TV Guide", color = EliteColors.paperMuted, fontSize = 14.sp, letterSpacing = 0.8.sp)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedButton(
                    onClick = { recordNowDurationDialog = true },
                    modifier = Modifier.height(44.dp),
                    scale = OutlinedButtonDefaults.scale(scale = 1f, focusedScale = 1.055f, pressedScale = 1f),
                    border = OutlinedButtonDefaults.border(
                        border = Border(
                            border = BorderStroke(1.5.dp, EliteColors.rule),
                            inset = 0.dp,
                            shape = RoundedCornerShape(10.dp),
                        ),
                        focusedBorder = Border(
                            border = BorderStroke(2.dp, EliteColors.signal),
                            inset = 0.dp,
                            shape = RoundedCornerShape(10.dp),
                        ),
                    ),
                    colors = OutlinedButtonDefaults.colors(
                        containerColor = Color.Transparent,
                        contentColor = EliteColors.paperMuted,
                        focusedContainerColor = EliteColors.surface3,
                        focusedContentColor = EliteColors.signal,
                        pressedContainerColor = EliteColors.surface3,
                        pressedContentColor = EliteColors.paper,
                    ),
                ) {
                    Text("● Record Now", fontSize = 15.sp, fontWeight = FontWeight.Medium)
                }
                OutlinedButton(
                    onClick = { futureScheduleDialog = true },
                    modifier = Modifier.height(44.dp),
                    scale = OutlinedButtonDefaults.scale(scale = 1f, focusedScale = 1.055f, pressedScale = 1f),
                    border = OutlinedButtonDefaults.border(
                        border = Border(
                            border = BorderStroke(1.5.dp, EliteColors.rule),
                            inset = 0.dp,
                            shape = RoundedCornerShape(10.dp),
                        ),
                        focusedBorder = Border(
                            border = BorderStroke(2.dp, EliteColors.signal),
                            inset = 0.dp,
                            shape = RoundedCornerShape(10.dp),
                        ),
                    ),
                    colors = OutlinedButtonDefaults.colors(
                        containerColor = Color.Transparent,
                        contentColor = EliteColors.paperMuted,
                        focusedContainerColor = EliteColors.surface3,
                        focusedContentColor = EliteColors.signal,
                        pressedContainerColor = EliteColors.surface3,
                        pressedContentColor = EliteColors.paper,
                    ),
                ) {
                    Text("Schedule...", fontSize = 15.sp, fontWeight = FontWeight.Medium)
                }
                Button(
                    onClick = onPlayLive,
                    modifier = Modifier.height(44.dp).width(140.dp),
                    scale = ButtonDefaults.scale(scale = 1f, focusedScale = 1.055f, pressedScale = 1f),
                    border = ButtonDefaults.border(
                        border = Border.None,
                        focusedBorder = Border(
                            border = BorderStroke(2.dp, EliteColors.paper),
                            inset = 0.dp,
                            shape = RoundedCornerShape(10.dp),
                        ),
                    ),
                    colors = ButtonDefaults.colors(
                        containerColor        = EliteColors.signal,
                        contentColor          = EliteColors.ink,
                        focusedContainerColor = EliteColors.signal,
                        focusedContentColor   = EliteColors.ink,
                        pressedContainerColor = EliteColors.surface3,
                        pressedContentColor   = EliteColors.paper,
                    ),
                ) {
                    Text("▶  Watch Live", fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                }
                OutlinedButton(
                    onClick = onBack,
                    modifier = Modifier.height(44.dp),
                    scale = OutlinedButtonDefaults.scale(scale = 1f, focusedScale = 1.055f, pressedScale = 1f),
                    border = OutlinedButtonDefaults.border(
                        border = Border(
                            border = BorderStroke(1.5.dp, EliteColors.rule),
                            inset = 0.dp,
                            shape = RoundedCornerShape(10.dp),
                        ),
                        focusedBorder = Border(
                            border = BorderStroke(2.dp, EliteColors.signal),
                            inset = 0.dp,
                            shape = RoundedCornerShape(10.dp),
                        ),
                    ),
                    colors = OutlinedButtonDefaults.colors(
                        containerColor = Color.Transparent,
                        contentColor = EliteColors.paperMuted,
                        focusedContainerColor = EliteColors.surface3,
                        focusedContentColor = EliteColors.signal,
                        pressedContainerColor = EliteColors.surface3,
                        pressedContentColor = EliteColors.paper,
                    ),
                ) {
                    Text("← Back", fontSize = 16.sp)
                }
            }
        }

        Spacer(Modifier.height(16.dp))
        if (quickScheduleStatus.isNotBlank()) {
            Text(
                text = quickScheduleStatus,
                color = EliteColors.ok,
                fontSize = 13.sp,
                modifier = Modifier.padding(bottom = 10.dp),
            )
        }

        if (viewModel.epgListings.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = EliteColors.signal)
            }
            return@Column
        }

        // ── EPG Listings ──────────────────────────────────────────────────────
        val renderItems = remember(viewModel.epgListings) {
            viewModel.epgListings.map { listing ->
                TvGuideRenderItem(
                    listing = listing,
                    startMs = parseEpgMs(listing.start),
                    stopMs = parseEpgMs(listing.stop),
                )
            }
        }

        LazyColumn(
            contentPadding = PaddingValues(bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(renderItems, key = { it.listing.start ?: it.listing.title }) { item ->
                val isNow = item.startMs <= anchorMs && item.stopMs > anchorMs
                EpgRow(item.listing, isNow = isNow, onRecord = { scheduleDialog = item.listing })
            }
        }
    }

    // ── Schedule confirmation dialog ──────────────────────────────────────────
    scheduleDialog?.let { listing ->
        AlertDialog(
            onDismissRequest = { scheduleDialog = null; scheduleStatus = "" },
            title = { Text("Schedule Recording", color = EliteColors.paper) },
            text = {
                Column {
                    Text(listing.title, fontWeight = FontWeight.Bold, fontSize = 18.sp, color = EliteColors.paper)
                    Text(
                        "${formatEpgTime(listing.start)} – ${formatEpgTime(listing.stop)}",
                        color = EliteColors.paperMuted,
                        fontSize = 15.sp,
                    )
                    if (scheduleStatus.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        Text(scheduleStatus, color = EliteColors.ok, fontSize = 15.sp)
                    }
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        scope.launch {
                            try {
                                viewModel.scheduleRecording(
                                    channelId    = channelId,
                                    channelName  = channelName,
                                    startTime    = schedulerStartTimeFromEpg(listing.start),
                                    durationMins = epgDurationMins(listing.start, listing.stop),
                                )
                                scheduleStatus = "Recording scheduled."
                            } catch (e: Exception) {
                                scheduleStatus = "Failed: ${e.message}"
                            }
                        }
                    },
                    colors = MaterialButtonDefaults.textButtonColors(
                        contentColor = EliteColors.signal,
                        disabledContentColor = EliteColors.paperMuted,
                    ),
                ) { Text("Record") }
            },
            dismissButton = {
                TextButton(
                    onClick = { scheduleDialog = null; scheduleStatus = "" },
                    colors = MaterialButtonDefaults.textButtonColors(
                        contentColor = EliteColors.paperMuted,
                        disabledContentColor = EliteColors.paperMuted,
                    ),
                ) { Text("Cancel") }
            },
            containerColor = EliteColors.surface2,
            titleContentColor = EliteColors.paper,
            textContentColor = EliteColors.paper,
        )
    }

    if (recordNowDurationDialog) {
        AlertDialog(
            onDismissRequest = { recordNowDurationDialog = false },
            title = { Text("Record Now Duration", color = EliteColors.paper) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Choose duration", color = EliteColors.paperMuted, fontSize = 14.sp)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf(30, 60, 120, 180).forEach { mins ->
                            TextButton(
                                onClick = { recordNowDurationMins = mins },
                                colors = MaterialButtonDefaults.textButtonColors(
                                    contentColor = if (recordNowDurationMins == mins) EliteColors.signal else EliteColors.paper,
                                ),
                            ) {
                                Text("${mins}m")
                            }
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
                                    channelId = channelId,
                                    channelName = channelName,
                                    startTime = "NOW",
                                    durationMins = recordNowDurationMins,
                                )
                            }.onSuccess {
                                quickScheduleStatus = "Recording started for ${recordNowDurationMins} min."
                            }.onFailure {
                                quickScheduleStatus = "Record now failed: ${it.message}"
                            }
                        }
                        recordNowDurationDialog = false
                    },
                    colors = MaterialButtonDefaults.textButtonColors(contentColor = EliteColors.signal),
                ) { Text("Start") }
            },
            dismissButton = {
                TextButton(
                    onClick = { recordNowDurationDialog = false },
                    colors = MaterialButtonDefaults.textButtonColors(contentColor = EliteColors.paperMuted),
                ) { Text("Cancel") }
            },
            containerColor = EliteColors.surface2,
            titleContentColor = EliteColors.paper,
            textContentColor = EliteColors.paper,
        )
    }

    if (futureScheduleDialog) {
        val startTimeText = scheduleTimeLabelFromOffset(futureStartOffsetMins)
        AlertDialog(
            onDismissRequest = { futureScheduleDialog = false },
            title = { Text("Schedule Future Recording", color = EliteColors.paper) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Start", color = EliteColors.paperMuted, fontSize = 13.sp)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf(15, 30, 60, 120).forEach { offset ->
                            TextButton(
                                onClick = { futureStartOffsetMins = offset },
                                colors = MaterialButtonDefaults.textButtonColors(
                                    contentColor = if (futureStartOffsetMins == offset) EliteColors.signal else EliteColors.paper,
                                ),
                            ) { Text("+$offset m") }
                        }
                    }
                    Text("Duration", color = EliteColors.paperMuted, fontSize = 13.sp)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf(30, 60, 120, 180).forEach { mins ->
                            TextButton(
                                onClick = { futureDurationMins = mins },
                                colors = MaterialButtonDefaults.textButtonColors(
                                    contentColor = if (futureDurationMins == mins) EliteColors.signal else EliteColors.paper,
                                ),
                            ) { Text("${mins}m") }
                        }
                    }
                    Text(
                        "Will start at $startTimeText",
                        color = EliteColors.paper2,
                        fontSize = 13.sp,
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        scope.launch {
                            runCatching {
                                viewModel.scheduleRecording(
                                    channelId = channelId,
                                    channelName = channelName,
                                    startTime = startTimeText,
                                    durationMins = futureDurationMins,
                                )
                            }.onSuccess {
                                quickScheduleStatus = "Scheduled $startTimeText for ${futureDurationMins} min."
                            }.onFailure {
                                quickScheduleStatus = "Schedule failed: ${it.message}"
                            }
                        }
                        futureScheduleDialog = false
                    },
                    colors = MaterialButtonDefaults.textButtonColors(contentColor = EliteColors.signal),
                ) { Text("Schedule") }
            },
            dismissButton = {
                TextButton(
                    onClick = { futureScheduleDialog = false },
                    colors = MaterialButtonDefaults.textButtonColors(contentColor = EliteColors.paperMuted),
                ) { Text("Cancel") }
            },
            containerColor = EliteColors.surface2,
            titleContentColor = EliteColors.paper,
            textContentColor = EliteColors.paper,
        )
    }
}

@Composable
private fun EpgRow(listing: EpgListing, isNow: Boolean, onRecord: () -> Unit) {
    Surface(
        onClick = onRecord,
        modifier = Modifier.fillMaxWidth().height(72.dp),
        shape = ClickableSurfaceDefaults.shape(shape = RoundedCornerShape(6.dp)),
        colors = ClickableSurfaceDefaults.colors(
            containerColor        = EliteColors.inkSoft,
            focusedContainerColor = EliteColors.surface3,
        ),
        scale = TvFocusDefaults.surfaceScaleCard,
        border = ClickableSurfaceDefaults.border(
            border = Border.None,
            focusedBorder = Border(
                border = BorderStroke(2.dp, EliteColors.signal),
                inset = 0.dp,
                shape = RoundedCornerShape(6.dp),
            ),
        ),
    ) {
        Row(
            modifier = Modifier.fillMaxSize(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .width(3.dp)
                    .fillMaxHeight()
                    .background(if (isNow) EliteColors.signal else EliteColors.rule),
            )
            Row(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxHeight()
                    .padding(horizontal = 14.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        listing.title,
                        color = if (isNow) EliteColors.signal else EliteColors.paper,
                        fontSize = 16.sp,
                        fontWeight = if (isNow) FontWeight.SemiBold else FontWeight.Medium,
                    )
                    listing.description?.takeIf { it.isNotBlank() }?.let {
                        Text(it, color = EliteColors.paper2, fontSize = 12.sp, maxLines = 1)
                    }
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(formatEpgTime(listing.start), color = EliteColors.paperMuted, fontSize = 12.sp)
                    Text("– ${formatEpgTime(listing.stop)}", color = EliteColors.paperMuted, fontSize = 12.sp)
                }
            }
        }
    }
}

// formatEpgTime and epgDurationMins are defined in EpgGuideScreen.kt (same package, internal)

private fun scheduleTimeLabelFromOffset(offsetMins: Int): String {
    val whenMs = System.currentTimeMillis() + offsetMins.toLong() * 60_000L
    return java.text.SimpleDateFormat("hh:mm a", java.util.Locale.US).format(java.util.Date(whenMs))
}

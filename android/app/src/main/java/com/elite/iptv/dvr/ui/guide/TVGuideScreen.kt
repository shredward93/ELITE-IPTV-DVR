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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.tv.material3.Button
import androidx.tv.material3.ButtonDefaults
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.ExperimentalTvMaterial3Api
import androidx.tv.material3.Surface
import com.elite.iptv.dvr.api.EpgListing
import com.elite.iptv.dvr.ui.theme.EliteColors
import com.elite.iptv.dvr.viewmodel.MainViewModel
import kotlinx.coroutines.launch

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
                Button(
                    onClick = onPlayLive,
                    colors = ButtonDefaults.colors(
                        containerColor        = EliteColors.signal,
                        focusedContainerColor = EliteColors.surface3,
                    ),
                    modifier = Modifier.height(44.dp).width(140.dp),
                ) {
                    Text("▶  Watch Live", color = EliteColors.ink, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                }
                TextButton(onClick = onBack) {
                    Text("← Back", color = EliteColors.signal, fontSize = 16.sp)
                }
            }
        }

        Spacer(Modifier.height(16.dp))

        if (viewModel.epgListings.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = EliteColors.signal)
            }
            return@Column
        }

        // ── EPG Listings ──────────────────────────────────────────────────────
        LazyColumn(
            contentPadding = PaddingValues(bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(viewModel.epgListings, key = { it.start ?: it.title }) { listing ->
                val startMs = parseEpgMs(listing.start)
                val stopMs = parseEpgMs(listing.stop)
                val isNow = startMs <= anchorMs && stopMs > anchorMs
                EpgRow(listing, isNow = isNow, onRecord = { scheduleDialog = listing })
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
                TextButton(onClick = {
                    scope.launch {
                        try {
                            viewModel.scheduleRecording(
                                channelId    = channelId,
                                channelName  = channelName,
                                startTime    = listing.start ?: "",
                                durationMins = epgDurationMins(listing.start, listing.stop),
                            )
                            scheduleStatus = "Recording scheduled."
                        } catch (e: Exception) {
                            scheduleStatus = "Failed: ${e.message}"
                        }
                    }
                }) { Text("Record", color = EliteColors.signal) }
            },
            dismissButton = {
                TextButton(onClick = { scheduleDialog = null; scheduleStatus = "" }) {
                    Text("Cancel", color = EliteColors.paperMuted)
                }
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

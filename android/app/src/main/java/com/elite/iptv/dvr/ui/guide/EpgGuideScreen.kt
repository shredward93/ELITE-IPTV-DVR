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
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
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
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.BorderStroke
import androidx.tv.material3.Border
import androidx.tv.material3.Button
import androidx.tv.material3.ButtonDefaults
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.ExperimentalTvMaterial3Api
import androidx.tv.material3.Surface
import com.elite.iptv.dvr.api.Category
import com.elite.iptv.dvr.api.Channel
import com.elite.iptv.dvr.api.EpgListing
import com.elite.iptv.dvr.ui.theme.EliteColors
import com.elite.iptv.dvr.ui.theme.TvFocusDefaults
import com.elite.iptv.dvr.viewmodel.MainViewModel
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

private const val DP_PER_MIN = 4   // dp per minute in the timeline
/** Channel gutter width — aligns with [GuideTimeHeader] and TiviMate-like dense rail. */
private val ChannelGutterDp = 176.dp

@Composable
fun EpgGuideScreen(
    viewModel: MainViewModel,
    onChannelPlay: (id: String, name: String) -> Unit,
    onBack: () -> Unit,
) {
    BackHandler { onBack() }

    var selectedCategory by remember { mutableStateOf<Category?>(null) }
    var scheduleTarget by remember { mutableStateOf<Pair<Channel, EpgListing>?>(null) }
    var scheduleStatus by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()

    val anchorMs = remember { System.currentTimeMillis() }
    val windowStartMs = anchorMs - GuideConstants.WINDOW_PRE_MINUTES * 60_000L
    val windowEndMs = windowStartMs + GuideConstants.WINDOW_TOTAL_MINUTES * 60_000L

    LaunchedEffect(Unit) { viewModel.loadCategories() }

    LaunchedEffect(selectedCategory) {
        val cat = selectedCategory ?: return@LaunchedEffect
        viewModel.loadChannelsByCategory(cat.categoryId)
    }

    LaunchedEffect(viewModel.categoryChannels) {
        val ids = viewModel.categoryChannels.take(48).map { it.id }
        if (ids.isNotEmpty()) viewModel.loadGuideEpgBatched(ids)
    }

    Row(modifier = Modifier.fillMaxSize().background(EliteColors.ink)) {

        // ── Left sidebar: categories (TiviMate-style narrow rail) ─────────────
        Column(
            modifier = Modifier
                .width(200.dp)
                .fillMaxHeight()
                .background(EliteColors.inkSoft),
        ) {
            Text(
                text = "CATEGORIES",
                color = EliteColors.paperMuted,
                fontSize = 10.sp,
                fontWeight = FontWeight.SemiBold,
                letterSpacing = 1.6.sp,
                modifier = Modifier.padding(start = 14.dp, top = 18.dp, bottom = 8.dp),
            )
            LazyColumn(
                contentPadding = PaddingValues(bottom = 16.dp),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                items(viewModel.categories, key = { it.categoryId }) { cat ->
                    CategoryItem(
                        category = cat,
                        selected = cat.categoryId == selectedCategory?.categoryId,
                        onClick  = { selectedCategory = cat },
                    )
                }
            }
        }

        // ── Right panel: TV guide grid ────────────────────────────────────────
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(EliteColors.surface),
        ) {
            // Header bar
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(EliteColors.surface2)
                    .padding(horizontal = 14.dp, vertical = 10.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = selectedCategory?.categoryName ?: "TV Guide",
                    color = EliteColors.paper,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = onBack,
                        modifier = Modifier.height(40.dp),
                        scale = ButtonDefaults.scale(scale = 1f, focusedScale = 1.055f, pressedScale = 1f),
                        border = ButtonDefaults.border(
                            border = Border.None,
                            focusedBorder = Border(
                                border = BorderStroke(2.dp, EliteColors.signal),
                                inset = 0.dp,
                                shape = RoundedCornerShape(10.dp),
                            ),
                        ),
                        colors = ButtonDefaults.colors(
                            containerColor        = EliteColors.surface3,
                            contentColor          = EliteColors.paper,
                            focusedContainerColor = EliteColors.signal,
                            focusedContentColor   = EliteColors.ink,
                            pressedContainerColor = EliteColors.signal,
                            pressedContentColor   = EliteColors.ink,
                        ),
                    ) {
                        Text("← Back", fontSize = 15.sp)
                    }
                }
            }

            when {
                selectedCategory == null -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text(
                            "← Select a category to browse the guide",
                            color = EliteColors.paperMuted,
                            fontSize = 16.sp,
                        )
                    }
                }
                viewModel.categoryChannels.isEmpty() -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = EliteColors.signal)
                    }
                }
                else -> {
                    // Time header row
                    GuideTimeHeader(windowStartMs = windowStartMs, windowEndMs = windowEndMs)

                    // Channel + programme rows
                    LazyColumn(
                        contentPadding = PaddingValues(bottom = 24.dp),
                        verticalArrangement = Arrangement.spacedBy(2.dp),
                    ) {
                        items(viewModel.categoryChannels.take(48), key = { it.id }) { ch ->
                            GuideChannelRow(
                                channel       = ch,
                                listings      = viewModel.guideEpg[ch.id] ?: emptyList(),
                                windowStartMs = windowStartMs,
                                windowEndMs   = windowEndMs,
                                nowMs         = anchorMs,
                                onPlayLive    = { onChannelPlay(ch.id, ch.name) },
                                onRecord      = { listing ->
                                    scheduleStatus = ""
                                    scheduleTarget = ch to listing
                                },
                            )
                        }
                    }
                }
            }
        }
    }

    // ── Schedule confirmation dialog ──────────────────────────────────────────
    scheduleTarget?.let { (ch, listing) ->
        AlertDialog(
            onDismissRequest = { scheduleTarget = null; scheduleStatus = "" },
            title = { Text("Schedule Recording", color = EliteColors.paper) },
            text = {
                Column {
                    Text(listing.title, fontWeight = FontWeight.Bold, fontSize = 18.sp, color = EliteColors.paper)
                    Text(
                        "${formatEpgTime(listing.start)} – ${formatEpgTime(listing.stop)}",
                        color = EliteColors.paperMuted,
                        fontSize = 15.sp,
                    )
                    Text("Channel: ${ch.name}", color = EliteColors.paper2, fontSize = 14.sp)
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
                                    channelId    = ch.id,
                                    channelName  = ch.name,
                                    startTime    = schedulerStartTimeFromEpg(listing.start),
                                    durationMins = epgDurationMins(listing.start, listing.stop),
                                )
                                scheduleStatus = "Scheduled."
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
                    onClick = { scheduleTarget = null; scheduleStatus = "" },
                    colors = MaterialButtonDefaults.textButtonColors(
                        contentColor = EliteColors.paperMuted,
                        disabledContentColor = EliteColors.paperMuted,
                    ),
                ) { Text("Cancel") }
            },
            containerColor      = EliteColors.surface2,
            titleContentColor   = EliteColors.paper,
            textContentColor    = EliteColors.paper,
        )
    }
}

// ── Category sidebar item ─────────────────────────────────────────────────────

@Composable
private fun CategoryItem(category: Category, selected: Boolean, onClick: () -> Unit) {
    val interactionSource = remember { MutableInteractionSource() }
    val focused by interactionSource.collectIsFocusedAsState()
    val onSignalBg = selected || focused
    Surface(
        onClick = onClick,
        modifier = Modifier
            .fillMaxWidth()
            .height(44.dp),
        shape = ClickableSurfaceDefaults.shape(shape = RoundedCornerShape(0.dp)),
        colors = ClickableSurfaceDefaults.colors(
            containerColor        = if (selected) EliteColors.signal else Color.Transparent,
            focusedContainerColor = EliteColors.signal,
        ),
        scale = TvFocusDefaults.surfaceScaleRail,
        border = ClickableSurfaceDefaults.border(
            border = Border.None,
            focusedBorder = Border(
                border = BorderStroke(2.dp, EliteColors.signal),
                inset = 0.dp,
                shape = RoundedCornerShape(0.dp),
            ),
        ),
        interactionSource = interactionSource,
    ) {
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (selected) {
                Text("►", color = EliteColors.ink, fontSize = 11.sp)
                Spacer(Modifier.width(6.dp))
            }
            Text(
                text     = category.categoryName,
                color    = if (onSignalBg) EliteColors.ink else EliteColors.paper,
                fontSize = 15.sp,
                fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

// ── Time header ───────────────────────────────────────────────────────────────

@Composable
private fun GuideTimeHeader(windowStartMs: Long, windowEndMs: Long) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(30.dp)
            .background(EliteColors.inkSoft)
            .padding(bottom = 1.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // Gutter to align with channel name column
        Box(Modifier.width(ChannelGutterDp))

        // Time slots: every 30 minutes across the window
        val spanMin = ((windowEndMs - windowStartMs) / 60_000L).toInt().coerceAtLeast(30)
        (0 until (spanMin / 30)).forEach { i ->
            val slotMs = windowStartMs + i * 30 * 60_000L
            Text(
                text     = formatMs(slotMs),
                color    = EliteColors.paperMuted,
                fontSize = 11.sp,
                letterSpacing = 0.6.sp,
                modifier = Modifier.width((30 * DP_PER_MIN).dp).padding(start = 6.dp),
            )
        }
    }
}

// ── Channel row ───────────────────────────────────────────────────────────────

@Composable
private fun GuideChannelRow(
    channel: Channel,
    listings: List<EpgListing>,
    windowStartMs: Long,
    windowEndMs: Long,
    nowMs: Long,
    onPlayLive: () -> Unit,
    onRecord: (EpgListing) -> Unit,
) {
    val visible = remember(listings, windowStartMs, windowEndMs) {
        listings.filter { l ->
            val stop  = parseEpgMs(l.stop)
            val start = parseEpgMs(l.start)
            stop > windowStartMs && start < windowEndMs
        }
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(58.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // Channel name — press to watch live
        val gutterInteraction = remember { MutableInteractionSource() }
        val gutterFocused by gutterInteraction.collectIsFocusedAsState()
        Surface(
            onClick = onPlayLive,
            modifier = Modifier.width(ChannelGutterDp).height(58.dp),
            shape  = ClickableSurfaceDefaults.shape(shape = RoundedCornerShape(0.dp)),
            colors = ClickableSurfaceDefaults.colors(
                containerColor        = EliteColors.inkSoft,
                focusedContainerColor = EliteColors.signal,
            ),
            scale = TvFocusDefaults.surfaceScaleCompact,
            border = ClickableSurfaceDefaults.border(
                border = Border.None,
                focusedBorder = Border(
                    border = BorderStroke(2.dp, EliteColors.signal),
                    inset = 0.dp,
                    shape = RoundedCornerShape(0.dp),
                ),
            ),
            interactionSource = gutterInteraction,
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 10.dp),
                contentAlignment = Alignment.CenterStart,
            ) {
                Text(
                    text     = channel.name,
                    color    = if (gutterFocused) EliteColors.ink else EliteColors.paper,
                    fontSize = 13.sp,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }

        // Programme cells
        if (visible.isEmpty()) {
            Box(
                modifier = Modifier
                    .weight(1f)
                    .height(58.dp)
                    .background(EliteColors.ink),
                contentAlignment = Alignment.CenterStart,
            ) {
                Text("  No guide data", color = EliteColors.paperMuted, fontSize = 12.sp)
            }
        } else {
            LazyRow(
                modifier              = Modifier.weight(1f).height(58.dp).background(EliteColors.ink),
                horizontalArrangement = Arrangement.spacedBy(2.dp),
                contentPadding        = PaddingValues(end = 8.dp),
            ) {
                items(visible, key = { it.start ?: it.title }) { listing ->
                    val startMs      = parseEpgMs(listing.start)
                    val stopMs       = parseEpgMs(listing.stop)
                    val clampedStart = maxOf(startMs, windowStartMs)
                    val clampedStop  = minOf(stopMs, windowEndMs)
                    val durationMin  = ((clampedStop - clampedStart) / 60_000f).coerceAtLeast(15f)
                    val widthDp: Dp  = (durationMin * DP_PER_MIN).dp.coerceAtLeast(60.dp)
                    val isNow        = startMs <= nowMs && stopMs > nowMs

                    ProgramCell(
                        listing = listing,
                        widthDp = widthDp,
                        isNow   = isNow,
                        onClick = { onRecord(listing) },
                    )
                }
            }
        }
    }
}

// ── Programme cell ────────────────────────────────────────────────────────────

@Composable
private fun ProgramCell(
    listing: EpgListing,
    widthDp: Dp,
    isNow: Boolean,
    onClick: () -> Unit,
) {
    Surface(
        onClick  = onClick,
        modifier = Modifier.width(widthDp).height(58.dp),
        shape    = ClickableSurfaceDefaults.shape(shape = RoundedCornerShape(3.dp)),
        colors   = ClickableSurfaceDefaults.colors(
            containerColor        = if (isNow) EliteColors.inkSoft else EliteColors.surface,
            focusedContainerColor = EliteColors.surface3,
        ),
        scale = TvFocusDefaults.surfaceScaleCompact,
        border = ClickableSurfaceDefaults.border(
            border = Border.None,
            focusedBorder = Border(
                border = BorderStroke(2.dp, EliteColors.signal),
                inset = 0.dp,
                shape = RoundedCornerShape(3.dp),
            ),
        ),
    ) {
        Row(
            modifier = Modifier.fillMaxSize(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (isNow) {
                Box(
                    modifier = Modifier
                        .width(3.dp)
                        .height(58.dp)
                        .background(EliteColors.signal),
                )
            }
            Column(
                modifier = Modifier
                    .weight(1f)
                    .padding(horizontal = 8.dp, vertical = 5.dp),
                verticalArrangement = Arrangement.Center,
            ) {
                Text(
                    text     = listing.title,
                    color    = if (isNow) EliteColors.signal else EliteColors.paper,
                    fontSize = 13.sp,
                    fontWeight = if (isNow) FontWeight.SemiBold else FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text     = "${formatEpgTime(listing.start)}–${formatEpgTime(listing.stop)}",
                    color    = EliteColors.paperMuted,
                    fontSize = 10.sp,
                )
            }
        }
    }
}

// ── Time utilities ────────────────────────────────────────────────────────────

private val _epgSdf = ThreadLocal.withInitial {
    SimpleDateFormat("yyyyMMddHHmmss", Locale.US).apply {
        timeZone = TimeZone.getTimeZone("UTC")
    }
}

internal fun parseEpgMs(raw: String?): Long {
    if (raw == null) return 0L
    return try {
        _epgSdf.get()!!.parse(raw.trim().take(14))?.time ?: 0L
    } catch (_: Exception) { 0L }
}

private fun formatMs(ms: Long): String =
    SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date(ms))

internal fun formatEpgTime(raw: String?): String {
    if (raw == null) return "--:--"
    return try {
        val s = raw.trim()
        "${s.substring(8, 10)}:${s.substring(10, 12)}"
    } catch (_: Exception) { raw }
}

internal fun epgDurationMins(start: String?, stop: String?): Int {
    if (start == null || stop == null) return 60
    return try {
        fun toMins(s: String): Long {
            val h = s.substring(8, 10).toLong()
            val m = s.substring(10, 12).toLong()
            val d = s.substring(6, 8).toLong()
            return d * 1440 + h * 60 + m
        }
        (toMins(stop) - toMins(start)).coerceAtLeast(30).toInt()
    } catch (_: Exception) { 60 }
}

internal fun schedulerStartTimeFromEpg(raw: String?): String {
    val startMs = parseEpgMs(raw)
    val nowMs = System.currentTimeMillis()
    if (startMs <= nowMs + 60_000L) return "NOW"
    return SimpleDateFormat("hh:mm a", Locale.US).format(Date(startMs))
}

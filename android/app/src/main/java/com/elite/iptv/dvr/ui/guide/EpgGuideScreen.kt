@file:OptIn(ExperimentalTvMaterial3Api::class)

package com.elite.iptv.dvr.ui.guide

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Image
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
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.TileMode
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.res.painterResource
import android.view.KeyEvent as AndroidKeyEvent
import androidx.tv.material3.Button
import androidx.tv.material3.ButtonDefaults
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.ExperimentalTvMaterial3Api
import androidx.tv.material3.Surface
import androidx.tv.material3.SurfaceDefaults
import com.elite.iptv.dvr.api.Category
import com.elite.iptv.dvr.api.Channel
import com.elite.iptv.dvr.api.EpgListing
import com.elite.iptv.dvr.R
import com.elite.iptv.dvr.viewmodel.MainViewModel
import androidx.compose.ui.graphics.Brush
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

private const val DP_PER_MIN = 4   // dp per minute in the timeline
private const val WINDOW_MINS = 180 // 3-hour window
private const val PRE_MINS = 30     // show 30 min before now
private val CHANNEL_COL_WIDTH = 200.dp

private data class VisibleListing(
    val listing: EpgListing,
    val startMs: Long,
    val stopMs: Long,
    val timeLabel: String,
)

@Composable
fun EpgGuideScreen(
    viewModel: MainViewModel,
    onChannelPlay: (id: String, name: String) -> Unit,
    onBack: () -> Unit,
) {
    BackHandler { onBack() }

    var selectedCategory by remember { mutableStateOf<Category?>(null) }
    val guideListState = rememberLazyListState()

    val nowMs = System.currentTimeMillis()
    val windowStartMs = nowMs - PRE_MINS * 60_000L
    val guideTimeLabel = remember(nowMs) { formatGuideDateTime(nowMs) }

    // Tivimate-style: prefetch ALL guide data in background on first open
    LaunchedEffect(Unit) {
        if (viewModel.allCategories.isEmpty()) {
            viewModel.prefetchAllGuideData()
        }
    }

    // Select first category once categories are loaded
    LaunchedEffect(viewModel.allCategories) {
        if (selectedCategory == null && viewModel.allCategories.isNotEmpty()) {
            selectedCategory = viewModel.allCategories.first()
        }
    }

    // Instant category switch - just reveals pre-loaded data, no network call
    // If the selected category is not in the preloaded map yet, fall back to a single category load.
    LaunchedEffect(selectedCategory, viewModel.channelsByCategory) {
        val cat = selectedCategory ?: return@LaunchedEffect
        val cachedChannels = viewModel.channelsByCategory[cat.categoryId]
        if (cachedChannels.isNullOrEmpty()) {
            viewModel.loadGuideBundle(categoryId = cat.categoryId, limit = 24, refresh = false)
        } else {
            viewModel.switchGuideCategory(cat.categoryId)
        }
    }

    val effectiveChannels = viewModel.categoryChannels

    Box(modifier = Modifier.fillMaxSize().background(Color.Black)) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 27.dp, vertical = 18.dp),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(
                        brush = Brush.horizontalGradient(
                            colors = listOf(
                                Color(0xFF1A1A1A),
                                Color(0xFF2A2A2A),
                                Color(0xFF1A1A1A)
                            ),
                            tileMode = TileMode.Clamp
                        )
                    )
                    .padding(horizontal = 27.dp, vertical = 14.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .size(40.dp)
                            .background(Color(0xFFF89344), CircleShape),
                        contentAlignment = Alignment.Center
                    ) {
                        Image(
                            painter = painterResource(id = R.drawable.elite_logo),
                            contentDescription = "ELITE IPTV DVR logo",
                            modifier = Modifier.size(32.dp)
                        )
                    }

                    Column {
                        Text(
                            text = "TV Guide",
                            color = Color.White,
                            fontSize = 28.sp,
                            fontWeight = FontWeight.Bold,
                            lineHeight = 32.sp,
                        )
                        Text(
                            text = selectedCategory?.categoryName ?: "Choose a category",
                            color = Color(0xFFCCCCCC),
                            fontSize = 16.sp,
                        )
                    }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = guideTimeLabel,
                        color = Color(0xFFF89344),
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Medium,
                    )
                    Button(
                        onClick = onBack,
                        colors = ButtonDefaults.colors(
                            containerColor        = Color(0xFF2E2E2E),
                            focusedContainerColor = Color(0xFFF89344),
                        ),
                        modifier = Modifier.height(40.dp),
                    ) {
                        Text("← Back", color = Color.White, fontSize = 15.sp)
                    }
                }
            }

            Spacer(Modifier.height(14.dp))

            Row(modifier = Modifier.weight(1f)) {
                Surface(
                    modifier = Modifier
                        .width(248.dp)
                        .fillMaxHeight(),
                    shape = RoundedCornerShape(18.dp),
                    colors = SurfaceDefaults.colors(containerColor = Color(0xFF111111)),
                ) {
                    Column(modifier = Modifier.fillMaxSize().padding(horizontal = 14.dp, vertical = 14.dp)) {
                        Text(
                            text = "Categories",
                            color = Color(0xFFE0E0E0),
                            fontSize = 18.sp,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Spacer(Modifier.height(12.dp))
                        if (viewModel.allCategories.isEmpty() || viewModel.guidePrefetching) {
                            // Show prefetch progress
                            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                    CircularProgressIndicator(color = Color(0xFFF89344))
                                    Spacer(Modifier.height(8.dp))
                                    val (loaded, total) = viewModel.guidePrefetchProgress
                                    if (total > 0) {
                                        Text(
                                            text = "Loading $loaded/$total...",
                                            color = Color(0xFFAAAAAA),
                                            fontSize = 12.sp,
                                        )
                                    }
                                }
                            }
                        } else {
                            // Only restore focus to selected category once
                            val selectedFocusRequester = remember { FocusRequester() }
                            LaunchedEffect(selectedCategory) {
                                if (selectedCategory != null) {
                                    runCatching { selectedFocusRequester.requestFocus() }
                                }
                            }

                            LazyColumn(
                                contentPadding = PaddingValues(bottom = 8.dp),
                                verticalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                items(
                                    items = viewModel.allCategories,
                                    key = { it.categoryId },
                                    contentType = { "category" }
                                ) { cat ->
                                    val isSelected = cat.categoryId == selectedCategory?.categoryId
                                    CategoryChip(
                                        category = cat,
                                        selected = isSelected,
                                        onClick = {
                                            if (selectedCategory?.categoryId != cat.categoryId) {
                                                selectedCategory = cat
                                            }
                                        },
                                        focusRequester = if (isSelected) selectedFocusRequester else null,
                                    )
                                }
                            }
                        }
                    }
                }

                Spacer(Modifier.width(14.dp))

                Surface(
                    modifier = Modifier.weight(1f).fillMaxHeight(),
                    shape = RoundedCornerShape(18.dp),
                    colors = SurfaceDefaults.colors(containerColor = Color(0xFF0F0F0F)),
                ) {
                    Box(modifier = Modifier.fillMaxSize()) {
                        if (viewModel.categories.isEmpty() || effectiveChannels.isEmpty()) {
                            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                                CircularProgressIndicator(color = Color(0xFFF89344))
                            }
                        } else {
                            Column(modifier = Modifier.fillMaxSize()) {
                                GuideTimeHeader(windowStartMs = windowStartMs)

                                LazyColumn(
                                    state = guideListState,
                                    contentPadding = PaddingValues(bottom = 20.dp),
                                    verticalArrangement = Arrangement.spacedBy(2.dp),
                                ) {
                                    items(effectiveChannels.take(50), key = { it.id }) { ch ->
                                        GuideChannelRow(
                                            viewModel = viewModel,
                                            channel = ch,
                                            windowStartMs = windowStartMs,
                                            nowMs = nowMs,
                                            onChannelPlay = onChannelPlay,
                                        )
                                    }
                                }
                            }

                            CurrentTimeMarker(
                                nowMs = nowMs,
                                windowStartMs = windowStartMs,
                            )
                        }
                    }
                }
            }
        }
    }
}

// ── Category sidebar item ─────────────────────────────────────────────────────

@Composable
private fun CategoryChip(
    category: Category,
    selected: Boolean,
    onClick: () -> Unit,
    focusRequester: FocusRequester? = null,
) {
    Surface(
        onClick = onClick,
        modifier = Modifier
            .then(if (focusRequester != null) Modifier.focusRequester(focusRequester) else Modifier)
            .onFocusChanged { if (it.isFocused) onClick() }
            .height(40.dp),
        shape = ClickableSurfaceDefaults.shape(shape = RoundedCornerShape(20.dp)),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = if (selected) Color(0xFFF89344) else Color(0xFF1A1A1A),
            focusedContainerColor = if (selected) Color(0xFFF0A44C) else Color(0xFF2A2A2A),
        ),
    ) {
        Row(
            modifier = Modifier
                .padding(horizontal = 16.dp)
                .height(40.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (selected) {
                Text("●", color = Color.White, fontSize = 10.sp)
                Spacer(Modifier.width(6.dp))
            }
            Text(
                text = category.categoryName,
                color = if (selected) Color.White else Color(0xFFE6E6E6),
                fontSize = 14.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun GuideTimeHeader(windowStartMs: Long) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(24.dp)
            .background(Color(0xFF181818)),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // Gutter to align with channel name column
        Box(Modifier.width(CHANNEL_COL_WIDTH))

        // Time slots: every 30 minutes across the 3-hour window
        (0 until (WINDOW_MINS / 30)).forEach { i ->
            val slotMs = windowStartMs + i * 30 * 60_000L
            Text(
                text     = formatMs12h(slotMs),
                color    = Color(0xFF888888),
                fontSize = 12.sp,
                modifier = Modifier.width((30 * DP_PER_MIN).dp).padding(start = 6.dp),
            )
        }
    }
}

// ── Channel row ───────────────────────────────────────────────────────────────

@Composable
private fun GuideChannelRow(
    viewModel: MainViewModel,
    channel: Channel,
    windowStartMs: Long,
    nowMs: Long,
    onChannelPlay: (id: String, name: String) -> Unit,
) {
    val windowEndMs = windowStartMs + WINDOW_MINS * 60_000L
    val focusManager = LocalFocusManager.current

    val listings = viewModel.guideEpg[channel.id].orEmpty()
    val visible = remember(channel.id, windowStartMs, listings) {
        listings.mapNotNull { listing ->
            val startMs = parseEpgMs(listing.start)
            val stopMs = parseEpgMs(listing.stop)
            val isValid = startMs > 0 && stopMs > 0
            if (isValid && (stopMs > windowStartMs && startMs < windowEndMs)) {
                VisibleListing(
                    listing = listing,
                    startMs = startMs,
                    stopMs = stopMs,
                    timeLabel = "${formatEpgTime(listing.start)}–${formatEpgTime(listing.stop)}",
                )
            } else {
                null
            }
        }
    }

    val hasGuide = viewModel.guideEpg.containsKey(channel.id)

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(54.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // Channel name cell - handles vertical navigation
        Surface(
            onClick = { onChannelPlay(channel.id, channel.name) },
            modifier = Modifier
                .width(CHANNEL_COL_WIDTH)
                .height(48.dp)
                .onPreviewKeyEvent { event ->
                    if (event.nativeKeyEvent.action == AndroidKeyEvent.ACTION_DOWN) {
                        when (event.nativeKeyEvent.keyCode) {
                            AndroidKeyEvent.KEYCODE_DPAD_UP -> focusManager.moveFocus(FocusDirection.Up)
                            AndroidKeyEvent.KEYCODE_DPAD_DOWN -> focusManager.moveFocus(FocusDirection.Down)
                            else -> false
                        }
                    } else false
                },
            shape = ClickableSurfaceDefaults.shape(shape = RoundedCornerShape(4.dp)),
            colors = ClickableSurfaceDefaults.colors(
                containerColor = Color(0xFF1A1A1A),
                focusedContainerColor = Color(0xFFF89344),
            ),
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 10.dp),
                contentAlignment = Alignment.CenterStart,
            ) {
                Text(
                    text = channel.name,
                    color = Color.White,
                    fontSize = 14.sp,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }

        Spacer(Modifier.width(2.dp))

        // Programs area - simple Row (not LazyRow) for performance
        // Tivimate-style: all rows render same time window, no per-row scrolling
        if (visible.isEmpty()) {
            Box(
                modifier = Modifier
                    .weight(1f)
                    .height(48.dp)
                    .background(Color(0xFF111111)),
                contentAlignment = Alignment.CenterStart,
            ) {
                Text(
                    text = if (!hasGuide) "  Loading..." else "  No guide data",
                    color = Color(0xFF444444),
                    fontSize = 13.sp,
                )
            }
        } else {
            // Simple Row instead of LazyRow - much faster for limited items
            Row(
                modifier = Modifier
                    .weight(1f)
                    .height(48.dp)
                    .background(Color(0xFF0A0A0A)),
                horizontalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                visible.forEach { visibleListing ->
                    val startMs = visibleListing.startMs
                    val stopMs = visibleListing.stopMs
                    val durationMin = ((stopMs - startMs) / 60_000f).coerceAtLeast(15f)
                    val widthDp = (durationMin * DP_PER_MIN).dp.coerceAtMost(300.dp)
                    val isNow = startMs <= nowMs && stopMs > nowMs

                    ProgramCell(
                        listing = visibleListing,
                        widthDp = widthDp,
                        isNow = isNow,
                        onClick = { onChannelPlay(channel.id, channel.name) },
                    )
                }
            }
        }
    }
}

@Composable
private fun CurrentTimeMarker(nowMs: Long, windowStartMs: Long) {
    val markerOffsetDp = CHANNEL_COL_WIDTH + (((nowMs - windowStartMs).coerceAtLeast(0L) / 60_000f) * DP_PER_MIN).dp

    Box(
        modifier = Modifier
            .fillMaxHeight()
            .padding(top = 24.dp)
            .offset(x = markerOffsetDp)
            .width(2.dp)
            .background(Color(0xFFF89344).copy(alpha = 0.9f)),
    )
}

// ── Programme cell ────────────────────────────────────────────────────────────

@Composable
private fun ProgramCell(
    listing: VisibleListing,
    widthDp: Dp,
    isNow: Boolean,
    onClick: () -> Unit,
) {
    // Lightweight clickable box - navigation handled at row level
    Surface(
        onClick = onClick,
        modifier = Modifier
            .width(widthDp)
            .height(48.dp),
        shape = ClickableSurfaceDefaults.shape(shape = RoundedCornerShape(4.dp)),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = if (isNow) Color(0xFF1A3A1A) else Color(0xFF1E1E1E),
            focusedContainerColor = if (isNow) Color(0xFF2E8D2E) else Color(0xFF3E3E3E),
        ),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 8.dp, vertical = 2.dp),
            verticalArrangement = Arrangement.Center,
        ) {
            Text(
                text = listing.listing.title,
                color = if (isNow) Color(0xFF90EE90) else Color.White,
                fontSize = 13.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = listing.timeLabel,
                color = Color(0xFF888888),
                fontSize = 10.sp,
            )
        }
    }
}

// ── Time utilities ────────────────────────────────────────────────────────────

private val _epgSdf = object : ThreadLocal<SimpleDateFormat>() {
    override fun initialValue(): SimpleDateFormat {
        return SimpleDateFormat("yyyyMMddHHmmss", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }
    }
}

internal fun parseEpgMs(raw: String?): Long {
    if (raw == null) return 0L
    return try {
        val clean = raw.trim().take(14)
        val parsed = _epgSdf.get()!!.parse(clean)
        val result = parsed?.time ?: 0L
        if (result == 0L) {
            println("[TIME] Failed to parse EPG time: '$raw'")
        }
        result
    } catch (e: Exception) {
        println("[TIME] Error parsing EPG time '$raw': ${e.message}")
        0L
    }
}

private fun formatMs12h(ms: Long): String =
    SimpleDateFormat("h:mm a", Locale.getDefault()).format(Date(ms))

private fun formatGuideDateTime(ms: Long): String =
    SimpleDateFormat("EEE, MMM d • h:mm a", Locale.getDefault()).format(Date(ms))

internal fun formatEpgTime12h(raw: String?): String {
    if (raw == null) return "--:--"
    return try {
        val parsed = _epgSdf.get()!!.parse(raw.trim().take(14))
        parsed?.let { SimpleDateFormat("h:mm a", Locale.getDefault()).format(it) } ?: raw
    } catch (_: Exception) { raw }
}

internal fun formatEpgTime(raw: String?): String = formatEpgTime12h(raw)

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

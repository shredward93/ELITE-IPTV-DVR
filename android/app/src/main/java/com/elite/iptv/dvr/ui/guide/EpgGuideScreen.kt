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

    LaunchedEffect(Unit) {
        if (viewModel.categoryChannels.isEmpty()) {
            viewModel.loadGuideBundle()
        }
    }

    LaunchedEffect(viewModel.categories) {
        if (selectedCategory == null) {
            selectedCategory = viewModel.categories.firstOrNull()
        }
    }

    LaunchedEffect(selectedCategory) {
        val cat = selectedCategory ?: return@LaunchedEffect
        val alreadyLoaded = viewModel.lastGuideCategoryId == cat.categoryId && viewModel.categoryChannels.isNotEmpty()
        if (!alreadyLoaded) {
            viewModel.loadGuideBundle(cat.categoryId)
        }
    }

    // If the backend is still downloading XMLTV, retry every 8 s until EPG arrives
    LaunchedEffect(viewModel.guideBundleSource) {
        if (viewModel.guideBundleSource == "loading") {
            kotlinx.coroutines.delay(8_000L)
            viewModel.loadGuideBundle(selectedCategory?.categoryId, refresh = true)
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
                        text = formatGuideDateTime(nowMs),
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
                        if (viewModel.categories.isEmpty()) {
                            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                                CircularProgressIndicator(color = Color(0xFFF89344))
                            }
                        } else {
                            LazyColumn(
                                contentPadding = PaddingValues(bottom = 8.dp),
                                verticalArrangement = Arrangement.spacedBy(10.dp),
                            ) {
                                items(viewModel.categories, key = { it.categoryId }) { cat ->
                                    CategoryChip(
                                        category = cat,
                                        selected = cat.categoryId == selectedCategory?.categoryId,
                                        onClick = { selectedCategory = cat },
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
private fun CategoryChip(category: Category, selected: Boolean, onClick: () -> Unit) {
    val focusRequester = remember { FocusRequester() }

    LaunchedEffect(selected) {
        if (selected) {
            runCatching { focusRequester.requestFocus() }
        }
    }

    Surface(
        onClick = onClick,
        modifier = Modifier
            .focusRequester(focusRequester)
            .onFocusChanged { if (it.isFocused) onClick() }
            .height(40.dp),
        shape = ClickableSurfaceDefaults.shape(shape = RoundedCornerShape(20.dp)),
        colors = ClickableSurfaceDefaults.colors(
            containerColor        = if (selected) Color(0xFFF89344) else Color(0xFF1A1A1A),
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
                text     = category.categoryName,
                color    = if (selected) Color.White else Color(0xFFE6E6E6),
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
    val isLoadingGuide = channel.id in viewModel.guideEpgLoadingChannelIds
    val hasLoadedGuide = channel.id in viewModel.guideEpgLoadedChannelIds || listings.isNotEmpty()

    val visible = remember(listings, windowStartMs) {
        val filtered = listings.filter { l ->
            val stop  = parseEpgMs(l.stop)
            val start = parseEpgMs(l.start)
            // Include programs with valid times that overlap our window, or invalid times for debugging
            val isValid = start > 0 && stop > 0
            val inWindow = isValid && (stop > windowStartMs && start < windowEndMs)
            inWindow || !isValid // Show invalid entries for debugging
        }
        println("[GUIDE] Channel ${channel.id}: ${listings.size} total listings, ${filtered.size} visible")
        filtered
    }

    val rowListState = rememberLazyListState()

    LaunchedEffect(visible) {
        val selectedIndex = visible.indexOfFirst {
            val startMs = parseEpgMs(it.start)
            val stopMs = parseEpgMs(it.stop)
            startMs <= nowMs && stopMs > nowMs
        }

        if (selectedIndex >= 0) {
            rowListState.animateScrollToItem(selectedIndex)
        }
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(58.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Surface(
            onClick = { onChannelPlay(channel.id, channel.name) },
            modifier = Modifier
                .width(CHANNEL_COL_WIDTH)
                .height(46.dp)
                .onPreviewKeyEvent { event ->
                    if (event.nativeKeyEvent.action == AndroidKeyEvent.ACTION_DOWN) {
                        when (event.nativeKeyEvent.keyCode) {
                            AndroidKeyEvent.KEYCODE_DPAD_RIGHT -> focusManager.moveFocus(FocusDirection.Right)
                            AndroidKeyEvent.KEYCODE_DPAD_UP -> focusManager.moveFocus(FocusDirection.Up)
                            AndroidKeyEvent.KEYCODE_DPAD_DOWN -> focusManager.moveFocus(FocusDirection.Down)
                            else -> false
                        }
                    } else {
                        false
                    }
                },
            shape  = ClickableSurfaceDefaults.shape(shape = RoundedCornerShape(0.dp)),
            colors = ClickableSurfaceDefaults.colors(
                containerColor        = Color(0xFF1A1A1A),
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
                    text     = channel.name,
                    color    = Color.White,
                    fontSize = 14.sp,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }

        if (visible.isEmpty()) {
            Box(
                modifier = Modifier
                    .weight(1f)
                    .height(46.dp)
                    .background(Color(0xFF111111)),
                contentAlignment = Alignment.CenterStart,
            ) {
                Text(
                    text = if (isLoadingGuide || !hasLoadedGuide) "  Loading guide..." else "  No guide data",
                    color = Color(0xFF444444),
                    fontSize = 13.sp,
                )
            }
        } else {
            LazyRow(
                state               = rowListState,
                modifier            = Modifier.weight(1f).height(46.dp),
                horizontalArrangement = Arrangement.spacedBy(2.dp),
                contentPadding      = PaddingValues(end = 8.dp),
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
    listing: EpgListing,
    widthDp: Dp,
    isNow: Boolean,
    onClick: () -> Unit,
) {
    val focusManager = LocalFocusManager.current

    Surface(
        onClick  = onClick,
        modifier = Modifier
            .onPreviewKeyEvent { event ->
                if (event.nativeKeyEvent.action == AndroidKeyEvent.ACTION_DOWN) {
                    when (event.nativeKeyEvent.keyCode) {
                        AndroidKeyEvent.KEYCODE_DPAD_LEFT -> focusManager.moveFocus(FocusDirection.Left)
                        AndroidKeyEvent.KEYCODE_DPAD_RIGHT -> focusManager.moveFocus(FocusDirection.Right)
                        AndroidKeyEvent.KEYCODE_DPAD_UP -> focusManager.moveFocus(FocusDirection.Up)
                        AndroidKeyEvent.KEYCODE_DPAD_DOWN -> focusManager.moveFocus(FocusDirection.Down)
                        else -> false
                    }
                } else {
                    false
                }
            }
            .width(widthDp)
            .height(46.dp),
        shape    = ClickableSurfaceDefaults.shape(shape = RoundedCornerShape(4.dp)),
        colors   = ClickableSurfaceDefaults.colors(
            containerColor        = if (isNow) Color(0xFF1A2E1A) else Color(0xFF1E1E1E),
            focusedContainerColor = if (isNow) Color(0xFF2E7D2E) else Color(0xFF2E2E2E),
        ),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 8.dp, vertical = 3.dp),
            verticalArrangement = Arrangement.Center,
        ) {
            Text(
                text     = listing.title,
                color    = if (isNow) Color(0xFF90EE90) else Color.White,
                fontSize = 13.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text     = "${formatEpgTime(listing.start)}–${formatEpgTime(listing.stop)}",
                color    = Color(0xFF888888),
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

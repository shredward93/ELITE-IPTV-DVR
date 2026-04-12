package com.elite.iptv.dvr.ui.guide

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.border
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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.TileMode
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusProperties
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.elite.iptv.dvr.R
import com.elite.iptv.dvr.api.Category
import com.elite.iptv.dvr.api.Channel
import com.elite.iptv.dvr.api.EpgListing
import com.elite.iptv.dvr.viewmodel.MainViewModel
import kotlinx.coroutines.delay

private const val DP_PER_MIN = 4
private const val WINDOW_MINS = 180
private const val PRE_MINS = 30
private const val MAX_VISIBLE_ROWS = 60
private val CATEGORY_RAIL_WIDTH = 200.dp
private val DETAIL_PANEL_WIDTH = 200.dp
private val CHANNEL_COL_WIDTH = 164.dp

private data class VisibleProgram(
    val listing: EpgListing,
    val startMs: Long,
    val stopMs: Long,
    val timeLabel: String,
)

@Composable
fun GuideGridScreen(
    viewModel: MainViewModel,
    onChannelPlay: (id: String, name: String) -> Unit,
    onBack: () -> Unit,
) {
    BackHandler { onBack() }

    val categories = viewModel.guideCategories()
    var selectedCategoryId by remember { mutableStateOf<String?>(null) }
    var selectedChannelId by remember { mutableStateOf<String?>(null) }

    val activeCategoryId = selectedCategoryId?.takeIf { id -> categories.any { it.categoryId == id } }
        ?: categories.firstOrNull()?.categoryId
    val selectedCategory = categories.firstOrNull { it.categoryId == activeCategoryId }
    val channelsForSelectedCategory = viewModel.guideChannelsFor(activeCategoryId)
    val activeChannelId = selectedChannelId?.takeIf { id -> channelsForSelectedCategory.any { it.id == id } }
        ?: channelsForSelectedCategory.firstOrNull()?.id
    val selectedChannel = channelsForSelectedCategory.firstOrNull { it.id == activeChannelId }
    val selectedListings = selectedChannel?.let { viewModel.guideEpg[it.id].orEmpty() }.orEmpty()
    val selectedProgram = remember(selectedChannel?.id, selectedListings) {
        selectedListings.firstOrNull { listing ->
            val startMs = guideGridParseEpgMs(listing.start)
            val stopMs = guideGridParseEpgMs(listing.stop)
            startMs > 0 && stopMs > 0 && stopMs > System.currentTimeMillis() - PRE_MINS * 60_000L
        } ?: selectedListings.firstOrNull()
    }
    val guideListState = rememberLazyListState()

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 24.dp, vertical = 18.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column {
                    Text(
                        text = "TV Guide",
                        color = Color.White,
                        fontSize = 22.sp,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        text = selectedCategory?.categoryName ?: "Select a category",
                        color = Color(0xFFBDBDBD),
                        fontSize = 12.sp,
                    )
                }

                Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = viewModel.guideLoadState.name,
                        color = Color(0xFFF89344),
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Medium,
                    )
                    GoldHoverButton(text = "Refresh", containerColor = Color(0xFFF89344), onClick = { viewModel.prefetchAllGuideData() })
                    GoldHoverButton(text = "Back", containerColor = Color(0xFF2E2E2E), onClick = onBack)
                }
            }

            Spacer(Modifier.height(12.dp))

            GuideCompactDetailStrip(
                selectedCategory = selectedCategory,
                focusedChannel = selectedChannel,
                focusedProgram = selectedProgram,
                loadState = viewModel.guideLoadState,
                loadError = viewModel.guideLoadError,
                source = viewModel.guideBundleSource,
                onPlay = {
                    selectedChannel?.let { onChannelPlay(it.id, it.name) }
                },
                onRetry = { viewModel.prefetchAllGuideData() },
            )

            Spacer(Modifier.height(12.dp))

            Row(modifier = Modifier.weight(1f)) {
                Box(
                    modifier = Modifier
                        .width(CATEGORY_RAIL_WIDTH)
                        .fillMaxHeight()
                        .background(Color(0xFF101010), RoundedCornerShape(18.dp)),
                ) {
                    Column(modifier = Modifier.fillMaxSize().padding(12.dp)) {
                        Text(
                            text = "Categories",
                            color = Color(0xFFE0E0E0),
                            fontSize = 14.sp,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Spacer(Modifier.height(10.dp))

                        if (categories.isEmpty()) {
                            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                                CircularProgressIndicator(color = Color(0xFFF89344))
                            }
                        } else {
                            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                items(categories) { category ->
                                    CategoryChip(
                                        category = category,
                                        selected = category.categoryId == activeCategoryId,
                                        count = viewModel.channelsByCategory[category.categoryId]?.size
                                            ?: if (viewModel.lastGuideCategoryId == category.categoryId) viewModel.categoryChannels.size else 0,
                                        onClick = {
                                            selectedCategoryId = category.categoryId
                                            selectedChannelId = viewModel.guideChannelsFor(category.categoryId).firstOrNull()?.id
                                        },
                                    )
                                }
                            }
                        }
                    }
                }

                Spacer(Modifier.width(14.dp))

                GuideGridPane(
                    modifier = Modifier.weight(1f),
                    channels = channelsForSelectedCategory,
                    guideEpg = viewModel.guideEpg,
                    windowStartMs = System.currentTimeMillis() - PRE_MINS * 60_000L,
                    windowEndMs = System.currentTimeMillis() + (WINDOW_MINS - PRE_MINS) * 60_000L,
                    nowMs = System.currentTimeMillis(),
                    listState = guideListState,
                    selectedChannelId = activeChannelId,
                    onChannelSelected = { selectedChannelId = it },
                    onChannelPlay = onChannelPlay,
                )
            }
        }
    }
}

@Composable
private fun GuideCompactDetailStrip(
    selectedCategory: Category?,
    focusedChannel: Channel?,
    focusedProgram: EpgListing?,
    loadState: MainViewModel.GuideLoadState,
    loadError: String?,
    source: String?,
    onPlay: () -> Unit,
    onRetry: () -> Unit,
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color(0xFF111111), RoundedCornerShape(14.dp)),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = focusedChannel?.name ?: "Select a channel",
                    color = Color.White,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = selectedCategory?.categoryName ?: "Choose a category",
                    color = Color(0xFFF89344),
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Medium,
                )
                Text(
                    text = focusedProgram?.let {
                        "${it.title} • ${guideGridFormatEpgTime(it.start)} – ${guideGridFormatEpgTime(it.stop)}"
                    } ?: "No program selected",
                    color = Color(0xFFBDBDBD),
                    fontSize = 10.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = source?.let { "Source: $it" } ?: loadState.name,
                    color = Color(0xFF9A9A9A),
                    fontSize = 10.sp,
                    maxLines = 1,
                )
                GoldHoverButton(text = "Play", containerColor = Color(0xFFF89344), modifier = Modifier.height(28.dp), onClick = onPlay)
                GoldHoverButton(text = "Retry", containerColor = Color(0xFF2A2A2A), modifier = Modifier.height(28.dp), onClick = onRetry)
            }
        }

        loadError?.takeIf { it.isNotBlank() }?.let {
            Text(
                text = it,
                color = Color(0xFFFF8A80),
                fontSize = 9.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier
                    .align(Alignment.BottomStart)
                    .padding(start = 14.dp, bottom = 6.dp),
            )
        }
    }
}

@Composable
private fun GuideHeader(
    timeLabel: String,
    selectedCategory: Category?,
    loadState: MainViewModel.GuideLoadState,
    source: String?,
    onBack: () -> Unit,
    onRefresh: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(
                brush = Brush.horizontalGradient(
                    colors = listOf(Color(0xFF161616), Color(0xFF262626), Color(0xFF141414)),
                    tileMode = TileMode.Clamp,
                ),
            )
            .padding(horizontal = 22.dp, vertical = 16.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(42.dp)
                    .background(Color(0xFFF89344), CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Image(
                    painter = painterResource(id = R.drawable.elite_logo),
                    contentDescription = "ELITE IPTV DVR logo",
                    modifier = Modifier.size(30.dp),
                )
            }

            Spacer(Modifier.width(14.dp))

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

        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    text = timeLabel,
                    color = Color(0xFFF89344),
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Medium,
                )
                Text(
                    text = source?.let { "Source: $it" } ?: loadState.name,
                    color = Color(0xFFBDBDBD),
                    fontSize = 12.sp,
                )
            }

            Box(
                modifier = Modifier
                    .height(40.dp)
                    .background(Color(0xFF2A2A2A))
                    .clickable(onClick = onRefresh),
            ) {
                Text("Refresh", color = Color.White, fontSize = 14.sp, modifier = Modifier.padding(8.dp))
            }

            Box(
                modifier = Modifier
                    .height(40.dp)
                    .background(Color(0xFF2A2A2A))
                    .clickable(onClick = onBack),
            ) {
                Text("← Back", color = Color.White, fontSize = 14.sp, modifier = Modifier.padding(8.dp))
            }
        }
    }
}

@Composable
private fun CategoryRail(
    categories: List<Category>,
    selectedCategoryId: String?,
    channelCountForCategory: (String) -> Int,
    onSelectCategory: (String) -> Unit,
) {
    Box(
        modifier = Modifier
            .width(CATEGORY_RAIL_WIDTH)
            .fillMaxHeight()
            .background(Color(0xFF101010), RoundedCornerShape(18.dp)),
    ) {
        Column(modifier = Modifier.fillMaxSize().padding(horizontal = 14.dp, vertical = 14.dp)) {
            Text(
                text = "Categories",
                color = Color(0xFFE0E0E0),
                fontSize = 18.sp,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.height(12.dp))

            if (categories.isEmpty()) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = Color(0xFFF89344))
                }
                return@Column
            }

            LazyColumn(
                contentPadding = PaddingValues(bottom = 8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(categories) { category ->
                    val isSelected = category.categoryId == selectedCategoryId
                    CategoryChip(
                        category = category,
                        selected = isSelected,
                        count = channelCountForCategory(category.categoryId),
                        onClick = { onSelectCategory(category.categoryId) },
                    )
                }
            }
        }
    }
}

@Composable
private fun CategoryChip(
    category: Category,
    selected: Boolean,
    count: Int,
    onClick: () -> Unit,
) {
    var focused by remember { mutableStateOf(false) }
    val isEmphasized = selected || focused

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(44.dp)
            .background(
                color = when {
                    selected -> Color(0xFFF89344)
                    focused -> Color(0xFF2E2E2E)
                    else -> Color(0xFF1A1A1A)
                },
                shape = RoundedCornerShape(22.dp),
            )
            .then(
                when {
                    selected -> Modifier.border(3.dp, Color.White, RoundedCornerShape(22.dp))
                    focused -> Modifier.border(3.dp, Color(0xFFFFD24C), RoundedCornerShape(22.dp))
                    else -> Modifier
                }
            )
            .onFocusChanged {
                focused = it.isFocused || it.hasFocus
            }
            .clickable(onClick = onClick),
    ) {
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (isEmphasized) {
                    Text("●", color = Color.White, fontSize = 10.sp)
                    Spacer(Modifier.width(6.dp))
                }
                Text(
                    text = category.categoryName,
                    color = if (isEmphasized) Color.White else Color(0xFFE6E6E6),
                    fontSize = 14.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }

            Text(
                text = count.toString(),
                color = if (isEmphasized) Color.White else Color(0xFFA9A9A9),
                fontSize = 12.sp,
                fontWeight = FontWeight.Medium,
            )
        }
    }
}

@Composable
private fun GuideChannelRow(
    channel: Channel,
    listings: List<EpgListing>,
    windowStartMs: Long,
    windowEndMs: Long,
    nowMs: Long,
    selected: Boolean,
    focusRequester: FocusRequester? = null,
    onSelect: () -> Unit,
    onChannelPlay: (id: String, name: String) -> Unit,
) {
    val visiblePrograms = remember(channel.id, listings, windowStartMs, windowEndMs) {
        listings.mapNotNull { listing ->
            val startMs = guideGridParseEpgMs(listing.start)
            val stopMs = guideGridParseEpgMs(listing.stop)
            val valid = startMs > 0 && stopMs > 0
            if (valid && stopMs > windowStartMs && startMs < windowEndMs) {
                VisibleProgram(
                    listing = listing,
                    startMs = startMs,
                    stopMs = stopMs,
                    timeLabel = "${guideGridFormatEpgTime(listing.start)}–${guideGridFormatEpgTime(listing.stop)}",
                )
            } else {
                null
            }
        }
    }

    val hasGuide = listings.isNotEmpty()
    var channelFocused by remember { mutableStateOf(false) }
    val isEmphasized = selected || channelFocused

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(54.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .width(CHANNEL_COL_WIDTH)
                .height(48.dp)
                .background(
                    when {
                        selected -> Color(0xFFF89344)
                        channelFocused -> Color(0xFF303030)
                        else -> Color(0xFF1A1A1A)
                    },
                    RoundedCornerShape(6.dp),
                )
                .then(
                    when {
                        selected -> Modifier.border(3.dp, Color.White, RoundedCornerShape(6.dp))
                        channelFocused -> Modifier.border(3.dp, Color(0xFFFFD24C), RoundedCornerShape(6.dp))
                        else -> Modifier
                    }
                )
                .then(if (focusRequester != null) Modifier.focusRequester(focusRequester) else Modifier)
            .onFocusChanged {
                channelFocused = it.isFocused || it.hasFocus
            }
            .clickable(onClick = onSelect),
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 10.dp),
                contentAlignment = Alignment.CenterStart,
            ) {
                Text(
                    text = channel.name,
                    color = if (isEmphasized) Color.White else Color.White,
                    fontSize = 14.sp,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }

        Spacer(Modifier.width(2.dp))

        if (visiblePrograms.isEmpty()) {
            Box(
                modifier = Modifier
                    .weight(1f)
                    .height(48.dp)
                    .background(Color(0xFF111111)),
                contentAlignment = Alignment.CenterStart,
            ) {
                Text(
                    text = if (!hasGuide) "  Loading…" else "  No guide data",
                    color = Color(0xFF666666),
                    fontSize = 13.sp,
                )
            }
        } else {
            Row(
                modifier = Modifier
                    .weight(1f)
                    .height(48.dp)
                    .background(Color(0xFF0A0A0A)),
                horizontalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                visiblePrograms.forEach { program ->
                    val durationMin = ((program.stopMs - program.startMs) / 60_000f).coerceAtLeast(15f)
                    val widthDp = (durationMin * DP_PER_MIN).dp.coerceAtMost(300.dp)
                    val isNow = program.startMs <= nowMs && program.stopMs > nowMs

                    ProgramCell(
                        title = program.listing.title,
                        timeLabel = program.timeLabel,
                        description = program.listing.description,
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
private fun ProgramCell(
    title: String,
    timeLabel: String,
    description: String?,
    widthDp: Dp,
    isNow: Boolean,
    leftRequester: FocusRequester? = null,
    onClick: () -> Unit,
) {
    var focused by remember { mutableStateOf(false) }
    val isEmphasized = focused || isNow

    Box(
        modifier = Modifier
            .width(widthDp)
            .height(48.dp)
            .background(
                color = when {
                    focused -> Color(0xFF2A2A2A)
                    isNow -> Color(0xFF1A3A1A)
                    else -> Color(0xFF1E1E1E)
                },
                shape = RoundedCornerShape(6.dp),
            )
            .then(
                if (focused) {
                    Modifier.border(3.dp, Color(0xFFFFD24C), RoundedCornerShape(6.dp))
                } else {
                    Modifier
                }
            )
            .focusProperties {
                if (leftRequester != null) {
                    left = leftRequester
                }
            }
            .onFocusChanged {
                focused = it.isFocused || it.hasFocus
            }
            .clickable(onClick = onClick),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 8.dp, vertical = 3.dp),
            verticalArrangement = Arrangement.Center,
        ) {
            Text(
                text = title,
                color = if (isEmphasized) Color(0xFFFFF2A8) else Color.White,
                fontSize = 13.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = timeLabel,
                color = if (focused) Color.White else Color(0xFFAAAAAA),
                fontSize = 10.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            description?.takeIf { it.isNotBlank() }?.let {
                Text(
                    text = it,
                    color = if (focused) Color(0xFFE8E8E8) else Color(0xFF7F7F7F),
                    fontSize = 9.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun GuideGridPane(
    modifier: Modifier = Modifier,
    channels: List<Channel>,
    guideEpg: Map<String, List<EpgListing>>,
    windowStartMs: Long,
    windowEndMs: Long,
    nowMs: Long,
    listState: androidx.compose.foundation.lazy.LazyListState,
    selectedChannelId: String?,
    onChannelSelected: (String) -> Unit,
    onChannelPlay: (id: String, name: String) -> Unit,
) {
    Box(
        modifier = modifier
            .fillMaxHeight()
            .background(Color(0xFF0F0F0F), RoundedCornerShape(18.dp)),
    ) {
        Box(modifier = Modifier.fillMaxSize()) {
            if (channels.isEmpty()) {
                EmptyGuidePane()
            } else {
                Column(modifier = Modifier.fillMaxSize()) {
                    GuideTimeHeader(windowStartMs = windowStartMs)

                    LazyColumn(
                        state = listState,
                        contentPadding = PaddingValues(bottom = 18.dp),
                        verticalArrangement = Arrangement.spacedBy(2.dp),
                    ) {
                        items(channels.take(MAX_VISIBLE_ROWS)) { channel ->
                            GuideChannelRow(
                                channel = channel,
                                listings = guideEpg[channel.id].orEmpty(),
                                windowStartMs = windowStartMs,
                                windowEndMs = windowEndMs,
                                nowMs = nowMs,
                                selected = channel.id == selectedChannelId,
                                onSelect = { onChannelSelected(channel.id) },
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

@Composable
private fun EmptyGuidePane() {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center,
    ) {
        CircularProgressIndicator(color = Color(0xFFF89344))
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
        Box(Modifier.width(CHANNEL_COL_WIDTH))
        (0 until (WINDOW_MINS / 30)).forEach { index ->
            val slotMs = windowStartMs + index * 30 * 60_000L
            Text(
                text = formatMs12h(slotMs),
                color = Color(0xFF888888),
                fontSize = 12.sp,
                modifier = Modifier.width((30 * DP_PER_MIN).dp).padding(start = 6.dp),
            )
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
            .background(Color(0xFFF89344).copy(alpha = 0.92f)),
    )
}


@Composable
private fun GuideDetailPane(
    width: Dp,
    selectedCategory: Category?,
    focusedChannel: Channel?,
    focusedProgram: EpgListing?,
    loadState: MainViewModel.GuideLoadState,
    loadError: String?,
    source: String?,
    onPlay: () -> Unit,
    onRetry: () -> Unit,
) {
    Box(
        modifier = Modifier
            .width(width)
            .fillMaxHeight()
            .background(Color(0xFF101010), RoundedCornerShape(18.dp)),
    ) {
        Column(modifier = Modifier.fillMaxSize().padding(12.dp)) {
            Text(
                text = "Details",
                color = Color(0xFFE0E0E0),
                fontSize = 14.sp,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.height(10.dp))

            if (focusedChannel == null) {
                Text("Select a channel", color = Color(0xFF9A9A9A), fontSize = 11.sp)
            } else {
                Text(
                    text = focusedChannel.name,
                    color = Color.White,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Bold,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = selectedCategory?.categoryName ?: "",
                    color = Color(0xFFF89344),
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Medium,
                )

                Spacer(Modifier.height(10.dp))
                if (focusedProgram != null) {
                    Text(
                        text = focusedProgram.title,
                        color = Color(0xFFEFEFEF),
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        text = "${guideGridFormatEpgTime(focusedProgram.start)} – ${guideGridFormatEpgTime(focusedProgram.stop)}",
                        color = Color(0xFFB8B8B8),
                        fontSize = 11.sp,
                    )
                    Spacer(Modifier.height(6.dp))
                    Text(
                        text = focusedProgram.description?.takeIf { it.isNotBlank() } ?: "No description available.",
                        color = Color(0xFFD1D1D1),
                        fontSize = 11.sp,
                        lineHeight = 14.sp,
                        maxLines = 6,
                        overflow = TextOverflow.Ellipsis,
                    )
                } else {
                    Text(
                        text = "No program data in the current time window.",
                        color = Color(0xFF9A9A9A),
                        fontSize = 11.sp,
                    )
                }
            }

            Spacer(Modifier.height(10.dp))

            GoldHoverButton(
                text = "Watch Live",
                containerColor = Color(0xFFF89344),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(34.dp),
                onClick = onPlay,
            )

            Spacer(Modifier.height(8.dp))

            GoldHoverButton(
                text = "Retry guide",
                containerColor = Color(0xFF2A2A2A),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(34.dp),
                onClick = onRetry,
            )

            Spacer(Modifier.height(10.dp))
            Text(
                text = "State: ${loadState.name}",
                color = Color(0xFFBDBDBD),
                fontSize = 10.sp,
            )
            Text(
                text = source?.let { "Source: $it" } ?: "Source pending",
                color = Color(0xFF8E8E8E),
                fontSize = 10.sp,
            )

            loadError?.takeIf { it.isNotBlank() }?.let {
                Spacer(Modifier.height(8.dp))
                Text(
                    text = "Error:\n$it",
                    color = Color(0xFFFF8A80),
                    fontSize = 10.sp,
                    maxLines = 6,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun GoldHoverButton(
    text: String,
    containerColor: Color,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var focused by remember { mutableStateOf(false) }

    Button(
        onClick = onClick,
        shape = RoundedCornerShape(14.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = containerColor,
            contentColor = Color.White,
        ),
        modifier = modifier
            .border(
                width = 3.dp,
                color = if (focused) Color(0xFFFFD24C) else Color.Transparent,
                shape = RoundedCornerShape(14.dp),
            )
            .onFocusChanged {
                focused = it.isFocused || it.hasFocus
            },
    ) {
        Text(text, fontSize = 11.sp, color = Color.White)
    }
}

@Composable
private fun LoadingOverlay(
    progress: Pair<Int, Int>,
    message: String,
) {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            CircularProgressIndicator(color = Color(0xFFF89344))
            Spacer(Modifier.height(10.dp))
            val (loaded, total) = progress
            if (total > 0) {
                Text(
                    text = "$message ($loaded/$total)",
                    color = Color(0xFFB8B8B8),
                    fontSize = 13.sp,
                )
            } else {
                Text(
                    text = message,
                    color = Color(0xFFB8B8B8),
                    fontSize = 13.sp,
                )
            }
        }
    }
}

@Composable
private fun rememberGuideNowMs(tickMs: Long = 30_000L): androidx.compose.runtime.State<Long> {
    return produceState(initialValue = System.currentTimeMillis()) {
        while (true) {
            delay(tickMs)
            value = System.currentTimeMillis()
        }
    }
}

private val _guideGridEpgSdf = object : ThreadLocal<java.text.SimpleDateFormat>() {
    override fun initialValue(): java.text.SimpleDateFormat {
        return java.text.SimpleDateFormat("yyyyMMddHHmmss", java.util.Locale.US).apply {
            timeZone = java.util.TimeZone.getTimeZone("UTC")
        }
    }
}

private fun guideGridParseEpgMs(raw: String?): Long {
    if (raw == null) return 0L
    return try {
        val parsed = _guideGridEpgSdf.get()!!.parse(raw.trim().take(14))
        parsed?.time ?: 0L
    } catch (_: Exception) {
        0L
    }
}

private fun formatMs12h(ms: Long): String =
    java.text.SimpleDateFormat("h:mm a", java.util.Locale.getDefault()).format(java.util.Date(ms))

private fun guideGridFormatGuideDateTime(ms: Long): String =
    java.text.SimpleDateFormat("EEE, MMM d • h:mm a", java.util.Locale.getDefault()).format(java.util.Date(ms))

private fun guideGridFormatEpgTime(raw: String?): String {
    if (raw == null) return "--:--"
    return try {
        val parsed = _guideGridEpgSdf.get()!!.parse(raw.trim().take(14))
        parsed?.let { java.text.SimpleDateFormat("h:mm a", java.util.Locale.getDefault()).format(it) } ?: raw
    } catch (_: Exception) {
        raw
    }
}

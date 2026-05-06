@file:OptIn(ExperimentalTvMaterial3Api::class)

package com.elite.iptv.dvr.ui.channels

import android.view.KeyEvent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.BorderStroke
import androidx.tv.material3.Border
import androidx.tv.material3.Button
import androidx.tv.material3.ButtonDefaults
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.ExperimentalTvMaterial3Api
import androidx.tv.material3.Surface
import com.elite.iptv.dvr.BuildConfig
import com.elite.iptv.dvr.api.Channel
import com.elite.iptv.dvr.ui.theme.EliteColors
import com.elite.iptv.dvr.ui.theme.TvFocusDefaults
import com.elite.iptv.dvr.viewmodel.MainViewModel
import kotlinx.coroutines.delay

@Composable
fun ChannelBrowserScreen(
    viewModel: MainViewModel,
    onChannelSelected: (id: String, name: String) -> Unit,
    onGuideOpen: (id: String, name: String) -> Unit,
    onGuideGridOpen: () -> Unit,
    onLibraryOpen: () -> Unit,
    onSettingsOpen: () -> Unit,
) {
    val firstFocus = remember { FocusRequester() }
    var optionsChannel by remember { mutableStateOf<Channel?>(null) }
    var recordNowFor by remember { mutableStateOf<Channel?>(null) }
    var recordNowMins by remember { mutableStateOf(120) }
    var scheduleLaterFor by remember { mutableStateOf<Channel?>(null) }
    var scheduleLaterOffsetMins by remember { mutableStateOf(30) }
    var scheduleLaterDurationMins by remember { mutableStateOf(120) }
    var actionNote by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        viewModel.loadFavorites()
        viewModel.loadCategories()
        viewModel.loadCompletedRecordings()
        viewModel.searchChannels("")
        runCatching { firstFocus.requestFocus() }
    }

    LaunchedEffect(actionNote) {
        if (actionNote.isNotBlank()) {
            delay(4000)
            actionNote = ""
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(EliteColors.ink)
            .padding(24.dp),
    ) {
    Column(
        modifier = Modifier.fillMaxSize(),
    ) {
        // ── Header ────────────────────────────────────────────────────────────
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text(
                    text = "ELITE IPTV DVR",
                    color = EliteColors.signal,
                    fontSize = 26.sp,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = "Server-first TV shell",
                    color = EliteColors.paperMuted,
                    fontSize = 11.sp,
                    letterSpacing = 0.8.sp,
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                TvButton("TV Guide",    onClick = onGuideGridOpen)
                TvButton("DVR Library", onClick = onLibraryOpen)
                TvButton("Settings",    onClick = onSettingsOpen)
            }
        }

        Spacer(Modifier.height(20.dp))

        if (viewModel.activeRecordings.isNotEmpty() || viewModel.completedRecordings.isNotEmpty()) {
            Text("DVR", color = EliteColors.paper, fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                val liveCount = viewModel.activeRecordings.size
                val doneCount = viewModel.completedRecordings.size
                TvButton(
                    text = if (liveCount > 0) "Resume DVR ($liveCount live)" else "Open DVR Library",
                    width = 220.dp,
                    onClick = onLibraryOpen,
                )
                Text(
                    text = "$doneCount completed recordings ready",
                    color = EliteColors.paperMuted,
                    fontSize = 13.sp,
                )
            }
            Spacer(Modifier.height(16.dp))
        }

        val favoriteCategories = remember(viewModel.categories, viewModel.favoriteCategoryIds) {
            viewModel.favoriteCategoriesFromLoaded()
        }
        if (favoriteCategories.isNotEmpty()) {
            Text("Favorite Categories", color = EliteColors.paper, fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(8.dp))
            LazyRow(
                contentPadding = PaddingValues(end = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(favoriteCategories, key = { it.categoryId }) { cat ->
                    CategoryPill(
                        label = cat.categoryName,
                        onClick = onGuideGridOpen,
                    )
                }
            }
            Spacer(Modifier.height(16.dp))
        }

        // ── Favorites row ─────────────────────────────────────────────────────
        if (viewModel.favorites.isNotEmpty()) {
            Text("Favourites", color = EliteColors.paper, fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(8.dp))
            LazyRow(
                contentPadding = PaddingValues(end = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .focusRequester(firstFocus),
            ) {
                items(viewModel.favorites, key = { it.id }) { ch ->
                    ChannelCard(
                        channel = ch,
                        onSelect = { optionsChannel = ch },
                        onGuide = { onGuideOpen(ch.id, ch.name) },
                    )
                }
            }
            Spacer(Modifier.height(20.dp))
        }

        Text(
            text = "DVR-first home: pick a recording, favorite category, or channel. Long-press a guide category to save it.",
            color = EliteColors.paperMuted,
            fontSize = 11.sp,
            letterSpacing = 0.4.sp,
        )
        Spacer(Modifier.height(12.dp))

        // ── Channel browser grid ───────────────────────────────────────────────
        if (viewModel.searchResults.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("Loading channels...", color = EliteColors.paperMuted, fontSize = 18.sp)
            }
        } else {
            LazyVerticalGrid(
                columns = GridCells.Adaptive(220.dp),
                contentPadding = PaddingValues(bottom = 24.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
                modifier = Modifier.fillMaxSize(),
            ) {
                items(viewModel.searchResults, key = { it.id }) { ch ->
                    ChannelCard(
                        channel = ch,
                        onSelect = { optionsChannel = ch },
                        onGuide = { onGuideOpen(ch.id, ch.name) },
                    )
                }
            }
        }
    }

        if (actionNote.isNotBlank()) {
            Text(
                text = actionNote,
                color = EliteColors.ok,
                fontSize = 13.sp,
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 8.dp),
            )
        }

        optionsChannel?.let { ch ->
            ChannelOptionsDialog(
                channel = ch,
                onDismiss = { optionsChannel = null },
                onWatchLive = { onChannelSelected(ch.id, ch.name) },
                onTvGuide = { onGuideOpen(ch.id, ch.name) },
                onRecordNow = {
                    recordNowMins = 120
                    recordNowFor = ch
                },
                onScheduleLater = {
                    scheduleLaterOffsetMins = 30
                    scheduleLaterDurationMins = 120
                    scheduleLaterFor = ch
                },
            )
        }

        recordNowFor?.let { ch ->
            RecordNowChannelDialog(
                channel = ch,
                viewModel = viewModel,
                durationMins = recordNowMins,
                onDurationChange = { recordNowMins = it },
                onDismiss = { recordNowFor = null },
                onResultNote = { actionNote = it },
            )
        }

        scheduleLaterFor?.let { ch ->
            ScheduleLaterChannelDialog(
                channel = ch,
                viewModel = viewModel,
                offsetMins = scheduleLaterOffsetMins,
                onOffsetChange = { scheduleLaterOffsetMins = it },
                durationMins = scheduleLaterDurationMins,
                onDurationChange = { scheduleLaterDurationMins = it },
                onDismiss = { scheduleLaterFor = null },
                onResultNote = { actionNote = it },
            )
        }

        Text(
            text = "v${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})",
            color = EliteColors.paperMuted,
            fontSize = 11.sp,
            fontWeight = FontWeight.Medium,
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(horizontal = 10.dp, vertical = 6.dp),
        )
    }
}

@Composable
private fun ChannelCard(
    channel: Channel,
    onSelect: () -> Unit,
    onGuide: () -> Unit,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val focused by interactionSource.collectIsFocusedAsState()
    Surface(
        onClick = onSelect,
        onLongClick = onSelect,
        modifier = Modifier
            .width(220.dp)
            .height(64.dp)
            .onPreviewKeyEvent { ev ->
                val native = ev.nativeKeyEvent ?: return@onPreviewKeyEvent false
                if (native.action != KeyEvent.ACTION_DOWN) return@onPreviewKeyEvent false
                if (native.keyCode == KeyEvent.KEYCODE_MENU ||
                    native.keyCode == KeyEvent.KEYCODE_INFO ||
                    native.keyCode == 172 // KeyEvent.KEYCODE_TV_GUIDE (API 21+)
                ) {
                    onGuide()
                    true
                } else {
                    false
                }
            },
        shape = ClickableSurfaceDefaults.shape(shape = androidx.compose.foundation.shape.RoundedCornerShape(8.dp)),
        colors = ClickableSurfaceDefaults.colors(
            containerColor        = EliteColors.surface,
            focusedContainerColor = EliteColors.signal,
            pressedContainerColor = EliteColors.surface3,
        ),
        scale = TvFocusDefaults.surfaceScaleCard,
        border = ClickableSurfaceDefaults.border(
            border = Border.None,
            focusedBorder = Border(
                border = BorderStroke(2.dp, EliteColors.signal),
                inset = 0.dp,
                shape = RoundedCornerShape(8.dp),
            ),
        ),
        interactionSource = interactionSource,
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 14.dp),
            contentAlignment = Alignment.CenterStart,
        ) {
            Text(
                text = channel.name,
                fontSize = 18.sp,
                color = if (focused) EliteColors.ink else EliteColors.paper,
                maxLines = 1,
            )
        }
    }
}

@Composable
private fun TvButton(text: String, onClick: () -> Unit) {
    Button(
        onClick = onClick,
        modifier = Modifier.size(width = 140.dp, height = 44.dp),
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
        Text(text, fontSize = 15.sp, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun TvButton(text: String, width: androidx.compose.ui.unit.Dp, onClick: () -> Unit) {
    Button(
        onClick = onClick,
        modifier = Modifier.size(width = width, height = 44.dp),
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
        Text(text, fontSize = 15.sp, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun CategoryPill(label: String, onClick: () -> Unit) {
    Surface(
        onClick = onClick,
        modifier = Modifier.height(40.dp),
        shape = ClickableSurfaceDefaults.shape(shape = RoundedCornerShape(20.dp)),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = EliteColors.surface2,
            focusedContainerColor = EliteColors.signal,
        ),
        scale = TvFocusDefaults.surfaceScaleCompact,
        border = ClickableSurfaceDefaults.border(
            border = Border(
                border = BorderStroke(1.dp, EliteColors.rule),
                inset = 0.dp,
                shape = RoundedCornerShape(20.dp),
            ),
            focusedBorder = Border(
                border = BorderStroke(2.dp, EliteColors.signal),
                inset = 0.dp,
                shape = RoundedCornerShape(20.dp),
            ),
        ),
    ) {
        Box(modifier = Modifier.padding(horizontal = 14.dp), contentAlignment = Alignment.Center) {
            Text(label, color = EliteColors.paper, fontSize = 13.sp, maxLines = 1)
        }
    }
}

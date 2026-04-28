@file:OptIn(ExperimentalTvMaterial3Api::class)

package com.elite.iptv.dvr.ui.channels

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
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
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
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
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
import com.elite.iptv.dvr.api.Channel
import com.elite.iptv.dvr.ui.theme.EliteColors
import com.elite.iptv.dvr.ui.theme.TvFocusDefaults
import com.elite.iptv.dvr.viewmodel.MainViewModel

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

    LaunchedEffect(Unit) {
        viewModel.loadFavorites()
        viewModel.searchChannels("")
        runCatching { firstFocus.requestFocus() }
    }

    var query by remember { mutableStateOf("") }

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
                        channel  = ch,
                        onClick  = { onChannelSelected(ch.id, ch.name) },
                    )
                }
            }
            Spacer(Modifier.height(20.dp))
        }

        // ── Search ────────────────────────────────────────────────────────────
        OutlinedTextField(
            value = query,
            onValueChange = { q ->
                query = q
                viewModel.searchChannels(q)
            },
            label = { Text("Search channels", fontSize = 16.sp, color = EliteColors.paperMuted) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            keyboardActions = KeyboardActions(onSearch = { viewModel.searchChannels(query) }),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = EliteColors.signal,
                unfocusedBorderColor = EliteColors.rule,
                focusedTextColor = EliteColors.paper,
                unfocusedTextColor = EliteColors.paper,
                cursorColor = EliteColors.signal,
                focusedLabelColor = EliteColors.signal,
                unfocusedLabelColor = EliteColors.paperMuted,
            ),
        )

        Spacer(Modifier.height(8.dp))
        Text(
            text = "Press OK to play. Use TV Guide for schedule details.",
            color = EliteColors.paperMuted,
            fontSize = 11.sp,
            letterSpacing = 0.4.sp,
        )
        Spacer(Modifier.height(12.dp))

        // ── Results grid ──────────────────────────────────────────────────────
        if (viewModel.searchResults.isEmpty() && query.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("Type to search channels", color = EliteColors.paperMuted, fontSize = 18.sp)
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
                        channel  = ch,
                        onClick  = { onChannelSelected(ch.id, ch.name) },
                    )
                }
            }
        }
    }
}

@Composable
private fun ChannelCard(
    channel: Channel,
    onClick: () -> Unit,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val focused by interactionSource.collectIsFocusedAsState()
    Surface(
        onClick = onClick,
        modifier = Modifier
            .width(220.dp)
            .height(64.dp),
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

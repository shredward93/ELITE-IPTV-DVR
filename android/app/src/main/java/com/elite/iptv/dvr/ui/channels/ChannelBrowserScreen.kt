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
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.OutlinedTextField
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
import androidx.tv.material3.Button
import androidx.tv.material3.ButtonDefaults
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.ExperimentalTvMaterial3Api
import androidx.tv.material3.Surface
import com.elite.iptv.dvr.api.Channel
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
            .background(Color.Black)
            .padding(24.dp),
    ) {
        // ── Header ────────────────────────────────────────────────────────────
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "ELITE IPTV DVR",
                color = Color(0xFFF89344),
                fontSize = 26.sp,
                fontWeight = FontWeight.Bold,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                TvButton("TV Guide",    onClick = onGuideGridOpen)
                TvButton("DVR Library", onClick = onLibraryOpen)
                TvButton("Settings",    onClick = onSettingsOpen)
            }
        }

        Spacer(Modifier.height(20.dp))

        // ── Favorites row ─────────────────────────────────────────────────────
        if (viewModel.favorites.isNotEmpty()) {
            Text("Favourites", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
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
                        onLongClick = { onGuideOpen(ch.id, ch.name) },
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
            label = { Text("Search channels", fontSize = 16.sp) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            keyboardActions = KeyboardActions(onSearch = { viewModel.searchChannels(query) }),
        )

        Spacer(Modifier.height(16.dp))

        // ── Results grid ──────────────────────────────────────────────────────
        if (viewModel.searchResults.isEmpty() && query.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("Type to search channels", color = Color.Gray, fontSize = 18.sp)
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
                        onLongClick = { onGuideOpen(ch.id, ch.name) },
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
    onLongClick: () -> Unit,
) {
    Surface(
        onClick = onClick,
        modifier = Modifier
            .width(220.dp)
            .height(64.dp),
        shape = ClickableSurfaceDefaults.shape(shape = androidx.compose.foundation.shape.RoundedCornerShape(8.dp)),
        colors = ClickableSurfaceDefaults.colors(
            containerColor        = Color(0xFF1E1E1E),
            focusedContainerColor = Color(0xFFF89344),
            pressedContainerColor = Color(0xFFD4791E),
        ),
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
                color = Color.White,
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
        colors = ButtonDefaults.colors(
            containerColor        = Color(0xFF2E2E2E),
            focusedContainerColor = Color(0xFFF89344),
        ),
    ) {
        Text(text, fontSize = 16.sp, color = Color.White)
    }
}

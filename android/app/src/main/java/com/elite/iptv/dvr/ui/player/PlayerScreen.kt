package com.elite.iptv.dvr.ui.player

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import com.elite.iptv.dvr.api.ApiClient
import com.elite.iptv.dvr.viewmodel.MainViewModel
import kotlinx.coroutines.delay

@Composable
fun PlayerScreen(
    viewModel: MainViewModel,
    channelId: String,
    channelName: String,
    onBack: () -> Unit,
) {
    val context = LocalContext.current
    var isLoading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var loadedSegments by remember { mutableIntStateOf(0) }

    val player = remember {
        ExoPlayer.Builder(context).build().apply { playWhenReady = true }
    }

    // Release player and stop DVR when composable leaves the tree
    DisposableEffect(Unit) {
        onDispose {
            player.release()
            viewModel.stopDvrAsync()
        }
    }

    // Start DVR, wait for first segment, then poll for new ones
    LaunchedEffect(channelId) {
        isLoading = true
        error = null

        try {
            viewModel.startDvr(channelId, channelName)
        } catch (e: Exception) {
            error = "Failed to start DVR: ${e.message}"
            isLoading = false
            return@LaunchedEffect
        }

        // Wait up to 30 s for the first segment to appear
        var segs = emptyList<com.elite.iptv.dvr.api.DvrSegment>()
        repeat(15) {
            delay(2_000)
            segs = runCatching { viewModel.getDvrSegments() }.getOrElse { emptyList() }
            if (segs.isNotEmpty()) return@repeat
        }

        if (segs.isEmpty()) {
            error = "No stream data received. Is the PC running?"
            isLoading = false
            return@LaunchedEffect
        }

        // Build initial playlist
        val items = segs.map { seg ->
            MediaItem.fromUri(ApiClient.dvrSegmentUrl(viewModel.pcUrl, seg.name))
        }
        player.setMediaItems(items)
        player.prepare()
        loadedSegments = segs.size
        isLoading = false

        // Poll for new segments every 30 s
        while (true) {
            delay(30_000)
            val newSegs = try { viewModel.getDvrSegments() } catch (_: Exception) { continue }
            if (newSegs.size > loadedSegments) {
                newSegs.drop(loadedSegments).forEach { seg ->
                    player.addMediaItem(
                        MediaItem.fromUri(ApiClient.dvrSegmentUrl(viewModel.pcUrl, seg.name))
                    )
                }
                loadedSegments = newSegs.size
            }
        }
    }

    BackHandler { onBack() }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black),
    ) {
        AndroidView(
            factory = { ctx ->
                PlayerView(ctx).apply {
                    this.player = player
                    useController = true
                    setShowNextButton(false)
                    setShowPreviousButton(false)
                }
            },
            modifier = Modifier.fillMaxSize(),
        )

        if (isLoading) {
            Column(
                modifier = Modifier.align(Alignment.Center),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                CircularProgressIndicator(color = Color(0xFFF89344))
                Text(
                    text = "Starting DVR buffer for $channelName…",
                    color = Color.White,
                    fontSize = 18.sp,
                    modifier = Modifier.padding(top = 16.dp),
                )
            }
        }

        error?.let { msg ->
            Text(
                text = msg,
                color = Color(0xFFE74C3C),
                fontSize = 18.sp,
                modifier = Modifier
                    .align(Alignment.Center)
                    .padding(32.dp),
            )
        }
    }
}

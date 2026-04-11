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
import androidx.media3.common.AudioAttributes
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.DefaultLoadControl
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
    var playerView by remember { mutableStateOf<PlayerView?>(null) }

    val player = remember {
        ExoPlayer.Builder(context)
            .setAudioAttributes(AudioAttributes.DEFAULT, /* handleAudioFocus= */ true)
            .setLoadControl(
                DefaultLoadControl.Builder()
                    .setBufferDurationsMs(
                        /* minBufferMs             */ 30_000,
                        /* maxBufferMs             */ 60_000,
                        /* bufferForPlaybackMs     */ 4_000,
                        /* bufferForPlaybackAfterRebufferMs */ 8_000,
                    )
                    .setPrioritizeTimeOverSizeThresholds(true)
                    .build()
            )
            .build()
            .apply { playWhenReady = true }
    }

    DisposableEffect(Unit) {
        onDispose {
            player.release()
            viewModel.stopDvrAsync()
        }
    }

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

        // Wait for FFmpeg to produce at least 2 segments so the HLS manifest
        // is populated and ExoPlayer has something to start playing immediately.
        var ready = false
        repeat(25) {
            delay(800)
            val segs = runCatching { viewModel.getDvrSegments() }.getOrElse { emptyList() }
            if (segs.size >= 2) { ready = true; return@repeat }
        }

        if (!ready) {
            error = "No stream data received. Is the PC running?"
            isLoading = false
            return@LaunchedEffect
        }

        // Single HLS manifest URL. media3-exoplayer-hls auto-detects .m3u8 and
        // builds an HlsMediaSource; LiveConfiguration tells it to aim for the
        // live edge with a 6 s target offset and mild speed-ramp to catch up.
        val mediaItem = MediaItem.Builder()
            .setUri(ApiClient.dvrPlaylistUrl(viewModel.pcUrl))
            .setLiveConfiguration(
                MediaItem.LiveConfiguration.Builder()
                    // Stay 20 s behind live edge — segments are always ready,
                    // no chance of hitting the edge and stalling.
                    .setTargetOffsetMs(20_000)
                    .setMinOffsetMs(10_000)
                    .setMaxOffsetMs(40_000)
                    // No speed ramp — constant 1× playback, no audio pitch shifts.
                    .setMinPlaybackSpeed(1.0f)
                    .setMaxPlaybackSpeed(1.0f)
                    .build()
            )
            .build()

        player.setMediaItem(mediaItem)
        player.prepare()
        isLoading = false
    }

    // Keep nudging focus back to PlayerView so D-pad events (OK / arrows) always
    // reach the controller. `update` callback alone isn't enough — focus can be
    // stolen on surface updates and never recovered.
    LaunchedEffect(isLoading, error) {
        if (!isLoading && error == null) {
            while (true) {
                playerView?.let {
                    if (it.isAttachedToWindow && !it.hasFocus()) it.requestFocus()
                }
                delay(750)
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
                    setShowBuffering(PlayerView.SHOW_BUFFERING_WHEN_PLAYING)
                    keepScreenOn = true
                    controllerAutoShow = false
                    controllerHideOnTouch = true
                    setControllerShowTimeoutMs(4_000)
                    isFocusable = true
                    isFocusableInTouchMode = true
                }.also { playerView = it }
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

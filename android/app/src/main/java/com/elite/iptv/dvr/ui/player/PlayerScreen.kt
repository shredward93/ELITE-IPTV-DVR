@file:OptIn(androidx.tv.material3.ExperimentalTvMaterial3Api::class)

package com.elite.iptv.dvr.ui.player

/**
 * Live playback mirrors `static/remote.html` watch modes: Live DVR (`/api/preview/start` + HLS),
 * Original (`/api/stream/live`), Data saver (`/api/stream/mobile.m3u8?profile=data_saver`).
 * ExoPlayer + Media3 handle manifests; no per-channel codec forks here.
 */
import android.net.Uri
import android.view.View
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.AudioAttributes
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.DefaultLoadControl
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import androidx.tv.material3.Border
import androidx.tv.material3.Button
import androidx.tv.material3.ButtonDefaults
import com.elite.iptv.dvr.api.ApiClient
import com.elite.iptv.dvr.api.PreviewStartRequest
import com.elite.iptv.dvr.api.PreviewStopRequest
import com.elite.iptv.dvr.ui.theme.EliteColors
import com.elite.iptv.dvr.viewmodel.MainViewModel
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.delay
import java.net.URLEncoder

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
    var showQualityBar by remember { mutableStateOf(false) }

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

    LaunchedEffect(channelId, viewModel.watchMode) {
        var previewToStop: Int? = null
        isLoading = true
        error = null
        try {
            player.stop()
            player.clearMediaItems()

            when (viewModel.watchMode) {
                MainViewModel.WATCH_LIVE_DVR -> {
                    val res = ApiClient.service.startPreview(PreviewStartRequest(channelId))
                    if (!res.ok) {
                        error = res.error ?: "Live DVR failed"
                        isLoading = false
                        return@LaunchedEffect
                    }
                    val pid = res.previewId
                    val path = res.liveHlsUrl
                    if (pid == null || path.isNullOrBlank()) {
                        error = "Live DVR: invalid response"
                        isLoading = false
                        return@LaunchedEffect
                    }
                    previewToStop = pid
                    val uri = Uri.parse(ApiClient.resolvePlaybackUrl(viewModel.pcUrl, path))
                    player.setMediaItem(liveHlsMediaItem(uri))
                    player.prepare()
                }
                MainViewModel.WATCH_ORIGINAL -> {
                    val enc = URLEncoder.encode(channelId, "UTF-8")
                    val uri = Uri.parse(
                        ApiClient.resolvePlaybackUrl(viewModel.pcUrl, "api/stream/live?channel_id=$enc"),
                    )
                    player.setMediaItem(MediaItem.Builder().setUri(uri).build())
                    player.prepare()
                }
                MainViewModel.WATCH_DATA_SAVER -> {
                    val enc = URLEncoder.encode(channelId, "UTF-8")
                    val uri = Uri.parse(
                        ApiClient.resolvePlaybackUrl(
                            viewModel.pcUrl,
                            "api/stream/mobile.m3u8?channel_id=$enc&profile=data_saver",
                        ),
                    )
                    player.setMediaItem(liveHlsMediaItem(uri))
                    player.prepare()
                }
            }
            isLoading = false
            awaitCancellation()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            error = e.message ?: "Playback failed"
            isLoading = false
        } finally {
            previewToStop?.let { pid ->
                runCatching { ApiClient.service.stopPreview(PreviewStopRequest(pid)) }
            }
            viewModel.stopDvrAsync()
        }
    }

    BackHandler { onBack() }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(EliteColors.ink),
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
                    controllerAutoShow = true
                    controllerHideOnTouch = true
                    setControllerShowTimeoutMs(4_000)
                    isFocusable = true
                    isFocusableInTouchMode = true
                    setControllerVisibilityListener(
                        PlayerView.ControllerVisibilityListener { visibility ->
                            showQualityBar = visibility == View.VISIBLE
                        },
                    )
                }.also { playerView = it }
            },
            modifier = Modifier.fillMaxSize(),
        )

        if (isLoading) {
            Column(
                modifier = Modifier.align(Alignment.Center),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                CircularProgressIndicator(color = EliteColors.signal)
                Text(
                    text = "Loading $channelName…",
                    color = EliteColors.paper,
                    fontSize = 18.sp,
                    modifier = Modifier.padding(top = 16.dp),
                )
            }
        }

        error?.let { msg ->
            Text(
                text = msg,
                color = EliteColors.live,
                fontSize = 18.sp,
                modifier = Modifier
                    .align(Alignment.Center)
                    .padding(32.dp),
            )
        }

        if (showQualityBar && !isLoading && error == null) {
            WatchQualityBar(
                current = viewModel.watchMode,
                onSelect = viewModel::applyWatchMode,
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 36.dp),
            )
        }

    }
}

private fun liveHlsMediaItem(uri: Uri): MediaItem =
    MediaItem.Builder()
        .setUri(uri)
        .setLiveConfiguration(
            MediaItem.LiveConfiguration.Builder()
                .setTargetOffsetMs(20_000)
                .setMinOffsetMs(10_000)
                .setMaxOffsetMs(40_000)
                .setMinPlaybackSpeed(1.0f)
                .setMaxPlaybackSpeed(1.0f)
                .build(),
        )
        .build()

@Composable
private fun WatchQualityBar(
    current: String,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp, Alignment.CenterHorizontally),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = "QUALITY",
            color = EliteColors.paperMuted,
            fontSize = 10.sp,
            fontWeight = FontWeight.SemiBold,
            letterSpacing = 0.8.sp,
            modifier = Modifier.padding(end = 4.dp),
        )
        QualityModeButton(
            label = "Live DVR",
            mode = MainViewModel.WATCH_LIVE_DVR,
            current = current,
            onSelect = onSelect,
        )
        QualityModeButton(
            label = "Original",
            mode = MainViewModel.WATCH_ORIGINAL,
            current = current,
            onSelect = onSelect,
        )
        QualityModeButton(
            label = "Data saver",
            mode = MainViewModel.WATCH_DATA_SAVER,
            current = current,
            onSelect = onSelect,
        )
    }
}

@Composable
private fun QualityModeButton(
    label: String,
    mode: String,
    current: String,
    onSelect: (String) -> Unit,
) {
    val active = current == mode
    Button(
        onClick = { onSelect(mode) },
        modifier = Modifier.padding(0.dp),
        scale = ButtonDefaults.scale(scale = 1f, focusedScale = 1.04f, pressedScale = 1f),
        border = ButtonDefaults.border(
            border = Border.None,
            focusedBorder = Border(
                border = BorderStroke(2.dp, EliteColors.signal),
                inset = 0.dp,
                shape = RoundedCornerShape(8.dp),
            ),
        ),
        colors = ButtonDefaults.colors(
            containerColor = if (active) EliteColors.signal else EliteColors.surface3,
            contentColor = if (active) EliteColors.ink else EliteColors.paper,
            focusedContainerColor = EliteColors.signal,
            focusedContentColor = EliteColors.ink,
            pressedContainerColor = EliteColors.surface2,
            pressedContentColor = EliteColors.paper,
        ),
    ) {
        Text(label, fontSize = 13.sp, fontWeight = if (active) FontWeight.SemiBold else FontWeight.Medium)
    }
}

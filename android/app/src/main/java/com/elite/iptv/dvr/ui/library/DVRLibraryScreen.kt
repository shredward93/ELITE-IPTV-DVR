@file:OptIn(ExperimentalTvMaterial3Api::class)

package com.elite.iptv.dvr.ui.library

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import android.net.Uri
import androidx.media3.common.AudioAttributes
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.DefaultLoadControl
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.BorderStroke
import androidx.tv.material3.Border
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.ExperimentalTvMaterial3Api
import androidx.tv.material3.OutlinedButton
import androidx.tv.material3.OutlinedButtonDefaults
import androidx.tv.material3.Surface
import com.elite.iptv.dvr.api.ApiClient
import com.elite.iptv.dvr.api.ActiveRecording
import com.elite.iptv.dvr.api.CompletedRecording
import com.elite.iptv.dvr.ui.player.applyTvSeekIncrements
import com.elite.iptv.dvr.ui.player.applyTvTimeBarDpadIncrements
import com.elite.iptv.dvr.ui.theme.EliteColors
import com.elite.iptv.dvr.ui.theme.TvFocusDefaults
import com.elite.iptv.dvr.viewmodel.MainViewModel
import java.text.DecimalFormat
import kotlinx.coroutines.delay

@Composable
fun DVRLibraryScreen(
    viewModel: MainViewModel,
    onBack: () -> Unit,
) {
    LaunchedEffect(Unit) { viewModel.loadCompletedRecordings() }

    // Inline player state
    val context = LocalContext.current
    var playingUrl by remember { mutableStateOf<String?>(null) }
    var libraryPlayerView by remember { mutableStateOf<PlayerView?>(null) }
    val player = remember {
        ExoPlayer.Builder(context)
            .setAudioAttributes(AudioAttributes.DEFAULT, true)
            .applyTvSeekIncrements()
            .setLoadControl(
                DefaultLoadControl.Builder()
                    .setBufferDurationsMs(15_000, 60_000, 2_000, 5_000)
                    .build()
            )
            .build()
            .apply { playWhenReady = true }
    }

    BackHandler(playingUrl == null) { onBack() }
    BackHandler(playingUrl != null) {
        val pv = libraryPlayerView
        if (pv != null && pv.isControllerFullyVisible) {
            pv.hideController()
        } else {
            playingUrl = null
            player.stop()
        }
    }

    LaunchedEffect(playingUrl) {
        val url = playingUrl ?: run { player.stop(); return@LaunchedEffect }
        player.stop()
        player.clearMediaItems()
        // Direct .ts — supports range requests, so position 0 = true start of recording.
        player.setMediaItem(MediaItem.fromUri(Uri.parse(url)), /* startPositionMs= */ 0L)
        player.prepare()
        // Show controls immediately and keep focus on the PlayerView so remote keys work.
        libraryPlayerView?.showController()
        while (playingUrl != null) {
            libraryPlayerView?.let {
                if (it.isAttachedToWindow && !it.hasFocus()) it.requestFocus()
            }
            delay(750)
        }
    }
    androidx.compose.runtime.DisposableEffect(Unit) { onDispose { player.release() } }

    if (playingUrl != null) {
        Box(Modifier.fillMaxSize().background(EliteColors.ink)) {
            AndroidView(
                factory = { ctx ->
                    PlayerView(ctx).apply {
                        this.player = player
                        useController = true
                        setShowRewindButton(true)
                        setShowFastForwardButton(true)
                        setShowNextButton(false)
                        setShowPreviousButton(false)
                        setShowBuffering(PlayerView.SHOW_BUFFERING_WHEN_PLAYING)
                        keepScreenOn = true
                        controllerAutoShow = true
                        controllerHideOnTouch = true
                        setControllerShowTimeoutMs(5_000)
                        isFocusable = true
                        isFocusableInTouchMode = true
                    }.also { v ->
                        libraryPlayerView = v
                        v.applyTvTimeBarDpadIncrements()
                    }
                },
                modifier = Modifier.fillMaxSize(),
            )
        }
        return
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(EliteColors.ink)
            .padding(24.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "DVR Library",
                color = EliteColors.paper,
                fontSize = 26.sp,
                fontWeight = FontWeight.Bold,
            )
            OutlinedButton(
                onClick = onBack,
                scale = OutlinedButtonDefaults.scale(scale = 1f, focusedScale = 1.06f, pressedScale = 1f),
                border = OutlinedButtonDefaults.border(
                    border = Border(
                        border = BorderStroke(1.5.dp, EliteColors.rule),
                        inset = 0.dp,
                        shape = RoundedCornerShape(10.dp),
                    ),
                    focusedBorder = Border(
                        border = BorderStroke(2.dp, EliteColors.signal),
                        inset = 0.dp,
                        shape = RoundedCornerShape(10.dp),
                    ),
                ),
                colors = OutlinedButtonDefaults.colors(
                    containerColor = Color.Transparent,
                    contentColor = EliteColors.paperMuted,
                    focusedContainerColor = EliteColors.surface3,
                    focusedContentColor = EliteColors.signal,
                ),
            ) {
                Text("← Back", fontSize = 18.sp)
            }
        }

        if (viewModel.isLoading) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = EliteColors.signal)
            }
            return@Column
        }

        if (viewModel.activeRecordings.isEmpty() && viewModel.completedRecordings.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("No recordings yet.", color = EliteColors.paperMuted, fontSize = 20.sp)
            }
            return@Column
        }

        LazyColumn(
            contentPadding = PaddingValues(top = 16.dp, bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (viewModel.activeRecordings.isNotEmpty()) {
                item {
                    Text(
                        text = "Now Recording",
                        color = EliteColors.signal,
                        fontSize = 16.sp,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.padding(vertical = 4.dp),
                    )
                }
                items(viewModel.activeRecordings, key = { "active-${it.index}-${it.channelName}" }) { rec ->
                    ActiveRecordingRow(rec) { playPath ->
                        playingUrl = ApiClient.resolvePlaybackUrl(viewModel.pcUrl, playPath)
                    }
                }
                item {
                    Text(
                        text = "Completed",
                        color = EliteColors.paperMuted,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.padding(top = 10.dp, bottom = 4.dp),
                    )
                }
            }
            items(viewModel.completedRecordings, key = { it.filename }) { rec ->
                RecordingRow(rec) {
                    playingUrl = ApiClient.recordingUrl(viewModel.pcUrl, rec.filename)
                }
            }
        }
    }
}

@Composable
private fun ActiveRecordingRow(rec: ActiveRecording, onPlay: (playPath: String) -> Unit) {
    // Prefer the .ts file URL — it always plays from the start of the recording (byte 0)
    // and supports range requests for scrubbing. Fall back to live HLS if missing.
    val playPath = rec.tsUrl ?: rec.liveHlsUrl ?: return
    val interactionSource = remember { MutableInteractionSource() }
    val focused by interactionSource.collectIsFocusedAsState()
    Surface(
        onClick = { onPlay(playPath) },
        modifier = Modifier.fillMaxWidth().height(72.dp),
        shape = ClickableSurfaceDefaults.shape(shape = RoundedCornerShape(8.dp)),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = EliteColors.surface2,
            focusedContainerColor = EliteColors.signal,
        ),
        scale = TvFocusDefaults.surfaceScaleCard,
        border = ClickableSurfaceDefaults.border(
            border = Border(
                border = BorderStroke(1.dp, EliteColors.rule),
                inset = 0.dp,
                shape = RoundedCornerShape(8.dp),
            ),
            focusedBorder = Border(
                border = BorderStroke(2.dp, EliteColors.signal),
                inset = 0.dp,
                shape = RoundedCornerShape(8.dp),
            ),
        ),
        interactionSource = interactionSource,
    ) {
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 20.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column {
                Text(
                    text = rec.channelName,
                    color = if (focused) EliteColors.ink else EliteColors.paper,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Medium,
                )
                Text(
                    text = "Live recording in progress",
                    color = if (focused) EliteColors.ink.copy(alpha = 0.72f) else EliteColors.paperMuted,
                    fontSize = 14.sp,
                )
            }
            Text(
                text = "LIVE",
                color = if (focused) EliteColors.ink else EliteColors.signal,
                fontSize = 14.sp,
                fontWeight = FontWeight.Bold,
            )
        }
    }
}

@Composable
private fun RecordingRow(rec: CompletedRecording, onPlay: () -> Unit) {
    val interactionSource = remember { MutableInteractionSource() }
    val focused by interactionSource.collectIsFocusedAsState()
    Surface(
        onClick = onPlay,
        modifier = Modifier.fillMaxWidth().height(72.dp),
        shape = ClickableSurfaceDefaults.shape(shape = RoundedCornerShape(8.dp)),
        colors = ClickableSurfaceDefaults.colors(
            containerColor        = EliteColors.surface2,
            focusedContainerColor = EliteColors.signal,
        ),
        scale = TvFocusDefaults.surfaceScaleCard,
        border = ClickableSurfaceDefaults.border(
            border = Border(
                border = BorderStroke(1.dp, EliteColors.rule),
                inset = 0.dp,
                shape = RoundedCornerShape(8.dp),
            ),
            focusedBorder = Border(
                border = BorderStroke(2.dp, EliteColors.signal),
                inset = 0.dp,
                shape = RoundedCornerShape(8.dp),
            ),
        ),
        interactionSource = interactionSource,
    ) {
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 20.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column {
                Text(
                    text = rec.filename.removeSuffix(".ts"),
                    color = if (focused) EliteColors.ink else EliteColors.paper,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Medium,
                )
                Text(
                    text = rec.recordedAt.take(10),
                    color = if (focused) EliteColors.ink.copy(alpha = 0.72f) else EliteColors.paperMuted,
                    fontSize = 14.sp,
                )
            }
            Text(
                text = formatBytes(rec.sizeBytes),
                color = if (focused) EliteColors.ink.copy(alpha = 0.75f) else EliteColors.paperMuted,
                fontSize = 16.sp,
            )
        }
    }
}

private fun formatBytes(bytes: Long): String {
    if (bytes < 1_000_000) return "${bytes / 1_000} KB"
    if (bytes < 1_000_000_000) return "${DecimalFormat("0.0").format(bytes / 1_000_000.0)} MB"
    return "${DecimalFormat("0.0").format(bytes / 1_000_000_000.0)} GB"
}

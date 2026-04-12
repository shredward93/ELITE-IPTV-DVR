package com.elite.iptv.dvr.ui.player

import android.util.Log
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.MutableState
import androidx.compose.runtime.Stable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import com.elite.iptv.dvr.api.ApiClient

@Stable
class LivePlaybackState internal constructor(
    val player: ExoPlayer,
    val isLoading: MutableState<Boolean>,
    val error: MutableState<String?>,
    val isPlaying: MutableState<Boolean>,
)

@Composable
fun rememberLivePlaybackState(
    baseUrl: String,
    channelId: String,
    logTag: String = "ElitePlayer",
): LivePlaybackState {
    val context = LocalContext.current
    val isLoading = remember { mutableStateOf(true) }
    val error = remember { mutableStateOf<String?>(null) }
    val isPlaying = remember { mutableStateOf(false) }
    val exoPlayer = remember { ExoPlayer.Builder(context).build().apply { playWhenReady = true } }

    DisposableEffect(exoPlayer) {
        val listener = object : Player.Listener {
            override fun onPlaybackStateChanged(state: Int) {
                Log.d(logTag, "ExoPlayer state=$state playWhenReady=${exoPlayer.playWhenReady}")
                when (state) {
                    Player.STATE_BUFFERING -> isLoading.value = true
                    Player.STATE_READY -> {
                        isLoading.value = false
                        isPlaying.value = exoPlayer.isPlaying
                    }
                    Player.STATE_ENDED -> {
                        isLoading.value = false
                        isPlaying.value = false
                    }
                }
            }

            override fun onIsPlayingChanged(isPlayingNow: Boolean) {
                isPlaying.value = isPlayingNow
            }

            override fun onPlayerError(playbackError: PlaybackException) {
                Log.e(logTag, "ExoPlayer error", playbackError)
                error.value = "Playback error: ${playbackError.errorCodeName}"
                isLoading.value = false
                isPlaying.value = false
            }
        }

        exoPlayer.addListener(listener)

        onDispose {
            runCatching { exoPlayer.removeListener(listener) }
            runCatching { exoPlayer.stop() }
            runCatching { exoPlayer.clearMediaItems() }
            runCatching { exoPlayer.release() }
        }
    }

    LaunchedEffect(baseUrl, channelId) {
        isLoading.value = true
        error.value = null
        isPlaying.value = false

        try {
            val liveUrl = ApiClient.liveStreamUrl(baseUrl, channelId)
            runCatching { exoPlayer.stop() }
            runCatching { exoPlayer.clearMediaItems() }
            exoPlayer.setMediaItem(MediaItem.fromUri(liveUrl))
            exoPlayer.prepare()
            exoPlayer.playWhenReady = true
            Log.d(logTag, "ExoPlayer prepare requested url=$liveUrl")
        } catch (e: Exception) {
            error.value = "Failed to start playback: ${e.message}"
            isLoading.value = false
            isPlaying.value = false
        }
    }

    return remember(exoPlayer) {
        LivePlaybackState(
            player = exoPlayer,
            isLoading = isLoading,
            error = error,
            isPlaying = isPlaying,
        )
    }
}

@Composable
fun LivePlayerView(
    player: ExoPlayer,
    modifier: Modifier = Modifier,
    useController: Boolean = false,
) {
    AndroidView(
        factory = { ctx ->
            PlayerView(ctx).also { view ->
                view.player = player
                view.useController = useController
            }
        },
        modifier = modifier,
    )
}

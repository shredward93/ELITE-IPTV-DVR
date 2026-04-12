package com.elite.iptv.dvr.ui.player

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import android.net.Uri
import android.util.Log
import com.elite.iptv.dvr.api.ApiClient
import com.elite.iptv.dvr.viewmodel.MainViewModel
import androidx.compose.ui.platform.LocalContext
import org.videolan.libvlc.LibVLC
import org.videolan.libvlc.Media
import org.videolan.libvlc.MediaPlayer
import org.videolan.libvlc.util.VLCVideoLayout
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.cancel
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

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

    val libVlc = remember {
        LibVLC(
            context,
            arrayListOf(
                "--network-caching=3000",
                "--live-caching=3000",
                "--clock-jitter=0",
                "--clock-synchro=0",
            ),
        )
    }

    val mediaPlayer = remember { MediaPlayer(libVlc) }
    val cleanupScope = remember { CoroutineScope(SupervisorJob() + Dispatchers.Default) }

    DisposableEffect(mediaPlayer) {
        val listener = object : MediaPlayer.EventListener {
            override fun onEvent(event: MediaPlayer.Event) {
                Log.d("ElitePlayer", "libVLC event=$event")
            }
        }

        mediaPlayer.setEventListener(listener)
        onDispose {
            viewModel.stopDvrAsync()
            cleanupScope.launch {
                runCatching { mediaPlayer.setEventListener(null) }
                runCatching { mediaPlayer.stop() }
                runCatching { mediaPlayer.detachViews() }
                runCatching { mediaPlayer.media = null }
                runCatching { mediaPlayer.release() }
                runCatching { libVlc.release() }
                runCatching { cleanupScope.cancel() }
            }
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

        val playlistUrl = ApiClient.dvrPlaylistUrl(viewModel.pcUrl)
        val media = Media(libVlc, Uri.parse(playlistUrl)).apply {
            addOption(":network-caching=3000")
            addOption(":live-caching=3000")
            addOption(":clock-jitter=0")
            addOption(":clock-synchro=0")
        }

        try {
            runCatching { mediaPlayer.stop() }
            mediaPlayer.media = media
            mediaPlayer.play()
            Log.d("ElitePlayer", "libVLC play requested url=$playlistUrl")
        } catch (e: Exception) {
            error = "Failed to start VLC playback: ${e.message}"
            isLoading = false
            return@LaunchedEffect
        } finally {
            media.release()
        }

        isLoading = false
    }

    BackHandler { onBack() }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black),
    ) {
        AndroidView(
            factory = { ctx -> VLCVideoLayout(ctx).also { runCatching { mediaPlayer.attachViews(it, null, false, false) } } },
            modifier = Modifier.fillMaxSize(),
        )

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
        ) {
            Button(onClick = onBack) {
                Text("Back")
            }
        }

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

package com.elite.iptv.dvr.ui.player

import android.media.AudioAttributes
import android.media.MediaPlayer as AndroidMediaPlayer
import android.net.Uri
import android.util.Log
import android.view.SurfaceHolder
import android.view.SurfaceView
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.elite.iptv.dvr.api.ApiClient
import com.elite.iptv.dvr.viewmodel.MainViewModel
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
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
    var isPlaying by remember { mutableStateOf(false) }
    var surfaceHolder by remember { mutableStateOf<SurfaceHolder?>(null) }
    var surfaceView by remember { mutableStateOf<SurfaceView?>(null) }

    val mediaPlayer = remember { AndroidMediaPlayer() }
    val cleanupScope = remember { CoroutineScope(SupervisorJob() + Dispatchers.Default) }

    val surfaceCallback = remember(mediaPlayer) {
        object : SurfaceHolder.Callback {
            override fun surfaceCreated(holder: SurfaceHolder) {
                Log.d("ElitePlayer", "Surface created")
                surfaceHolder = holder
                runCatching { mediaPlayer.setSurface(holder.surface) }
            }

            override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) {
                Log.d("ElitePlayer", "Surface changed format=$format width=$width height=$height")
                surfaceHolder = holder
            }

            override fun surfaceDestroyed(holder: SurfaceHolder) {
                Log.d("ElitePlayer", "Surface destroyed")
                if (surfaceHolder == holder) {
                    surfaceHolder = null
                }
            }
        }
    }

    DisposableEffect(mediaPlayer) {
        val attrs = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_MEDIA)
            .setContentType(AudioAttributes.CONTENT_TYPE_MOVIE)
            .build()

        runCatching { mediaPlayer.setAudioAttributes(attrs) }

        mediaPlayer.setOnPreparedListener { mp ->
            Log.d("ElitePlayer", "Android MediaPlayer prepared")
            isLoading = false
            isPlaying = true
            runCatching { mp.start() }
        }

        mediaPlayer.setOnCompletionListener {
            Log.d("ElitePlayer", "Android MediaPlayer completed")
            isPlaying = false
            isLoading = false
        }

        mediaPlayer.setOnErrorListener { _, what, extra ->
            Log.e("ElitePlayer", "Android MediaPlayer error what=$what extra=$extra")
            error = "Playback error ($what/$extra)"
            isLoading = false
            isPlaying = false
            viewModel.stopDvrAsync()
            true
        }

        mediaPlayer.setOnInfoListener { _, what, extra ->
            Log.d("ElitePlayer", "Android MediaPlayer info what=$what extra=$extra")
            false
        }

        mediaPlayer.setOnVideoSizeChangedListener { _, width, height ->
            Log.d("ElitePlayer", "Android MediaPlayer video size width=$width height=$height")
        }

        onDispose {
            viewModel.stopDvrAsync()
            cleanupScope.launch {
                try {
                    runCatching { mediaPlayer.setOnPreparedListener(null) }
                    runCatching { mediaPlayer.setOnCompletionListener(null) }
                    runCatching { mediaPlayer.setOnErrorListener(null) }
                    runCatching { mediaPlayer.setOnInfoListener(null) }
                    runCatching { mediaPlayer.setOnVideoSizeChangedListener(null) }
                    runCatching { mediaPlayer.stop() }
                    runCatching { mediaPlayer.reset() }
                    runCatching { mediaPlayer.setSurface(null) }
                    runCatching { mediaPlayer.release() }
                } finally {
                    runCatching { cleanupScope.cancel() }
                }
            }
        }
    }

    DisposableEffect(surfaceView) {
        onDispose {
            surfaceView?.holder?.removeCallback(surfaceCallback)
        }
    }

    LaunchedEffect(channelId) {
        isLoading = true
        error = null
        isPlaying = false

        try {
            viewModel.startDvr(channelId, channelName)
        } catch (e: Exception) {
            error = "Failed to start DVR: ${e.message}"
            isLoading = false
            return@LaunchedEffect
        }

        // Wait for FFmpeg to produce at least 2 segments so the HLS manifest
        // is populated and the player has something to start playing immediately.
        var ready = false
        repeat(25) {
            delay(800)
            val segs = runCatching { viewModel.getDvrSegments() }.getOrElse { emptyList() }
            if (segs.size >= 2) {
                ready = true
                return@repeat
            }
        }

        if (!ready) {
            error = "No stream data received. Is the PC running?"
            isLoading = false
            return@LaunchedEffect
        }

        var holder: SurfaceHolder? = null
        repeat(25) {
            delay(100)
            holder = surfaceHolder
            if (holder?.surface?.isValid == true) {
                return@repeat
            }
        }

        if (holder?.surface?.isValid != true) {
            error = "Video surface not ready."
            isLoading = false
            return@LaunchedEffect
        }

        val playlistUrl = ApiClient.dvrPlaylistUrl(viewModel.pcUrl)

        try {
            runCatching { mediaPlayer.reset() }
            runCatching { mediaPlayer.setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MOVIE)
                    .build()
            ) }
            runCatching { mediaPlayer.setSurface(holder!!.surface) }
            mediaPlayer.setDataSource(context, Uri.parse(playlistUrl))
            mediaPlayer.prepareAsync()
            Log.d("ElitePlayer", "Android MediaPlayer prepare requested url=$playlistUrl")
        } catch (e: Exception) {
            error = "Failed to start playback: ${e.message}"
            isLoading = false
            isPlaying = false
            viewModel.stopDvrAsync()
            return@LaunchedEffect
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
                SurfaceView(ctx).also { view ->
                    surfaceView = view
                    view.holder.addCallback(surfaceCallback)
                }
            },
            modifier = Modifier.fillMaxSize(),
        )

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Button(onClick = onBack) {
                Text("Back")
            }

            Button(
                enabled = !isLoading && error == null,
                onClick = {
                    if (mediaPlayer.isPlaying) {
                        runCatching { mediaPlayer.pause() }
                        isPlaying = false
                    } else {
                        runCatching { mediaPlayer.start() }
                        isPlaying = true
                    }
                },
            ) {
                Text(if (isPlaying) "Pause" else "Play")
            }

            Text(
                text = channelName,
                color = Color.White,
                fontSize = 16.sp,
                fontWeight = FontWeight.SemiBold,
            )
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

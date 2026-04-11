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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.ExperimentalTvMaterial3Api
import androidx.tv.material3.Surface
import com.elite.iptv.dvr.api.ApiClient
import com.elite.iptv.dvr.api.CompletedRecording
import com.elite.iptv.dvr.viewmodel.MainViewModel
import java.text.DecimalFormat

@Composable
fun DVRLibraryScreen(
    viewModel: MainViewModel,
    onBack: () -> Unit,
) {
    LaunchedEffect(Unit) { viewModel.loadCompletedRecordings() }

    BackHandler { onBack() }

    // Inline player state
    val context = LocalContext.current
    var playingFile by remember { mutableStateOf<String?>(null) }
    val player = remember { ExoPlayer.Builder(context).build().apply { playWhenReady = true } }
    LaunchedEffect(playingFile) {
        val file = playingFile ?: run { player.stop(); return@LaunchedEffect }
        val url = ApiClient.recordingUrl(viewModel.pcUrl, file)
        player.setMediaItem(MediaItem.fromUri(url))
        player.prepare()
    }
    androidx.compose.runtime.DisposableEffect(Unit) { onDispose { player.release() } }

    if (playingFile != null) {
        Box(Modifier.fillMaxSize().background(Color.Black)) {
            AndroidView(
                factory = { ctx -> PlayerView(ctx).also { it.player = player } },
                modifier = Modifier.fillMaxSize(),
            )
            TextButton(
                onClick = { playingFile = null; player.stop() },
                modifier = Modifier.align(Alignment.TopStart).padding(16.dp),
            ) {
                Text("← Back", color = Color.White, fontSize = 18.sp)
            }
        }
        return
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black)
            .padding(24.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "DVR Library",
                color = Color.White,
                fontSize = 26.sp,
                fontWeight = FontWeight.Bold,
            )
            TextButton(onClick = onBack) {
                Text("← Back", color = Color(0xFFF89344), fontSize = 18.sp)
            }
        }

        if (viewModel.isLoading) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = Color(0xFFF89344))
            }
            return@Column
        }

        if (viewModel.completedRecordings.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("No recordings yet.", color = Color.Gray, fontSize = 20.sp)
            }
            return@Column
        }

        LazyColumn(
            contentPadding = PaddingValues(top = 16.dp, bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(viewModel.completedRecordings, key = { it.filename }) { rec ->
                RecordingRow(rec) { playingFile = rec.filename }
            }
        }
    }
}

@Composable
private fun RecordingRow(rec: CompletedRecording, onPlay: () -> Unit) {
    Surface(
        onClick = onPlay,
        modifier = Modifier.fillMaxWidth().height(72.dp),
        shape = ClickableSurfaceDefaults.shape(shape = androidx.compose.foundation.shape.RoundedCornerShape(8.dp)),
        colors = ClickableSurfaceDefaults.colors(
            containerColor        = Color(0xFF1E1E1E),
            focusedContainerColor = Color(0xFFF89344),
        ),
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
                    color = Color.White,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Medium,
                )
                Text(
                    text = rec.recordedAt.take(10),
                    color = Color.Gray,
                    fontSize = 14.sp,
                )
            }
            Text(
                text = formatBytes(rec.sizeBytes),
                color = Color.Gray,
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

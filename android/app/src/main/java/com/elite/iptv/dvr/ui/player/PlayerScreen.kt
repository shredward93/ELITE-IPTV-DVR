package com.elite.iptv.dvr.ui.player

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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.elite.iptv.dvr.viewmodel.MainViewModel

@Composable
fun PlayerScreen(
    viewModel: MainViewModel,
    channelId: String,
    channelName: String,
    onBack: () -> Unit,
) {
    val playback = rememberLivePlaybackState(viewModel.pcUrl, channelId, logTag = "ElitePlayer")

    BackHandler { onBack() }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black),
    ) {
        LivePlayerView(
            player = playback.player,
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
                enabled = !playback.isLoading.value && playback.error.value == null,
                onClick = {
                    if (playback.player.isPlaying) {
                        playback.player.pause()
                        playback.isPlaying.value = false
                    } else {
                        playback.player.play()
                        playback.isPlaying.value = true
                    }
                },
            ) {
                Text(if (playback.isPlaying.value) "Pause" else "Play")
            }

            Text(
                text = channelName,
                color = Color.White,
                fontSize = 16.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }

        if (playback.isLoading.value) {
            Column(
                modifier = Modifier.align(Alignment.Center),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                CircularProgressIndicator(color = Color(0xFFF89344))
                Text(
                    text = "Connecting to live stream for $channelName…",
                    color = Color.White,
                    fontSize = 18.sp,
                    modifier = Modifier.padding(top = 16.dp),
                )
            }
        }

        playback.error.value?.let { msg ->
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

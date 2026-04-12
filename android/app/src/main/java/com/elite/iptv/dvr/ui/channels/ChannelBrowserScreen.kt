package com.elite.iptv.dvr.ui.channels

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.TileMode
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.compose.ui.unit.dp

@Composable
fun ChannelBrowserScreen(
    onGuideGridOpen: () -> Unit,
    onLibraryOpen: () -> Unit,
    onSettingsOpen: () -> Unit,
) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black)
            .padding(horizontal = 24.dp, vertical = 18.dp),
    ) {
        Column(
            modifier = Modifier
                .align(Alignment.Center),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = "ELITE IPTV DVR",
                style = TextStyle(
                    brush = Brush.horizontalGradient(
                        colors = listOf(
                            Color(0xFFFF4DB8),
                            Color(0xFFFFA36C),
                            Color(0xFFFFD54D),
                        ),
                        tileMode = TileMode.Clamp,
                    ),
                    fontSize = 48.sp,
                    lineHeight = 52.sp,
                    fontWeight = FontWeight.Bold,
                ),
            )
            Spacer(Modifier.height(32.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(18.dp)) {
                HomePillButton(text = "TV Guide", gradient = true, onClick = onGuideGridOpen)
                HomePillButton(text = "DVR Library", onClick = onLibraryOpen)
                HomePillButton(text = "Settings", onClick = onSettingsOpen)
            }
        }
    }
}

@Composable
private fun HomePillButton(
    text: String,
    onClick: () -> Unit,
    gradient: Boolean = false,
    modifier: Modifier = Modifier,
) {
    var focused by remember { mutableStateOf(false) }

    Box(
        modifier = modifier
            .size(width = 160.dp, height = 52.dp)
            .border(
                width = 3.dp,
                color = if (focused) Color(0xFFFFD24C) else Color.Transparent,
                shape = RoundedCornerShape(26.dp),
            )
            .background(
                color = when {
                    focused && gradient -> Color(0xFFF6A24D)
                    focused -> Color(0xFF8A8A8A)
                    gradient -> Color(0xFFF89344)
                    else -> Color(0xFF7A7A7A)
                },
                shape = RoundedCornerShape(26.dp),
            )
            .onFocusChanged {
                focused = it.isFocused || it.hasFocus
            }
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = text,
            fontSize = 16.sp,
            fontWeight = FontWeight.SemiBold,
            color = if (gradient) Color.White else Color.Black,
        )
    }
}

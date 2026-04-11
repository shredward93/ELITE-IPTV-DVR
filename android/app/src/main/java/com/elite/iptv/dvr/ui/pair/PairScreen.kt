package com.elite.iptv.dvr.ui.pair

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.elite.iptv.dvr.viewmodel.MainViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun PairScreen(viewModel: MainViewModel, onConnected: () -> Unit) {
    var url by remember { mutableStateOf(viewModel.pcUrl) }
    var status by remember { mutableStateOf("") }
    var isError by remember { mutableStateOf(false) }
    var isConnecting by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    fun connect() {
        if (url.isBlank() || isConnecting) return
        scope.launch {
            isConnecting = true
            isError = false
            status = "Connecting…"
            try {
                viewModel.savePcUrl(url.trim())
                val info = viewModel.testConnection()
                status = "Connected — ${info.channelCount} channels available"
                isError = false
                delay(900)
                onConnected()
            } catch (e: Exception) {
                status = "Could not connect: ${e.message ?: "unknown error"}"
                isError = true
            }
            isConnecting = false
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            modifier = Modifier
                .width(520.dp)
                .padding(32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Text(
                text = "ELITE IPTV DVR",
                color = Color(0xFFF89344),
                fontSize = 32.sp,
                fontWeight = FontWeight.Bold,
            )
            Spacer(Modifier.height(6.dp))
            Text(
                text = "Enter your PC's address to connect",
                color = Color.Gray,
                fontSize = 18.sp,
            )
            Spacer(Modifier.height(36.dp))

            OutlinedTextField(
                value = url,
                onValueChange = { url = it },
                label = { Text("PC Address", fontSize = 16.sp) },
                placeholder = { Text("http://192.168.1.100:8080") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Uri,
                    imeAction = ImeAction.Done,
                ),
                keyboardActions = KeyboardActions(onDone = { connect() }),
            )

            Spacer(Modifier.height(20.dp))

            Button(
                onClick = { connect() },
                enabled = url.isNotBlank() && !isConnecting,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
            ) {
                if (isConnecting) {
                    CircularProgressIndicator(
                        modifier = Modifier.height(20.dp).width(20.dp),
                        strokeWidth = 2.dp,
                        color = Color.White,
                    )
                } else {
                    Text("Connect", fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
                }
            }

            if (status.isNotEmpty()) {
                Spacer(Modifier.height(20.dp))
                Text(
                    text = status,
                    color = if (isError) Color(0xFFE74C3C) else Color(0xFF2ECC71),
                    fontSize = 16.sp,
                )
            }
        }
    }
}

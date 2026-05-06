@file:OptIn(androidx.tv.material3.ExperimentalTvMaterial3Api::class)

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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.BorderStroke
import androidx.tv.material3.Border
import androidx.tv.material3.Button
import androidx.tv.material3.ButtonDefaults
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.elite.iptv.dvr.ui.theme.EliteColors
import com.elite.iptv.dvr.viewmodel.MainViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun PairScreen(viewModel: MainViewModel, onConnected: () -> Unit) {
    var url by remember { mutableStateOf(viewModel.pcUrl) }
    var status by remember { mutableStateOf("") }
    var isError by remember { mutableStateOf(false) }
    var isConnecting by remember { mutableStateOf(false) }
    var failoverSecsText by remember { mutableStateOf(viewModel.recordingFailoverSecs.toString()) }
    var categorySyncEnabled by remember { mutableStateOf(viewModel.categoryFavoritesSync) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(viewModel.pcUrl) {
        if (viewModel.pcUrl.isNotBlank()) {
            runCatching { viewModel.loadRecordingSettings() }
                .onSuccess {
                    failoverSecsText = viewModel.recordingFailoverSecs.toString()
                    categorySyncEnabled = viewModel.categoryFavoritesSync
                }
        }
    }

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
            .background(EliteColors.ink),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            modifier = Modifier
                .width(520.dp)
                .background(EliteColors.surface, RoundedCornerShape(14.dp))
                .padding(28.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Text(
                text = "ELITE IPTV DVR",
                color = EliteColors.signal,
                fontSize = 32.sp,
                fontWeight = FontWeight.Bold,
            )
            Spacer(Modifier.height(6.dp))
            Text(
                text = "Enter your PC's address to connect",
                color = EliteColors.paperMuted,
                fontSize = 18.sp,
            )
            Spacer(Modifier.height(36.dp))

            OutlinedTextField(
                value = url,
                onValueChange = { url = it },
                label = { Text("PC Address", fontSize = 16.sp, color = EliteColors.paperMuted) },
                placeholder = { Text("http://192.168.1.100:8080", color = EliteColors.paperMuted) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Uri,
                    imeAction = ImeAction.Done,
                ),
                keyboardActions = KeyboardActions(onDone = { connect() }),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = EliteColors.signal,
                    unfocusedBorderColor = EliteColors.ruleBright,
                    focusedTextColor = EliteColors.paper,
                    unfocusedTextColor = EliteColors.paper,
                    cursorColor = EliteColors.signal,
                    focusedLabelColor = EliteColors.signal,
                    unfocusedLabelColor = EliteColors.pickerUnselected,
                ),
            )

            Spacer(Modifier.height(20.dp))

            Button(
                onClick = { connect() },
                enabled = url.isNotBlank() && !isConnecting,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
                scale = ButtonDefaults.scale(scale = 1f, focusedScale = 1.04f, pressedScale = 1f),
                border = ButtonDefaults.border(
                    border = Border.None,
                    focusedBorder = Border(
                        border = BorderStroke(2.dp, EliteColors.paper),
                        inset = 0.dp,
                        shape = RoundedCornerShape(12.dp),
                    ),
                ),
                colors = ButtonDefaults.colors(
                    containerColor = EliteColors.signal,
                    contentColor = EliteColors.ink,
                    focusedContainerColor = EliteColors.signal,
                    focusedContentColor = EliteColors.ink,
                    disabledContainerColor = EliteColors.surface3,
                    disabledContentColor = EliteColors.paperMuted,
                ),
            ) {
                if (isConnecting) {
                    CircularProgressIndicator(
                        modifier = Modifier.height(20.dp).width(20.dp),
                        strokeWidth = 2.dp,
                        color = EliteColors.ink,
                    )
                } else {
                    Text("Connect", fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
                }
            }

            if (viewModel.pcUrl.isNotBlank()) {
                Spacer(Modifier.height(20.dp))
                OutlinedTextField(
                    value = failoverSecsText,
                    onValueChange = { failoverSecsText = it.filter(Char::isDigit).take(3) },
                    label = { Text("Recorder failover seconds (5-300)", fontSize = 14.sp, color = EliteColors.paperMuted) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Done),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = EliteColors.signal,
                        unfocusedBorderColor = EliteColors.ruleBright,
                        focusedTextColor = EliteColors.paper,
                        unfocusedTextColor = EliteColors.paper,
                        cursorColor = EliteColors.signal,
                        focusedLabelColor = EliteColors.signal,
                        unfocusedLabelColor = EliteColors.pickerUnselected,
                    ),
                )
                Spacer(Modifier.height(10.dp))
                Box(modifier = Modifier.fillMaxWidth()) {
                    Text(
                        text = "Sync favorite categories across devices",
                        color = EliteColors.paperMuted,
                        fontSize = 14.sp,
                        modifier = Modifier.align(Alignment.CenterStart),
                    )
                    Switch(
                        checked = categorySyncEnabled,
                        onCheckedChange = { categorySyncEnabled = it },
                        modifier = Modifier.align(Alignment.CenterEnd),
                    )
                }
                Spacer(Modifier.height(10.dp))
                Button(
                    onClick = {
                        scope.launch {
                            val secs = failoverSecsText.toIntOrNull()
                            if (secs == null || secs !in 5..300) {
                                status = "Failover seconds must be 5-300"
                                isError = true
                                return@launch
                            }
                            runCatching { viewModel.saveRecordingFailoverSecs(secs) }
                                .onSuccess {
                                    runCatching { viewModel.saveCategoryFavoritesSync(categorySyncEnabled) }
                                        .onSuccess {
                                            failoverSecsText = viewModel.recordingFailoverSecs.toString()
                                            categorySyncEnabled = viewModel.categoryFavoritesSync
                                            status = "Settings saved (${viewModel.recordingFailoverSecs}s failover)"
                                            isError = false
                                        }
                                        .onFailure {
                                            status = "Could not save category sync setting"
                                            isError = true
                                        }
                                }
                                .onFailure {
                                    status = "Could not save failover setting"
                                    isError = true
                                }
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp),
                    colors = ButtonDefaults.colors(
                        containerColor = EliteColors.surface3,
                        contentColor = EliteColors.paper,
                        focusedContainerColor = EliteColors.signal,
                        focusedContentColor = EliteColors.ink,
                    ),
                ) {
                    Text("Save Recorder Setting", fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                }
            }

            if (status.isNotEmpty()) {
                Spacer(Modifier.height(20.dp))
                Text(
                    text = status,
                    color = if (isError) EliteColors.live else EliteColors.ok,
                    fontSize = 16.sp,
                )
            }
        }
    }
}

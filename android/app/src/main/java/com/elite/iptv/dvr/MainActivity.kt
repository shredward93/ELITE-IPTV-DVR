package com.elite.iptv.dvr

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import com.elite.iptv.dvr.ui.EliteNavHost
import com.elite.iptv.dvr.ui.theme.EliteColors
import com.elite.iptv.dvr.viewmodel.MainViewModel

class MainActivity : ComponentActivity() {

    private val viewModel: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            androidx.compose.material3.Surface(
                modifier = Modifier.fillMaxSize().background(EliteColors.ink),
                color = EliteColors.ink,
            ) {
                EliteNavHost(viewModel)
            }
        }
    }
}

package com.elite.iptv.dvr.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.compose.ui.unit.dp
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.elite.iptv.dvr.ui.channels.ChannelBrowserScreen
import com.elite.iptv.dvr.ui.guide.GuideGridScreen
import com.elite.iptv.dvr.ui.guide.TVGuideScreen
import com.elite.iptv.dvr.ui.library.DVRLibraryScreen
import com.elite.iptv.dvr.ui.pair.PairScreen
import com.elite.iptv.dvr.ui.player.PlayerScreen
import com.elite.iptv.dvr.viewmodel.MainViewModel
import java.net.URLDecoder
import java.net.URLEncoder

sealed class Screen(val route: String) {
    object Pair      : Screen("pair")
    object Channels  : Screen("channels")
    object Library   : Screen("library")
    object GuideGrid : Screen("guide_grid")

    object Player : Screen("player/{channelId}/{channelName}") {
        fun go(id: String, name: String) =
            "player/$id/${URLEncoder.encode(name, "UTF-8")}"
    }

    object Guide : Screen("guide/{channelId}/{channelName}") {
        fun go(id: String, name: String) =
            "guide/$id/${URLEncoder.encode(name, "UTF-8")}"
    }
}

@Composable
fun EliteNavHost(viewModel: MainViewModel) {
    val nav = rememberNavController()
    val start = if (viewModel.pcUrl.isEmpty()) Screen.Pair.route else Screen.Channels.route

    NavHost(navController = nav, startDestination = start) {

        composable(Screen.Pair.route) {
            PairScreen(viewModel) {
                nav.navigate(Screen.Channels.route) {
                    popUpTo(Screen.Pair.route) { inclusive = true }
                }
            }
        }

        composable(Screen.Channels.route) {
            ChannelBrowserScreen(
                onGuideGridOpen = { nav.navigate(Screen.GuideGrid.route) },
                onLibraryOpen   = { nav.navigate(Screen.Library.route) },
                onSettingsOpen  = { nav.navigate(Screen.Pair.route) },
            )
        }

        composable(Screen.GuideGrid.route) {
            GuideGridScreen(
                viewModel     = viewModel,
                onChannelPlay = { id, name -> nav.navigate(Screen.Player.go(id, name)) },
                onBack        = { nav.popBackStack() },
            )
        }

        composable(
            Screen.Player.route,
            arguments = listOf(
                navArgument("channelId")   { type = NavType.StringType },
                navArgument("channelName") { type = NavType.StringType },
            ),
        ) { back ->
            PlayerScreen(
                viewModel   = viewModel,
                channelId   = back.arguments?.getString("channelId") ?: "",
                channelName = URLDecoder.decode(back.arguments?.getString("channelName") ?: "", "UTF-8"),
                onBack      = { nav.popBackStack() },
            )
        }

        composable(
            Screen.Guide.route,
            arguments = listOf(
                navArgument("channelId")   { type = NavType.StringType },
                navArgument("channelName") { type = NavType.StringType },
            ),
        ) { back ->
            val id   = back.arguments?.getString("channelId") ?: ""
            val name = URLDecoder.decode(back.arguments?.getString("channelName") ?: "", "UTF-8")
            TVGuideScreen(
                viewModel   = viewModel,
                channelId   = id,
                channelName = name,
                onPlayLive  = { nav.navigate(Screen.Player.go(id, name)) },
                onBack      = { nav.popBackStack() },
            )
        }

        composable(Screen.Library.route) {
            DVRLibraryScreen(
                viewModel = viewModel,
                onBack    = { nav.popBackStack() },
            )
        }
    }
}

@Composable
private fun GuideProbeScreen(
    onBack: () -> Unit,
) {
    BackHandler { onBack() }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black)
            .padding(24.dp),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Text(
                text = "TV Guide Probe",
                color = Color.White,
                fontSize = 28.sp,
                fontWeight = FontWeight.Bold,
            )
            Spacer(Modifier.height(12.dp))
            Text(
                text = "If this screen opens, the crash is inside the guide UI.",
                color = Color(0xFFBDBDBD),
                fontSize = 16.sp,
            )
            Spacer(Modifier.height(20.dp))
            Button(
                onClick = onBack,
                colors = ButtonDefaults.buttonColors(
                    containerColor = Color(0xFFF89344),
                    contentColor = Color.White,
                ),
            ) {
                Text("Back")
            }
        }
    }
}

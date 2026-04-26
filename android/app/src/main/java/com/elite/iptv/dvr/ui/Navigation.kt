package com.elite.iptv.dvr.ui

import androidx.compose.runtime.Composable
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.elite.iptv.dvr.ui.channels.ChannelBrowserScreen
import com.elite.iptv.dvr.ui.guide.EpgGuideScreen
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
                viewModel         = viewModel,
                onChannelSelected = { id, name -> nav.navigate(Screen.Player.go(id, name)) },
                onGuideOpen       = { id, name -> nav.navigate(Screen.Guide.go(id, name)) },
                onGuideGridOpen   = { nav.navigate(Screen.GuideGrid.route) },
                onLibraryOpen     = { nav.navigate(Screen.Library.route) },
                onSettingsOpen    = { nav.navigate(Screen.Pair.route) },
            )
        }

        composable(Screen.GuideGrid.route) {
            EpgGuideScreen(
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

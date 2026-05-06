package com.elite.iptv.dvr.ui.player

import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.DefaultTimeBar
import androidx.media3.ui.PlayerView
import androidx.media3.ui.R as Media3R

/**
 * Without this, [DefaultTimeBar] uses `duration / 20` per D-pad step ([androidx.media3.ui.DefaultTimeBar]
 * default), so a 3h recording jumps ~9 minutes per tick.
 */
private const val TIME_BAR_DPAD_INCREMENT_MS = 8_000L

/** RW / FF buttons — smaller than media3 defaults for TV remotes (hold-to-repeat stacks steps). */
private const val SEEK_BACK_MS = 5_000L
private const val SEEK_FORWARD_MS = 8_000L

fun ExoPlayer.Builder.applyTvSeekIncrements(): ExoPlayer.Builder =
    setSeekBackIncrementMs(SEEK_BACK_MS).setSeekForwardIncrementMs(SEEK_FORWARD_MS)

/** Call after [PlayerView] is attached (e.g. inside [PlayerView.post]). */
fun PlayerView.applyTvTimeBarDpadIncrements() {
    post {
        findViewById<DefaultTimeBar>(Media3R.id.exo_progress)
            ?.setKeyTimeIncrement(TIME_BAR_DPAD_INCREMENT_MS)
    }
}

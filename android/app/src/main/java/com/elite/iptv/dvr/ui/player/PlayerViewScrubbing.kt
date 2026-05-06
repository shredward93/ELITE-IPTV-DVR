package com.elite.iptv.dvr.ui.player

import android.view.View
import androidx.media3.ui.DefaultTimeBar
import androidx.media3.ui.PlayerView
import androidx.media3.ui.R as Media3UiR

/** D-pad steps on the timeline + RW/FF — TiviMate-like ~10s nudges (not multi-minute jumps). */
const val TV_SCRUB_STEP_MS = 10_000L

/**
 * Media3 [DefaultTimeBar] uses very large position steps for D-pad / accessibility by default
 * (often several minutes on long assets), which feels nothing like TiviMate playhead nudges.
 * [keyIncrementMs] should match ExoPlayer seek button increments.
 */
fun PlayerView.configurePlayheadKeyScrubbing(keyIncrementMs: Long) {
    val apply: () -> Unit = {
        findViewById<DefaultTimeBar>(Media3UiR.id.exo_progress)?.setKeyTimeIncrement(keyIncrementMs)
    }
    setControllerVisibilityListener { visibility ->
        if (visibility == View.VISIBLE) post(apply)
    }
    post(apply)
}

fun PlayerView.configureTiviMateStylePlayheadScrubbing() {
    configurePlayheadKeyScrubbing(TV_SCRUB_STEP_MS)
}

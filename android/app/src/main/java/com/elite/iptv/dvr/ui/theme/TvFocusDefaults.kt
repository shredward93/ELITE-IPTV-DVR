package com.elite.iptv.dvr.ui.theme

import androidx.tv.material3.ClickableSurfaceDefaults

/**
 * Shared TV focus affordance — subtle lift on focus so D-pad navigation reads clearly
 * without fighting dense grids (TiviMate-like clarity, not flashy motion).
 */
object TvFocusDefaults {
    val surfaceScaleCard = ClickableSurfaceDefaults.scale(
        scale = 1f,
        focusedScale = 1.06f,
        pressedScale = 1f,
    )

    val surfaceScaleCompact = ClickableSurfaceDefaults.scale(
        scale = 1f,
        focusedScale = 1.035f,
        pressedScale = 1f,
    )

    val surfaceScaleRail = ClickableSurfaceDefaults.scale(
        scale = 1f,
        focusedScale = 1.02f,
        pressedScale = 1f,
    )
}

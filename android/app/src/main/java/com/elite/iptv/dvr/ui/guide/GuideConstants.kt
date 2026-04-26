package com.elite.iptv.dvr.ui.guide

/**
 * Shared TV guide time window (must match [EpgGuideScreen] timeline width).
 * Server requests use the same bounds so payloads stay small and scroll stays fast.
 */
object GuideConstants {
    const val WINDOW_PRE_MINUTES = 30L
    const val WINDOW_TOTAL_MINUTES = 180L

    /** Inclusive-ish window [start, end) in unix ms for API filtering. */
    fun windowBounds(nowMs: Long = System.currentTimeMillis()): Pair<Long, Long> {
        val start = nowMs - WINDOW_PRE_MINUTES * 60_000L
        val end = start + WINDOW_TOTAL_MINUTES * 60_000L
        return start to end
    }
}

package com.elite.iptv.dvr.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * Visual tokens aligned with the mobile webapp (`static/remote.html` `:root`).
 * TiviMate-inspired usage: very dark panes, thin rules, **signal orange** for
 * selection / “now”, cool grey surfaces — same palette the web guide already proves.
 */
object EliteColors {
    val ink = Color(0xFF0A0A0C)
    val inkSoft = Color(0xFF101014)
    val surface = Color(0xFF15151B)
    val surface2 = Color(0xFF1C1C24)
    val surface3 = Color(0xFF232330)
    val rule = Color(0xFF2A2A35)
    val paper = Color(0xFFF4EFE3)
    val paper2 = Color(0xFFC9C3B4)
    val paperMuted = Color(0xFF7A7668)
    val signal = Color(0xFFFF8C42)
    /** Orange wash (~18% α) for “now” rows — same intent as `--signal-soft` on web. */
    val signalSoft = Color(0x2EFF8C42)
    val live = Color(0xFFFF2E4D)
    val ok = Color(0xFF78E0A7)
}

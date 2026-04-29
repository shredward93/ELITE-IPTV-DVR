package com.elite.iptv.dvr.viewmodel

import android.app.Application
import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.elite.iptv.dvr.api.ApiClient
import com.elite.iptv.dvr.api.Category
import com.elite.iptv.dvr.api.Channel
import com.elite.iptv.dvr.api.CompletedRecording
import com.elite.iptv.dvr.api.DvrSegment
import com.elite.iptv.dvr.api.DvrStartRequest
import com.elite.iptv.dvr.api.EpgListing
import com.elite.iptv.dvr.api.FavoriteRequest
import com.elite.iptv.dvr.api.ScheduleRequest
import com.elite.iptv.dvr.api.ServerInfo
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class MainViewModel(application: Application) : AndroidViewModel(application) {

    companion object {
        private const val GUIDE_EPG_CHUNK = 8
        private const val GUIDE_EPG_LISTING_LIMIT = 12
        const val WATCH_LIVE_DVR = "live_dvr"
        const val WATCH_ORIGINAL = "original"
        const val WATCH_DATA_SAVER = "data_saver"
    }

    private val prefs = application.getSharedPreferences("elite_dvr", Context.MODE_PRIVATE)

    /** Cancels stale single-channel EPG responses when the user changes channel quickly. */
    private var epgRequestGeneration = 0

    var pcUrl by mutableStateOf(prefs.getString("pc_url", "") ?: "")
        private set

    var favorites by mutableStateOf<List<Channel>>(emptyList())
        private set

    var searchResults by mutableStateOf<List<Channel>>(emptyList())
        private set

    var epgListings by mutableStateOf<List<EpgListing>>(emptyList())
        private set

    var categories by mutableStateOf<List<Category>>(emptyList())
        private set

    var categoryChannels by mutableStateOf<List<Channel>>(emptyList())
        private set

    var guideEpg by mutableStateOf<Map<String, List<EpgListing>>>(emptyMap())
        private set

    var completedRecordings by mutableStateOf<List<CompletedRecording>>(emptyList())
        private set

    var isLoading by mutableStateOf(false)
        private set

    var errorMessage by mutableStateOf<String?>(null)
        private set

    /** Same modes as `static/remote.html` watch bar (`eliteWatchMode`). */
    var watchMode by mutableStateOf(
        prefs.getString("watch_mode", WATCH_LIVE_DVR) ?: WATCH_LIVE_DVR,
    )
        private set

    fun applyWatchMode(mode: String) {
        val m = when (mode) {
            WATCH_LIVE_DVR, WATCH_ORIGINAL, WATCH_DATA_SAVER -> mode
            else -> WATCH_LIVE_DVR
        }
        if (m == watchMode) return
        watchMode = m
        prefs.edit().putString("watch_mode", m).apply()
    }

    init {
        if (pcUrl.isNotEmpty()) {
            try {
                ApiClient.setBaseUrl(pcUrl)
            } catch (_: Exception) {
                // Saved URL is malformed — reset so user is sent back to Pair screen
                pcUrl = ""
                prefs.edit().remove("pc_url").apply()
            }
        }
    }

    // ── Connection ────────────────────────────────────────────────────────────

    fun savePcUrl(url: String) {
        val normalized = url.trimEnd('/')
        pcUrl = normalized
        prefs.edit().putString("pc_url", normalized).apply()
        ApiClient.setBaseUrl(normalized)
    }

    suspend fun testConnection(): ServerInfo = ApiClient.service.getInfo()

    // ── Channels ──────────────────────────────────────────────────────────────

    fun loadFavorites() {
        viewModelScope.launch {
            runCatching { favorites = ApiClient.service.getFavorites() }
        }
    }

    fun searchChannels(query: String) {
        viewModelScope.launch {
            runCatching { searchResults = ApiClient.service.searchChannels(query) }
        }
    }

    fun addFavorite(channel: Channel) {
        viewModelScope.launch {
            runCatching {
                ApiClient.service.addFavorite(FavoriteRequest(channel.name, channel.id))
                loadFavorites()
            }
        }
    }

    // ── EPG ───────────────────────────────────────────────────────────────────

    fun loadEpgForChannel(channelId: String) {
        viewModelScope.launch {
            val gen = ++epgRequestGeneration
            // Window 0,0 = no server-side filter (matches shipped `android-tv-apk`); UI still clips to timeline.
            runCatching {
                var listings: List<EpgListing> = emptyList()
                for (attempt in 0 until 4) {
                    listings = ApiClient.service.getEpg(
                        channelId = channelId,
                        limit = 48,
                        windowStartMs = 0L,
                        windowEndMs = 0L,
                    ).listings
                    if (listings.isNotEmpty() || attempt == 3) break
                    delay(1500)
                }
                if (gen == epgRequestGeneration) {
                    epgListings = listings
                }
            }.onFailure {
                if (gen == epgRequestGeneration) {
                    epgListings = emptyList()
                }
            }
        }
    }

    suspend fun scheduleRecording(
        channelId: String,
        channelName: String,
        startTime: String,
        durationMins: Int,
    ) = ApiClient.service.schedule(ScheduleRequest(channelName, channelId, startTime, durationMins))

    // ── EPG category guide ────────────────────────────────────────────────────

    fun loadCategories() {
        viewModelScope.launch {
            runCatching { categories = ApiClient.service.getCategories() }
        }
    }

    fun loadChannelsByCategory(categoryId: String) {
        categoryChannels = emptyList()
        guideEpg = emptyMap()
        viewModelScope.launch {
            runCatching { categoryChannels = ApiClient.service.getChannelsByCategory(categoryId) }
        }
    }

    /**
     * Loads EPG for one chunk of channels. Window 0,0 skips server-side filtering so listings
     * are not dropped when timestamps are odd; [EpgGuideScreen] still filters to the visible window.
     */
    suspend fun loadGuideEpgChunk(channelIds: List<String>) {
        if (channelIds.isEmpty()) return
        val result = ApiClient.service.getMultiEpg(
            channelIds = channelIds.joinToString(","),
            limit = GUIDE_EPG_LISTING_LIMIT,
            windowStartMs = 0L,
            windowEndMs = 0L,
        )
        val patch = result.associate { it.channelId to it.listings }
        guideEpg = guideEpg + patch
    }

    /** Sequentially load guide rows in small batches to avoid huge single responses. */
    suspend fun loadGuideEpgBatched(channelIds: List<String>) {
        if (channelIds.isEmpty()) return
        var anyData = false
        channelIds.chunked(GUIDE_EPG_CHUNK).forEach { chunk ->
            loadGuideEpgChunk(chunk)
            if (!anyData) {
                anyData = chunk.any { id -> !guideEpg[id].isNullOrEmpty() }
            }
        }
        if (!anyData) {
            delay(2000)
            channelIds.chunked(GUIDE_EPG_CHUNK).forEach { chunk ->
                loadGuideEpgChunk(chunk)
            }
        }
    }

    // ── DVR ───────────────────────────────────────────────────────────────────

    suspend fun startDvr(channelId: String, channelName: String) {
        ApiClient.service.startDvr(DvrStartRequest(channelId, channelName))
    }

    fun stopDvrAsync() {
        viewModelScope.launch { runCatching { ApiClient.service.stopDvr() } }
    }

    suspend fun getDvrSegments(): List<DvrSegment> = ApiClient.service.getDvrSegments()

    // ── Completed recordings ──────────────────────────────────────────────────

    fun loadCompletedRecordings() {
        viewModelScope.launch {
            isLoading = true
            runCatching { completedRecordings = ApiClient.service.getCompletedRecordings() }
                .onFailure { errorMessage = it.message }
            isLoading = false
        }
    }

    fun clearError() { errorMessage = null }
}

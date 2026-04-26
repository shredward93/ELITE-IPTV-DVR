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
import com.elite.iptv.dvr.ui.guide.GuideConstants
import kotlinx.coroutines.launch

class MainViewModel(application: Application) : AndroidViewModel(application) {

    companion object {
        private const val GUIDE_EPG_CHUNK = 8
        private const val GUIDE_EPG_LISTING_LIMIT = 12
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
            val (ws, we) = GuideConstants.windowBounds()
            runCatching {
                val listings = ApiClient.service.getEpg(
                    channelId = channelId,
                    limit = 48,
                    windowStartMs = ws,
                    windowEndMs = we,
                ).listings
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
     * Loads EPG for one chunk of channels (same time window as [GuideConstants]).
     * Merge into [guideEpg] so the UI can fill in progressively.
     */
    suspend fun loadGuideEpgChunk(channelIds: List<String>) {
        if (channelIds.isEmpty()) return
        val (ws, we) = GuideConstants.windowBounds()
        val result = ApiClient.service.getMultiEpg(
            channelIds = channelIds.joinToString(","),
            limit = GUIDE_EPG_LISTING_LIMIT,
            windowStartMs = ws,
            windowEndMs = we,
        )
        val patch = result.associate { it.channelId to it.listings }
        guideEpg = guideEpg + patch
    }

    /** Sequentially load guide rows in small batches to avoid huge single responses. */
    suspend fun loadGuideEpgBatched(channelIds: List<String>) {
        if (channelIds.isEmpty()) return
        channelIds.chunked(GUIDE_EPG_CHUNK).forEach { chunk ->
            loadGuideEpgChunk(chunk)
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

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
import kotlinx.coroutines.launch

class MainViewModel(application: Application) : AndroidViewModel(application) {

    private val prefs = application.getSharedPreferences("elite_dvr", Context.MODE_PRIVATE)

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

    fun loadEpg(channelId: String) {
        viewModelScope.launch {
            runCatching { epgListings = ApiClient.service.getEpg(channelId).listings }
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

    fun loadGuideEpg(channelIds: List<String>, limit: Int = 6) {
        viewModelScope.launch {
            runCatching {
                val result = ApiClient.service.getMultiEpg(channelIds.joinToString(","), limit)
                guideEpg = result.associate { it.channelId to it.listings }
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

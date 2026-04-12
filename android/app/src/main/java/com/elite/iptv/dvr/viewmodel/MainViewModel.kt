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
import com.elite.iptv.dvr.api.GuideBundle
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

    var allChannels by mutableStateOf<List<Channel>>(emptyList())
        private set

    var guideBundleSource by mutableStateOf<String?>(null)
        private set

    var guideBundleLoading by mutableStateOf(false)
        private set

    var lastGuideCategoryId by mutableStateOf<String?>(null)
        private set

    var lastGuideRefreshAfterMs by mutableStateOf<Long>(0L)
        private set

    var guideEpg by mutableStateOf<Map<String, List<EpgListing>>>(emptyMap())
        private set

    var lastGuideChannelIds by mutableStateOf<List<String>>(emptyList())
        private set

    var lastGuideLimit by mutableStateOf(0)
        private set

    var guideEpgLoadedChannelIds by mutableStateOf<Set<String>>(emptySet())
        private set

    var guideEpgLoadingChannelIds by mutableStateOf<Set<String>>(emptySet())
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
        viewModelScope.launch {
            runCatching { categoryChannels = ApiClient.service.getChannelsByCategory(categoryId) }
        }
    }

    fun loadAllChannels() {
        viewModelScope.launch {
            runCatching { allChannels = ApiClient.service.getAllChannels() }
        }
    }

    fun loadGuideBundle(categoryId: String? = null, limit: Int = 24, refresh: Boolean = false) {
        val normalizedCategoryId = categoryId?.trim().orEmpty()
        val resolvedId = normalizedCategoryId.ifBlank { lastGuideCategoryId ?: "" }
        if (!refresh && guideBundleLoading) return
        if (!refresh && resolvedId == (lastGuideCategoryId ?: "") && categoryChannels.isNotEmpty() && lastGuideLimit >= limit) return

        guideBundleLoading = true
        viewModelScope.launch {
            runCatching {
                val bundle: GuideBundle = ApiClient.service.getGuide(
                    categoryId = normalizedCategoryId.ifBlank { null },
                    limit = limit,
                    refresh = refresh,
                )
                categories = bundle.categories
                categoryChannels = bundle.channels
                guideBundleSource = bundle.source
                lastGuideCategoryId = bundle.categoryId
                lastGuideRefreshAfterMs = bundle.refreshAfterMs
                lastGuideLimit = limit
                lastGuideChannelIds = bundle.channels.map { it.id }
                guideEpg = guideEpg + bundle.guideEpg
                guideEpgLoadedChannelIds = guideEpgLoadedChannelIds + bundle.guideEpg.keys
            }.onFailure { e ->
                println("[ANDROID] Guide bundle request failed: ${e.message}")
            }
            guideBundleLoading = false
        }
    }

    fun loadGuideEpg(channelIds: List<String>, limit: Int = 6) {
        val normalizedIds = channelIds.distinct().take(30)
        if (normalizedIds.isEmpty()) return
        if (guideEpg.isNotEmpty() && lastGuideChannelIds == normalizedIds && lastGuideLimit >= limit) return

        println("[ANDROID] Requesting EPG for ${normalizedIds.size} channels: ${normalizedIds.take(5)}")
        
        lastGuideChannelIds = normalizedIds
        lastGuideLimit = limit
        guideEpgLoadingChannelIds = guideEpgLoadingChannelIds + normalizedIds
        viewModelScope.launch {
            runCatching {
                val result = ApiClient.service.getMultiEpg(normalizedIds.joinToString(","), limit)
                val totalListings = result.sumOf { it.listings.size }
                println("[ANDROID] Received EPG: $totalListings listings for ${result.size} channels")
                guideEpg = guideEpg + result.associate { it.channelId to it.listings }
                guideEpgLoadedChannelIds = guideEpgLoadedChannelIds + normalizedIds
            }.onFailure { e ->
                println("[ANDROID] EPG request failed: ${e.message}")
            }
            guideEpgLoadingChannelIds = guideEpgLoadingChannelIds - normalizedIds.toSet()
        }
    }

    fun ensureGuideEpg(channelId: String, limit: Int = 12) {
        if (channelId.isBlank()) return
        if (guideEpg[channelId].orEmpty().isNotEmpty()) return
        if (channelId in guideEpgLoadingChannelIds) return

        guideEpgLoadingChannelIds = guideEpgLoadingChannelIds + channelId
        viewModelScope.launch {
            runCatching {
                val result = ApiClient.service.getEpg(channelId)
                guideEpg = guideEpg + (channelId to result.listings.take(limit))
                guideEpgLoadedChannelIds = guideEpgLoadedChannelIds + channelId
            }
            guideEpgLoadingChannelIds = guideEpgLoadingChannelIds - channelId
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

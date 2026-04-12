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

    enum class GuideLoadState {
        Idle,
        Loading,
        Prefetching,
        Refreshing,
        Ready,
        Error,
    }

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

    var guideLoadState by mutableStateOf(GuideLoadState.Idle)
        private set

    var guideLoadError by mutableStateOf<String?>(null)
        private set

    var lastGuideCategoryId by mutableStateOf<String?>(null)
        private set

    var lastGuideRefreshAfterMs by mutableStateOf<Long>(0L)
        private set

    var guideEpg by mutableStateOf<Map<String, List<EpgListing>>>(emptyMap())
        private set

    // Tivimate-style: pre-fetched guide data for ALL categories
    var allCategories by mutableStateOf<List<Category>>(emptyList())
        private set

    // Map categoryId -> channels for that category (all pre-loaded)
    var channelsByCategory by mutableStateOf<Map<String, List<Channel>>>(emptyMap())
        private set

    // True when background prefetch is running
    var guidePrefetching by mutableStateOf(false)
        private set

    // Progress: how many categories loaded out of total
    var guidePrefetchProgress by mutableStateOf(0 to 0)
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

    fun guideCategories(): List<Category> = allCategories.ifEmpty { categories }

    fun guideChannelsFor(categoryId: String?): List<Channel> {
        val resolvedId = categoryId?.trim().orEmpty()
        if (resolvedId.isNotBlank()) {
            val cached = channelsByCategory[resolvedId]
            if (!cached.isNullOrEmpty()) return cached
            if (resolvedId == (lastGuideCategoryId ?: "")) return categoryChannels
        }
        return categoryChannels
    }

    fun loadGuideBundle(categoryId: String? = null, limit: Int = 24, refresh: Boolean = false) {
        val normalizedCategoryId = categoryId?.trim().orEmpty()
        val resolvedId = normalizedCategoryId.ifBlank { lastGuideCategoryId ?: "" }
        if (!refresh && guideBundleLoading) return
        if (!refresh && resolvedId == (lastGuideCategoryId ?: "") && guideChannelsFor(resolvedId).isNotEmpty() && lastGuideLimit >= limit) return

        guideBundleLoading = true
        guideLoadError = null
        guideLoadState = if (guideBundleSource == null && allCategories.isEmpty()) {
            GuideLoadState.Loading
        } else {
            GuideLoadState.Refreshing
        }
        viewModelScope.launch {
            runCatching {
                val bundle: GuideBundle = ApiClient.service.getGuide(
                    categoryId = normalizedCategoryId.ifBlank { null },
                    limit = limit,
                    refresh = refresh,
                )
                categories = bundle.categories
                allCategories = bundle.categories
                categoryChannels = bundle.channels
                val bundleChannelsByCategory = bundle.channelsByCategory.orEmpty()
                channelsByCategory = if (bundleChannelsByCategory.isNotEmpty()) {
                    channelsByCategory + bundleChannelsByCategory
                } else {
                    channelsByCategory + (bundle.categoryId to bundle.channels)
                }
                guideBundleSource = bundle.source
                lastGuideCategoryId = bundle.categoryId
                lastGuideRefreshAfterMs = bundle.refreshAfterMs
                lastGuideLimit = limit
                lastGuideChannelIds = bundle.channels.map { it.id }
                guideEpg = guideEpg + bundle.guideEpg
                guideEpgLoadedChannelIds = guideEpgLoadedChannelIds + bundle.guideEpg.keys
                guideLoadState = GuideLoadState.Ready
            }.onFailure { e ->
                println("[ANDROID] Guide bundle request failed: ${e.message}")
                guideLoadError = e.message
                guideLoadState = GuideLoadState.Error
            }
            guideBundleLoading = false
        }
    }

    // Tivimate-style: prefetch ALL categories with channels and EPG in background
    fun prefetchAllGuideData(limit: Int = 24) {
        if (guidePrefetching) return
        if (allCategories.isNotEmpty() && channelsByCategory.isNotEmpty() && guideEpg.isNotEmpty()) return

        guidePrefetching = true
        guideLoadError = null
        guideLoadState = GuideLoadState.Prefetching
        viewModelScope.launch {
            runCatching {
                guidePrefetchProgress = 1 to 1
                println("[ANDROID] Prefetching full guide bundle...")

                val bundle: GuideBundle = ApiClient.service.getGuide(
                    categoryId = null,
                    limit = limit,
                    refresh = false,
                )

                allCategories = bundle.categories
                categories = bundle.categories
                channelsByCategory = bundle.channelsByCategory.orEmpty()
                categoryChannels = bundle.channels
                guideEpg = bundle.guideEpg
                guideEpgLoadedChannelIds = bundle.guideEpg.keys
                guideBundleSource = bundle.source
                lastGuideCategoryId = bundle.categoryId
                lastGuideRefreshAfterMs = bundle.refreshAfterMs
                lastGuideLimit = limit
                lastGuideChannelIds = bundle.channels.map { it.id }
                guidePrefetchProgress = 1 to 1
                guideLoadState = GuideLoadState.Ready
                println("[ANDROID] Prefetch complete: ${allCategories.size} categories, ${guideEpg.size} channels with EPG")
            }.onFailure { e ->
                println("[ANDROID] Guide prefetch failed: ${e.message}")
                guideLoadError = e.message
                guideLoadState = GuideLoadState.Error
            }
            guidePrefetching = false
        }
    }

    // For Tivimate-style: switch visible category without reloading
    fun switchGuideCategory(categoryId: String) {
        lastGuideCategoryId = categoryId
        categoryChannels = channelsByCategory[categoryId].orEmpty()
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

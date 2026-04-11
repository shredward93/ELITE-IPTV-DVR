package com.elite.iptv.dvr.api

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface ApiService {

    // ── Discovery ─────────────────────────────────────────────────────────────

    @GET("api/info")
    suspend fun getInfo(): ServerInfo

    // ── Channels ──────────────────────────────────────────────────────────────

    @GET("api/favorites")
    suspend fun getFavorites(): List<Channel>

    @GET("api/channels")
    suspend fun searchChannels(@Query("q") query: String): List<Channel>

    @GET("api/channels/all")
    suspend fun getAllChannels(): List<Channel>

    @POST("api/favorites/add")
    suspend fun addFavorite(@Body body: FavoriteRequest): OkResponse

    // ── EPG ───────────────────────────────────────────────────────────────────

    @GET("api/epg")
    suspend fun getEpg(@Query("channel_id") channelId: String): EpgResponse

    @GET("api/categories")
    suspend fun getCategories(): List<Category>

    @GET("api/channels/by-category")
    suspend fun getChannelsByCategory(@Query("category_id") categoryId: String): List<Channel>

    @GET("api/epg/multi")
    suspend fun getMultiEpg(
        @Query("channel_ids") channelIds: String,
        @Query("limit") limit: Int = 6,
    ): List<ChannelEpg>

    // ── Recordings ────────────────────────────────────────────────────────────

    @POST("api/schedule")
    suspend fun schedule(@Body body: ScheduleRequest): MessageResponse

    @GET("api/recordings")
    suspend fun getRecordings(): RecordingsResponse

    // ── DVR control ───────────────────────────────────────────────────────────

    @POST("dvr/start")
    suspend fun startDvr(@Body body: DvrStartRequest): OkResponse

    @POST("dvr/stop")
    suspend fun stopDvr(): OkResponse

    @GET("dvr/segments")
    suspend fun getDvrSegments(): List<DvrSegment>

    @GET("dvr/status")
    suspend fun getDvrStatus(): DvrStatus

    // ── Completed recording files ─────────────────────────────────────────────

    @GET("recordings")
    suspend fun getCompletedRecordings(): List<CompletedRecording>
}

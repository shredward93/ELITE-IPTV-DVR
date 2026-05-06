package com.elite.iptv.dvr.api

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.Response

interface ApiService {

    // ── Discovery ─────────────────────────────────────────────────────────────

    @GET("api/info")
    suspend fun getInfo(): ServerInfo

    @GET("api/settings")
    suspend fun getSettings(): RecordingSettings

    @POST("api/settings")
    suspend fun updateSettings(@Body body: RecordingSettings): RecordingSettings

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
    suspend fun getEpg(
        @Query("channel_id") channelId: String,
        @Query("limit") limit: Int = 32,
        @Query("window_start_ms") windowStartMs: Long = 0L,
        @Query("window_end_ms") windowEndMs: Long = 0L,
    ): EpgResponse

    @GET("api/categories")
    suspend fun getCategories(): List<Category>

    @GET("api/channels/by-category")
    suspend fun getChannelsByCategory(@Query("category_id") categoryId: String): List<Channel>

    @GET("api/epg/multi")
    suspend fun getMultiEpg(
        @Query("channel_ids") channelIds: String,
        @Query("limit") limit: Int = 12,
        @Query("window_start_ms") windowStartMs: Long = 0L,
        @Query("window_end_ms") windowEndMs: Long = 0L,
    ): List<ChannelEpg>

    @GET("api/guide")
    suspend fun getGuide(
        @Query("category_id") categoryId: String,
        @Query("limit") limit: Int = 24,
        @Query("refresh") refresh: Int = 0,
    ): GuideBundle

    // ── Recordings ────────────────────────────────────────────────────────────

    @POST("api/schedule")
    suspend fun schedule(@Body body: ScheduleRequest): MessageResponse

    @GET("api/recordings")
    suspend fun getRecordings(): RecordingsResponse

    // ── DVR control ───────────────────────────────────────────────────────────

    @POST("dvr/start")
    suspend fun startDvr(@Body body: DvrStartRequest): Response<Unit>

    @POST("dvr/stop")
    suspend fun stopDvr(): Response<Unit>

    @POST("api/preview/start")
    suspend fun startPreview(@Body body: PreviewStartRequest): PreviewStartResponse

    @POST("api/preview/stop")
    suspend fun stopPreview(@Body body: PreviewStopRequest): OkResponse

    @GET("dvr/segments")
    suspend fun getDvrSegments(): List<DvrSegment>

    @GET("dvr/status")
    suspend fun getDvrStatus(): DvrStatus
}

package com.elite.iptv.dvr.api

import com.google.gson.annotations.SerializedName

data class ServerInfo(
    val version: String,
    @SerializedName("server_reachable") val serverReachable: Boolean,
    @SerializedName("channel_count") val channelCount: Int,
    val capabilities: List<String>,
)

data class Channel(
    val name: String,
    val id: String,
)

data class EpgListing(
    val title: String,
    val description: String?,
    val start: String?,
    // XtreamCodes returns "end" in get_short_epg; some providers use "stop"
    @SerializedName(value = "stop", alternate = ["end"]) val stop: String?,
)

data class EpgResponse(
    val listings: List<EpgListing>,
)

data class ScheduleRequest(
    @SerializedName("channel_name") val channelName: String,
    @SerializedName("channel_id")   val channelId: String,
    @SerializedName("start_time")   val startTime: String,
    @SerializedName("duration_mins") val durationMins: Int,
)

data class FavoriteRequest(
    val name: String,
    val id: String,
)

data class MessageResponse(val message: String)

data class OkResponse(
    val ok: Boolean,
    val channel: String? = null,
)

data class DvrStartRequest(
    @SerializedName("channel_id")   val channelId: String,
    @SerializedName("channel_name") val channelName: String,
)

data class DvrSegment(
    val name: String,
    @SerializedName("size_bytes") val sizeBytes: Long,
    @SerializedName("is_active")  val isActive: Boolean,
)

data class DvrStatus(
    val active: Boolean,
    val channel: String?,
    val status: String,
    val error: String?,
    @SerializedName("buffer_age_secs")         val bufferAgeSecs: Int,
    @SerializedName("total_size_bytes")        val totalSizeBytes: Long,
    @SerializedName("storage_remaining_bytes") val storageRemainingBytes: Long,
    @SerializedName("segment_count")           val segmentCount: Int,
)

data class ActiveRecording(
    val index: Int,
    @SerializedName("channel_name")  val channelName: String,
    val status: String,
    @SerializedName("elapsed_secs")  val elapsedSecs: Int? = null,
    @SerializedName("remaining_secs") val remainingSecs: Int? = null,
    @SerializedName("output_file")   val outputFile: String? = null,
)

data class RecentRecording(
    @SerializedName("channel_name") val channelName: String,
    val status: String,
    @SerializedName("status_text")  val statusText: String,
)

data class RecordingsResponse(
    val active: List<ActiveRecording>,
    val recent: List<RecentRecording>,
)

data class CompletedRecording(
    val filename: String,
    @SerializedName("size_bytes")  val sizeBytes: Long,
    @SerializedName("recorded_at") val recordedAt: String,
)

data class Category(
    @SerializedName("category_id")   val categoryId: String,
    @SerializedName("category_name") val categoryName: String,
)

data class ChannelEpg(
    @SerializedName("channel_id") val channelId: String,
    val listings: List<EpgListing>,
)

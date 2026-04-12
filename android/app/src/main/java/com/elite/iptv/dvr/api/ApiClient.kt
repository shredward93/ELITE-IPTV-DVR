package com.elite.iptv.dvr.api

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {

    private var _service: ApiService? = null

    val service: ApiService
        get() = _service ?: error("ApiClient not initialized — call setBaseUrl() first")

    val isConfigured: Boolean
        get() = _service != null

    fun setBaseUrl(baseUrl: String) {
        val normalized = baseUrl.trimEnd('/') + "/"
        val http = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)  // longer for stream proxy
            .addInterceptor(
                HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.NONE }
            )
            .build()

        _service = Retrofit.Builder()
            .baseUrl(normalized)
            .client(http)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ApiService::class.java)
    }

    /** Full URL for the direct live MPEG-TS proxy used by the lighter live player path. */
    fun liveStreamUrl(baseUrl: String, channelId: String): String =
        "${baseUrl.trimEnd('/')}/api/stream/live?channel_id=$channelId"

    /** Full URL for a completed recording file. */
    fun recordingUrl(baseUrl: String, filename: String): String =
        "${baseUrl.trimEnd('/')}/recordings/$filename"
}

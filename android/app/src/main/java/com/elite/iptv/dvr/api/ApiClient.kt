package com.elite.iptv.dvr.api

import com.google.gson.GsonBuilder
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

        val gson = GsonBuilder()
            .registerTypeAdapter(EpgListing::class.java, EpgListingDeserializer)
            .create()
        _service = Retrofit.Builder()
            .baseUrl(normalized)
            .client(http)
            .addConverterFactory(GsonConverterFactory.create(gson))
            .build()
            .create(ApiService::class.java)
    }

    /** Same live DVR playlist URL the webapp uses (`static/remote.html` → `/dvr/playlist.m3u8`). */
    fun dvrPlaylistUrl(baseUrl: String): String =
        "${baseUrl.trimEnd('/')}/dvr/playlist.m3u8"

    /** Completed file URL — same path model as the webapp’s recording playback. */
    fun recordingUrl(baseUrl: String, filename: String): String =
        "${baseUrl.trimEnd('/')}/recordings/$filename"
}

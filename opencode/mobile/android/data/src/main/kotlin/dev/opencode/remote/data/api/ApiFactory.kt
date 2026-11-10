package dev.opencode.remote.data.api

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import dev.opencode.remote.domain.AppSettings
import dev.opencode.remote.domain.ServerProfile
import java.util.concurrent.TimeUnit
import kotlinx.serialization.json.Json
import okhttp3.Credentials
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit

/** Shared kotlinx.serialization config (doc 14 §1 — copy grapeot rules verbatim). */
val OpenCodeJson = Json {
    ignoreUnknownKeys = true
    isLenient = true
    coerceInputValues = true
    explicitNulls = false
    encodeDefaults = true
}

private const val JSON_MIME = "application/json"

/** Builds the S3-hardened client: Basic auth, timeouts from settings, `?directory=` routing. */
object ApiFactory {
    fun retrofit(profile: ServerProfile, password: String?, settings: AppSettings): Retrofit {
        val base = profile.baseUrl.trimEnd('/') + "/"
        val client = OkHttpClient.Builder()
            .connectTimeout(settings.connectTimeoutMs, TimeUnit.MILLISECONDS)
            .readTimeout(settings.readTimeoutMs, TimeUnit.MILLISECONDS)
            .writeTimeout(settings.readTimeoutMs, TimeUnit.MILLISECONDS)
            .addInterceptor(AuthInterceptor(profile.username, password))
            .addInterceptor(DirectoryInterceptor(profile.defaultDirectory))
            .apply {
                if (BuildConfigField.DEBUG_LOGGING) {
                    addInterceptor(HttpLoggingInterceptor().setLevel(HttpLoggingInterceptor.Level.BASIC))
                }
            }
            .authenticator { _, response ->
                if (response.request.header("Authorization") != null || password.isNullOrEmpty()) return@authenticator null
                response.request.newBuilder()
                    .header("Authorization", Credentials.basic(profile.username, password))
                    .build()
            }
            .build()
        return Retrofit.Builder()
            .baseUrl(base)
            .client(client)
            .addConverterFactory(StringConverterFactory)
            .addConverterFactory(OpenCodeJson.asConverterFactory(JSON_MIME.toMediaType()))
            .build()
    }

    fun api(profile: ServerProfile, password: String?, settings: AppSettings): OpenCodeApi =
        retrofit(profile, password, settings).create(OpenCodeApi::class.java)

    /** Active-profile-bound API (S3 single place: auth + directory + timeouts). */
    data class BoundApi(
        val profile: ServerProfile,
        val password: String?,
        val settings: AppSettings,
        val api: OpenCodeApi,
    )

    fun bound(profile: ServerProfile, password: String?, settings: AppSettings): BoundApi =
        BoundApi(profile, password, settings, api(profile, password, settings))
}

/** Preemptive Basic auth (grapeot pattern: nullable creds, works without password for local dev). */
private class AuthInterceptor(val user: String, val password: String?) : Interceptor {
    override fun intercept(chain: Interceptor.Chain) =
        chain.proceed(
            if (password.isNullOrEmpty()) chain.request()
            else chain.request().newBuilder()
                .header("Authorization", Credentials.basic(user, password))
                .build(),
        )
}

/** Appends `?directory=` when the profile pins one (doc 07: never target the wrong cwd). */
private class DirectoryInterceptor(val directory: String?) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): okhttp3.Response {
        val req = chain.request()
        if (directory.isNullOrBlank() || req.url.queryParameter("directory") != null) {
            return chain.proceed(req)
        }
        val url = req.url.newBuilder().addQueryParameter("directory", directory).build()
        return chain.proceed(req.newBuilder().url(url).build())
    }
}

/** Build-time debug flag without depending on :app BuildConfig. */
internal object BuildConfigField {
    const val DEBUG_LOGGING = true
}

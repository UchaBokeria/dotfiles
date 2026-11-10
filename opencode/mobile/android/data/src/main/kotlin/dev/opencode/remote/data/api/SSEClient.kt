package dev.opencode.remote.data.api

import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.retryWhen
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.sse.EventSource
import okhttp3.sse.EventSources
import android.util.Log

/**
 * SSE client (doc 14 §1 recipe — grapeot SSEClient, adapted).
 * GET {base}/global/event, Basic auth, infinite 1s→30s backoff, blank/[DONE] skip.
 * Emits raw (type, data) pairs; parsing lives in SseEvents.
 */
class SSEClient(private val http: OkHttpClient) {

    fun connect(baseUrl: String, username: String, password: String?): Flow<Pair<String?, String>> =
        callbackFlow {
            val req = Request.Builder()
                .url(baseUrl.trimEnd('/') + "/global/event")
                .header("Accept", "text/event-stream")
                .header("Cache-Control", "no-cache")
                .apply {
                    if (!password.isNullOrEmpty()) {
                        header("Authorization", okhttp3.Credentials.basic(username, password))
                    }
                }
                .build()
            val factory = EventSources.createFactory(http)
            var source: EventSource? = null
            val listener = object : okhttp3.sse.EventSourceListener() {
                override fun onOpen(eventSource: EventSource, response: okhttp3.Response) {
                    Log.d("OC-SSE", "open ${response.code}")
                    trySend("open" to "")
                }

                override fun onEvent(eventSource: EventSource, id: String?, type: String?, data: String) {
                    if (data.isBlank() || data == "[DONE]") return
                    Log.d("OC-SSE", "event type=$type data=${data.take(160)}")
                    trySend((type ?: "message") to data)
                }

                override fun onClosed(eventSource: EventSource) {
                    Log.d("OC-SSE", "closed")
                    close(Exception("sse closed"))
                }

                override fun onFailure(eventSource: EventSource, t: Throwable?, response: okhttp3.Response?) {
                    Log.d("OC-SSE", "failure ${t?.message} code=${response?.code}")
                    close(t ?: Exception("sse failure ${response?.code}"))
                }
            }
            source = factory.newEventSource(req, listener)
            awaitClose { source?.cancel() }
        }.retryWhen { _, attempt ->
            val backoff = (1_000L shl attempt.toInt().coerceAtMost(5)).coerceAtMost(30_000L)
            delay(backoff + (0..500L).random())
            true
        }
}

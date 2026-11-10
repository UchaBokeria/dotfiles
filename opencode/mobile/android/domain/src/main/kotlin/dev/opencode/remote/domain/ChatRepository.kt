package dev.opencode.remote.domain

import kotlinx.coroutines.flow.Flow

/** Outgoing message part (H1; file parts H2/P3 reuse File with data: URLs — doc 07 gap #1 resolved). */
data class OutPart(
    val type: String = "text",
    val text: String? = null,
    val mime: String? = null,
    val filename: String? = null,
    val url: String? = null,
)

/** Sessions + thread (C1–C3 subset, H1). Implemented in :data, consumed by :feature-chat. */
interface ChatRepository {
    val sessions: Flow<List<ChatSession>>
    val statusMap: Flow<Map<String, SessionStatus>>
    val tempSessionIds: Flow<Set<String>>
    val showTemp: Flow<Boolean>
    suspend fun refreshSessions(): Result<Unit>
    suspend fun createSession(title: String?, temp: Boolean): Result<ChatSession>
    suspend fun renameSession(id: String, title: String): Result<Unit>
    suspend fun deleteSession(id: String): Result<Unit>
    suspend fun abortSession(id: String): Result<Unit>
    suspend fun purgeTempSessions(): Result<Int>
    suspend fun setShowTemp(show: Boolean)
    suspend fun messages(sessionId: String, limit: Int = 50): Result<List<ChatMessage>>
    suspend fun send(
        sessionId: String,
        parts: List<OutPart>,
        agent: String,
        noReply: Boolean = false,
        modelProviderID: String? = null,
        modelID: String? = null,
        variant: String? = null,
        tools: Map<String, Boolean>? = null,
        system: String? = null,
    ): Result<Unit>

    suspend fun executeCommand(
        sessionId: String,
        command: String,
        arguments: String,
        agent: String,
    ): Result<Unit>

    /** Live SSE event flow for the active profile (shared, reference-counted in :data). */
    val events: Flow<SseEvent>
}

/** Minimal SSE event envelope (doc 14 SSE recipe). */
data class SseEvent(
    val type: String,
    val sessionID: String? = null,
    val messageID: String? = null,
    val partID: String? = null,
    val delta: String? = null,
    /** Human-readable error for session.error (from properties.error.message/name). */
    val errorMessage: String? = null,
    /** Approval/question request id for replied/rejected events. */
    val requestID: String? = null,
    val raw: String = "",
)

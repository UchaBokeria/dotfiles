package dev.opencode.remote.domain

import kotlinx.serialization.Serializable

/** A chat session (C1–C3). Server fields subset; unknown fields ignored. */
@Serializable
data class ChatSession(
    val id: String,
    val title: String = "",
    val directory: String = "",
    val projectID: String = "",
    val parentID: String? = null,
    val updatedAt: Long = 0,
)

enum class SessionBusy { IDLE, BUSY, RETRY }

@Serializable
data class SessionStatus(
    val type: String = "idle",
    val attempt: Int = 0,
    val message: String? = null,
) {
    fun toBusy(): SessionBusy = when (type) {
        "busy" -> SessionBusy.BUSY
        "retry" -> SessionBusy.RETRY
        else -> SessionBusy.IDLE
    }
}

/** Message role. */
enum class Role { USER, ASSISTANT, UNKNOWN }

/** Renderable part (doc 07 part model; unknown → Unknown, never crash). */
sealed interface ChatPart {
    data class Text(val text: String) : ChatPart
    data class Reasoning(val text: String) : ChatPart
    data class Tool(val callID: String, val tool: String, val state: String) : ChatPart
    data class StepStart(val id: String) : ChatPart
    data class StepFinish(val cost: Double = 0.0, val input: Long = 0, val output: Long = 0) : ChatPart
    data class File(val mime: String, val filename: String, val url: String = "") : ChatPart
    data class Patch(val files: Int = 0) : ChatPart
    data class Agent(val name: String) : ChatPart
    data class Retry(val attempt: Int, val error: String = "") : ChatPart
    data class Compaction(val text: String = "") : ChatPart
    data class Subtask(val prompt: String = "") : ChatPart
    data class Unknown(val type: String) : ChatPart
}

data class ChatMessage(
    val id: String,
    val role: Role,
    val parts: List<ChatPart>,
    val error: String? = null,
    val optimistic: Boolean = false,
)

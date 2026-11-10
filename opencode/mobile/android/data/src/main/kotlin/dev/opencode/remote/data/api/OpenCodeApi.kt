package dev.opencode.remote.data.api

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path

/**
 * opencode `serve` v1 HTTP contract (doc 07, frozen spec assets/serve-spec-1.0.0-dev.json,
 * teardown doc 14 §1). P0 ships health + profiles; chat/session calls land in P1.
 */
interface OpenCodeApi {
    @GET("global/health")
    suspend fun health(): HealthResponse

    // --- P1 surface (declared now so MockWebServer tests pin the paths) ---
    @GET("session")
    suspend fun sessions(): List<SessionDto>

    @POST("session")
    suspend fun createSession(@Body body: CreateSessionRequest): SessionDto

    @GET("session/{id}")
    suspend fun session(@Path("id") id: String): SessionDto

    @PATCH("session/{id}")
    suspend fun renameSession(@Path("id") id: String, @Body body: UpdateTitleRequest): SessionDto

    @DELETE("session/{id}")
    suspend fun deleteSession(@Path("id") id: String): Response<Unit>

    @GET("session/status")
    suspend fun sessionStatus(): Map<String, SessionStatusDto>

    @POST("session/{id}/prompt_async")
    suspend fun promptAsync(@Path("id") id: String, @Body body: PromptRequest): Response<Unit>

    @GET("permission")
    suspend fun pendingPermissions(): List<PermissionDto>

    @POST("permission/{requestId}/reply")
    suspend fun replyPermission(
        @Path("requestId") requestId: String,
        @Body body: PermissionReply,
    ): Response<Unit>

    // --- P2: approvals / catalog (raw strings, DtoMap parses leniently) ---
    @GET("permission")
    suspend fun rawPermissions(): String

    @GET("question")
    suspend fun rawQuestions(): String

    @POST("question/{requestId}/reply")
    suspend fun replyQuestion(
        @Path("requestId") requestId: String,
        @Body body: QuestionReply,
    ): Response<Unit>

    @POST("question/{requestId}/reject")
    suspend fun rejectQuestion(@Path("requestId") requestId: String): Response<Unit>

    @GET("provider")
    suspend fun rawProviders(): String

    @GET("config/providers")
    suspend fun rawConfigProviders(): String

    @GET("agent")
    suspend fun rawAgents(): String

    @GET("command")
    suspend fun rawCommands(): String

    @GET("mcp")
    suspend fun rawMcp(): String

    @GET("experimental/tool/ids")
    suspend fun rawToolIds(): String

    @POST("session/{id}/command")
    suspend fun rawCommand(
        @Path("id") id: String,
        @Body body: CommandExecute,
    ): String

    // --- raw string variants (lenient DtoMap parsing, doc 07 drift-proofing) ---
    @GET("session")
    suspend fun rawSessions(): String

    @GET("session/status")
    suspend fun rawStatus(): String

    @POST("session")
    suspend fun rawCreate(@Body body: CreateSessionRequest): kotlinx.serialization.json.JsonObject

    @GET("session/{id}/message")
    suspend fun rawMessages(
        @Path("id") id: String,
        @retrofit2.http.Query("limit") limit: Int = 50,
    ): String

    @POST("session/{id}/prompt_async")
    suspend fun rawPromptAsync(@Path("id") id: String, @Body body: PromptRequest): Response<Unit>

    @PATCH("session/{id}")
    suspend fun rawRename(@Path("id") id: String, @Body body: UpdateTitleRequest): String

    @DELETE("session/{id}")
    suspend fun rawDelete(@Path("id") id: String): Response<Unit>

    @POST("session/{id}/abort")
    suspend fun rawAbort(@Path("id") id: String): Response<Unit>
}

@Serializable
data class HealthResponse(val healthy: Boolean, val version: String)

@Serializable
data class SessionDto(
    val id: String,
    val title: String = "",
    val directory: String = "",
    val projectID: String = "",
)

@Serializable
data class CreateSessionRequest(val title: String? = null, val parentID: String? = null)

@Serializable
data class UpdateTitleRequest(val title: String)

@Serializable
data class SessionStatusDto(val type: String = "idle")

@Serializable
data class PromptRequest(
    val parts: List<PartInput>,
    val agent: String = "build",
    val model: ModelInput? = null,
    val variant: String? = null,
    val tools: Map<String, Boolean>? = null,
    val system: String? = null,
    val noReply: Boolean = false,
)

@Serializable
data class PartInput(
    val type: String = "text",
    val text: String? = null,
    val mime: String? = null,
    val filename: String? = null,
    val url: String? = null,
)

@Serializable
data class ModelInput(val providerID: String, val modelID: String)

@Serializable
data class PermissionDto(val id: String, val sessionID: String = "", val title: String = "")

@Serializable
data class PermissionReply(
    val reply: String,
    val message: String? = null,
)

@Serializable
data class QuestionReply(val answers: List<List<String>>)

@Serializable
data class CommandExecute(
    val command: String,
    val arguments: String = "",
    val agent: String? = null,
)

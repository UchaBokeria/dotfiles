package dev.opencode.remote.domain

import kotlinx.coroutines.flow.Flow

/** A pending permission request (spec PermissionRequest verbatim, lenient). */
data class PermissionItem(
    val id: String,
    val sessionID: String,
    val permission: String,
    val patterns: List<String> = emptyList(),
    val metadata: Map<String, String> = emptyMap(),
    val always: List<String> = emptyList(),
    val messageID: String? = null,
    val callID: String? = null,
    /** Terminal state after reply (grinev rule): null = awaiting. */
    val replied: String? = null,
)

enum class PermissionReplyKind(val wire: String) { ONCE("once"), ALWAYS("always"), REJECT("reject") }

interface PermissionRepository {
    val pending: Flow<List<PermissionItem>>
    suspend fun refresh(): Result<Unit>
    suspend fun reply(id: String, kind: PermissionReplyKind): Result<Unit>
    fun markRepliedExternally(requestID: String)
}

/** A pending AskUserQuestion request (one card; answers submitted in question order). */
data class QuestionOption(val label: String, val description: String = "")

data class QuestionPrompt(
    val header: String,
    val question: String,
    val options: List<QuestionOption>,
    val multiple: Boolean = false,
    val customAllowed: Boolean = false,
)

data class QuestionItem(
    val id: String,
    val sessionID: String,
    val questions: List<QuestionPrompt>,
)

interface QuestionRepository {
    val pending: Flow<List<QuestionItem>>
    suspend fun refresh(): Result<Unit>
    suspend fun reply(id: String, answers: List<List<String>>): Result<Unit>
    suspend fun reject(id: String): Result<Unit>
    fun markSettledExternally(requestID: String)
}

/** Provider/model/agent/command catalogs (server-driven pickers). */
data class ModelInfo(
    val id: String,
    val name: String,
    val contextLimit: Long = 0,
)

data class ProviderInfo(
    val id: String,
    val name: String,
    val models: List<ModelInfo>,
)

data class AgentInfo(
    val name: String,
    val description: String = "",
    val mode: String = "all",
)

data class CommandInfo(
    val name: String,
    val description: String = "",
    val source: String = "",
)

data class McpServerInfo(
    val name: String,
    val status: String,
)

interface CatalogRepository {
    val providers: Flow<List<ProviderInfo>>
    val agents: Flow<List<AgentInfo>>
    val commands: Flow<List<CommandInfo>>
    val mcpServers: Flow<List<McpServerInfo>>
    val toolIds: Flow<List<String>>
    suspend fun refresh(): Result<Unit>
}

/** Per-session model/agent/effort memory (grapeot pattern). */
data class SessionPrefs(
    val modelID: String? = null,
    val providerID: String? = null,
    val variant: String? = null,
    val agent: String? = null,
)

/** Client-side project (D1): memory + instructions mapped onto directories. */
@kotlinx.serialization.Serializable
data class Project(
    val id: String,
    val name: String,
    val directories: List<String> = emptyList(),
    val instructions: String = "",
    val memoryNote: String = "",
)

interface ProjectRepository {
    val projects: Flow<List<Project>>
    /** sessionId → projectId links. */
    val sessionLinks: Flow<Map<String, String>>
    suspend fun upsert(project: Project)
    suspend fun delete(id: String)
    suspend fun linkSession(sessionId: String, projectId: String?)
}

/** Persisted session→project link row (MapSerializer avoided: overload friction). */
@kotlinx.serialization.Serializable
data class SessionLink(val sessionId: String, val projectId: String)

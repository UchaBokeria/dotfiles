package dev.opencode.remote.data.repo

import dev.opencode.remote.data.api.DtoMap
import dev.opencode.remote.data.api.PermissionReply
import dev.opencode.remote.data.api.QuestionReply
import dev.opencode.remote.domain.AgentInfo
import dev.opencode.remote.domain.CatalogRepository
import dev.opencode.remote.domain.CommandInfo
import dev.opencode.remote.domain.McpServerInfo
import dev.opencode.remote.domain.PermissionItem
import dev.opencode.remote.domain.PermissionReplyKind
import dev.opencode.remote.domain.PermissionRepository
import dev.opencode.remote.domain.ProviderInfo
import dev.opencode.remote.domain.QuestionItem
import dev.opencode.remote.domain.QuestionRepository
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** Approvals (grinev rules: failed reply stays answerable; externally-settled items vanish on refresh). */
@Singleton
class PermissionRepositoryImpl @Inject constructor(
    private val active: ActiveApi,
) : PermissionRepository {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val _pending = MutableStateFlow<List<PermissionItem>>(emptyList())
    override val pending: Flow<List<PermissionItem>> = _pending.asStateFlow()

    init {
        scope.launch { refresh() }
    }

    override suspend fun refresh(): Result<Unit> = runCatching {
        val b = active.get() ?: return Result.success(Unit)
        val live = DtoMap.parsePermissions(b.api.rawPermissions())
        val liveIds = live.map { it.id }.toSet()
        val repliedById = _pending.value
            .filter { it.replied != null }
            .associate { it.id to it.replied }
        // Keep local terminal markers only while the request is still live server-side;
        // vanished = answered elsewhere → drop (grinev rule).
        _pending.value = live.map { item ->
            repliedById[item.id]?.let { item.copy(replied = it) } ?: item
        }
    }

    override suspend fun reply(id: String, kind: PermissionReplyKind): Result<Unit> = runCatching {
        val b = active.get() ?: error("no active server")
        val res = b.api.replyPermission(id, PermissionReply(reply = kind.wire))
        if (!res.isSuccessful) error("reply failed: HTTP ${res.code()}")
        _pending.value = _pending.value.map {
            if (it.id == id) it.copy(replied = kind.wire) else it
        }
    }

    override fun markRepliedExternally(requestID: String) {
        _pending.value = _pending.value.map {
            if (it.id == requestID) it.copy(replied = "external") else it
        }
    }
}

/** AskUserQuestion queue (single-select answers immediately; multi toggles + Done in UI). */
@Singleton
class QuestionRepositoryImpl @Inject constructor(
    private val active: ActiveApi,
) : QuestionRepository {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val _pending = MutableStateFlow<List<QuestionItem>>(emptyList())
    override val pending: Flow<List<QuestionItem>> = _pending.asStateFlow()

    init {
        scope.launch { refresh() }
    }

    override suspend fun refresh(): Result<Unit> = runCatching {
        val b = active.get() ?: return Result.success(Unit)
        val live = DtoMap.parseQuestions(b.api.rawQuestions())
        val liveIds = live.map { it.id }.toSet()
        // Drop items that vanished server-side (settled elsewhere).
        _pending.value = live.filter { it.id in liveIds }
    }

    override suspend fun reply(id: String, answers: List<List<String>>): Result<Unit> = runCatching {
        val b = active.get() ?: error("no active server")
        val res = b.api.replyQuestion(id, QuestionReply(answers))
        if (!res.isSuccessful) error("reply failed: HTTP ${res.code()}")
        _pending.value = _pending.value.filterNot { it.id == id }
    }

    override suspend fun reject(id: String): Result<Unit> = runCatching {
        val b = active.get() ?: error("no active server")
        val res = b.api.rejectQuestion(id)
        if (!res.isSuccessful) error("reject failed: HTTP ${res.code()}")
        _pending.value = _pending.value.filterNot { it.id == id }
    }

    override fun markSettledExternally(requestID: String) {
        _pending.value = _pending.value.filterNot { it.id == requestID }
    }
}

/** Server-driven pickers (providers/models, agents, commands, MCP, tool ids). */
@Singleton
class CatalogRepositoryImpl @Inject constructor(
    private val active: ActiveApi,
) : CatalogRepository {

    private val _providers = MutableStateFlow<List<ProviderInfo>>(emptyList())
    private val _agents = MutableStateFlow<List<AgentInfo>>(emptyList())
    private val _commands = MutableStateFlow<List<CommandInfo>>(emptyList())
    private val _mcp = MutableStateFlow<List<McpServerInfo>>(emptyList())
    private val _tools = MutableStateFlow<List<String>>(emptyList())

    override val providers: Flow<List<ProviderInfo>> = _providers.asStateFlow()
    override val agents: Flow<List<AgentInfo>> = _agents.asStateFlow()
    override val commands: Flow<List<CommandInfo>> = _commands.asStateFlow()
    override val mcpServers: Flow<List<McpServerInfo>> = _mcp.asStateFlow()
    override val toolIds: Flow<List<String>> = _tools.asStateFlow()

    override suspend fun refresh(): Result<Unit> = runCatching {
        val b = active.get() ?: return Result.success(Unit)
        _providers.value = DtoMap.parseProviders(b.api.rawProviders())
            .ifEmpty { DtoMap.parseProviders(b.api.rawConfigProviders()) }
        _agents.value = DtoMap.parseAgents(b.api.rawAgents())
        _commands.value = DtoMap.parseCommands(b.api.rawCommands())
        _mcp.value = DtoMap.parseMcp(b.api.rawMcp())
        _tools.value = DtoMap.parseToolIds(b.api.rawToolIds())
    }
}

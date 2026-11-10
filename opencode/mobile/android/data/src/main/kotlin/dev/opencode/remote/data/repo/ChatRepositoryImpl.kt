package dev.opencode.remote.data.repo

import dev.opencode.remote.data.api.ApiFactory
import dev.opencode.remote.data.api.DtoMap
import dev.opencode.remote.data.api.PartInput
import dev.opencode.remote.data.api.PromptRequest
import dev.opencode.remote.data.api.SSEClient
import dev.opencode.remote.domain.AppSettings
import dev.opencode.remote.domain.ChatMessage
import dev.opencode.remote.domain.ChatRepository
import dev.opencode.remote.domain.ChatSession
import dev.opencode.remote.domain.OutPart
import dev.opencode.remote.domain.ServerProfile
import dev.opencode.remote.domain.ServerRepository
import dev.opencode.remote.domain.SessionStatus
import dev.opencode.remote.domain.SseEvent
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit

/**
 * Chat data: sessions/thread over Retrofit + shared SSE (doc 14 grapeot recipe).
 * Temp sessions tracked client-side per profile (D2).
 */
@Singleton
class ChatRepositoryImpl @Inject constructor(
    private val servers: ServerRepository,
    private val permissions: dev.opencode.remote.domain.PermissionRepository,
    private val questions: dev.opencode.remote.domain.QuestionRepository,
    http: OkHttpClient,
) : ChatRepository {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val sse = SSEClient(http.newBuilder().readTimeout(0, TimeUnit.MILLISECONDS).build())

    private val _sessions = MutableStateFlow<List<ChatSession>>(emptyList())
    private val _status = MutableStateFlow<Map<String, SessionStatus>>(emptyMap())
    private val _events = MutableSharedFlow<SseEvent>(extraBufferCapacity = 256)

    override val sessions: Flow<List<ChatSession>> = _sessions.asStateFlow()
    override val statusMap: Flow<Map<String, SessionStatus>> = _status.asStateFlow()
    override val events: Flow<SseEvent> = _events.asSharedFlow()

    private val _temp = MutableStateFlow<Map<String, Set<String>>>(emptyMap())
    private val _showTemp = MutableStateFlow(true)

    private val activeId: Flow<String?> = servers.activeProfileId

    override val tempSessionIds: Flow<Set<String>> = combine(_temp, activeId) { m, id ->
        m[id] ?: emptySet()
    }
    override val showTemp: Flow<Boolean> = _showTemp.asStateFlow()

    init {
        // Shared SSE for the active profile; reconnects handled by SSEClient retryWhen.
        scope.launch {
            try {
                passwordHolder().distinctUntilChanged().collect { holder ->
                    android.util.Log.d("OC-SSE", "holder active=${holder?.profile?.baseUrl} hasPw=${holder?.password != null}")
                    if (holder == null) return@collect
                    launch {
                        sse.connect(holder.profile.baseUrl, holder.profile.username, holder.password)
                            .collect { (type, data) ->
                                DtoMap.event(type, data)?.let { ev ->
                                    android.util.Log.d("OC-SSE", "parsed ${ev.type} ses=${ev.sessionID}")
                                    _events.emit(ev)
                                    applyEvent(ev)
                                }
                            }
                    }
                }
            } catch (e: Exception) {
                android.util.Log.e("OC-SSE", "repo sse collector died: ${e.message}", e)
            }
        }
        // Keep sessions fresh when the active profile changes.
        scope.launch {
            passwordHolder().distinctUntilChanged().collect {
                _sessions.value = emptyList()
                _status.value = emptyMap()
                refreshSessions()
            }
        }
    }

    override suspend fun refreshSessions(): Result<Unit> = runCatching {
        val holder = activeHolder().first() ?: return Result.success(Unit)
        val api = ApiFactory.api(holder.profile, holder.password, holder.settings)
        _sessions.value = DtoMap.parseSessions(api.rawSessions())
        _status.value = DtoMap.parseStatusMap(api.rawStatus())
    }

    override suspend fun createSession(title: String?, temp: Boolean): Result<ChatSession> = runCatching {
        val holder = activeHolder().first() ?: error("no active server")
        val session = DtoMap.session(ApiFactory.api(holder.profile, holder.password, holder.settings).rawCreate(dev.opencode.remote.data.api.CreateSessionRequest(title = title)))
        _sessions.value = listOf(session) + _sessions.value
        if (temp) {
            val pid = holder.profile.id
            _temp.value = _temp.value + (pid to ((_temp.value[pid] ?: emptySet()) + session.id))
        }
        session
    }

    override suspend fun renameSession(id: String, title: String): Result<Unit> = runCatching {
        val holder = activeHolder().first() ?: error("no active server")
        ApiFactory.api(holder.profile, holder.password, holder.settings).rawRename(id, dev.opencode.remote.data.api.UpdateTitleRequest(title))
        _sessions.value = _sessions.value.map { if (it.id == id) it.copy(title = title) else it }
    }

    override suspend fun deleteSession(id: String): Result<Unit> = runCatching {
        val holder = activeHolder().first() ?: error("no active server")
        ApiFactory.api(holder.profile, holder.password, holder.settings).rawDelete(id)
        _sessions.value = _sessions.value.filterNot { it.id == id }
        _temp.value = _temp.value.mapValues { (_, set) -> set - id }
    }

    override suspend fun abortSession(id: String): Result<Unit> = runCatching {
        val holder = activeHolder().first() ?: error("no active server")
        ApiFactory.api(holder.profile, holder.password, holder.settings).rawAbort(id)
    }

    override suspend fun purgeTempSessions(): Result<Int> = runCatching {
        val holder = activeHolder().first() ?: error("no active server")
        val ids = _temp.value[holder.profile.id] ?: emptySet()
        var n = 0
        val api = ApiFactory.api(holder.profile, holder.password, holder.settings)
        for (id in ids) {
            runCatching { api.rawDelete(id); n++ }
        }
        _sessions.value = _sessions.value.filterNot { it.id in ids }
        _temp.value = _temp.value + (holder.profile.id to emptySet())
        n
    }

    override suspend fun setShowTemp(show: Boolean) {
        _showTemp.value = show
    }

    override suspend fun messages(sessionId: String, limit: Int): Result<List<ChatMessage>> = runCatching {
        val holder = activeHolder().first() ?: error("no active server")
        DtoMap.parseMessages(
            ApiFactory.api(holder.profile, holder.password, holder.settings).rawMessages(sessionId, limit),
        )
    }

    override suspend fun send(
        sessionId: String,
        parts: List<OutPart>,
        agent: String,
        noReply: Boolean,
        modelProviderID: String?,
        modelID: String?,
        variant: String?,
        tools: Map<String, Boolean>?,
        system: String?,
    ): Result<Unit> =
        runCatching {
            val holder = activeHolder().first() ?: error("no active server")
            ApiFactory.api(holder.profile, holder.password, holder.settings).rawPromptAsync(
                sessionId,
                PromptRequest(
                    parts = parts.map {
                        PartInput(type = it.type, text = it.text, mime = it.mime, filename = it.filename, url = it.url)
                    },
                    agent = agent,
                    model = if (modelProviderID != null && modelID != null) {
                        dev.opencode.remote.data.api.ModelInput(modelProviderID, modelID)
                    } else null,
                    variant = variant,
                    tools = tools,
                    noReply = noReply,
                    system = system,
                ),
            )
        }

    override suspend fun executeCommand(
        sessionId: String,
        command: String,
        arguments: String,
        agent: String,
    ): Result<Unit> = runCatching {
        val holder = activeHolder().first() ?: error("no active server")
        ApiFactory.api(holder.profile, holder.password, holder.settings).rawCommand(
            sessionId,
            dev.opencode.remote.data.api.CommandExecute(command = command, arguments = arguments, agent = agent),
        )
    }

    // --- internals ---
    private data class Holder(val profile: ServerProfile, val password: String?, val settings: AppSettings)

    /**
     * Active profile WITH resolved password, in a single flow — no cache race.
     * Password comes from SecureStore (source of truth) on every emission.
     */
    private fun passwordHolder(): Flow<Holder?> = combine(
        servers.profiles, servers.activeProfileId,
    ) { profiles, id ->
        val p = profiles.firstOrNull { it.id == id } ?: return@combine null
        Holder(p, servers.getPassword(p.id), AppSettings())
    }

    private fun activeHolder(): Flow<Holder?> = passwordHolder()

    private fun applyEvent(ev: SseEvent) {
        when (ev.type) {
            "session.status" -> scope.launch { refreshStatusOnly() }
            "session.created", "session.updated", "session.deleted" -> scope.launch { refreshSessions() }
            "message.updated", "message.created" -> scope.launch { refreshSessions() }
            "permission.asked" -> scope.launch { permissions.refresh() }
            "permission.replied" -> scope.launch {
                ev.requestID?.let { permissions.markRepliedExternally(it) }
                permissions.refresh()
            }
            "question.asked" -> scope.launch { questions.refresh() }
            "question.replied", "question.rejected" -> scope.launch {
                ev.requestID?.let { questions.markSettledExternally(it) }
                questions.refresh()
            }
        }
    }

    private suspend fun refreshStatusOnly() {
        val holder = activeHolder().first() ?: return
        val api = ApiFactory.api(holder.profile, holder.password, holder.settings)
        _status.value = DtoMap.parseStatusMap(api.rawStatus())
    }
}

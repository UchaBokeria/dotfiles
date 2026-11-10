package dev.opencode.remote.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import dev.opencode.remote.domain.ChatMessage
import dev.opencode.remote.domain.ChatPart
import dev.opencode.remote.domain.ChatRepository
import dev.opencode.remote.domain.OutPart
import dev.opencode.remote.domain.Role
import dev.opencode.remote.domain.SettingsRepository
import java.util.UUID
import javax.inject.Inject
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

data class ChatUiState(
    val messages: List<ChatMessage> = emptyList(),
    val streamingText: Map<String, String> = emptyMap(),
    val busy: Boolean = false,
    val input: String = "",
    val error: String? = null,
    val offline: Boolean = false,
    // P2: per-session send prefs (persisted in P4 with Room; memory here per spec).
    val agent: String = "build",
    val modelProviderID: String? = null,
    val modelID: String? = null,
    val variant: String? = null,
    val websearchOn: Boolean = true,
    val memoryOn: Boolean = true,
    val linkedProjectId: String? = null,
    val commands: List<dev.opencode.remote.domain.CommandInfo> = emptyList(),
    val agents: List<dev.opencode.remote.domain.AgentInfo> = emptyList(),
    val providers: List<dev.opencode.remote.domain.ProviderInfo> = emptyList(),
    val toolIds: List<String> = emptyList(),
    val sessionTokensIn: Long = 0,
    val sessionTokensOut: Long = 0,
    val sessionCost: Double = 0.0,
    val contextLimit: Long = 0,
    val staged: List<StagedAttachment> = emptyList(),
)
/**
 * H1: thread + streaming + send. Streaming deltas from repo events append into
 * [streamingText] keyed "msgId:partId"; full refresh on session.idle (grapeot rules).
 */
@HiltViewModel
class ChatViewModel @Inject constructor(
    private val chat: ChatRepository,
    private val settings: SettingsRepository,
    private val permissions: dev.opencode.remote.domain.PermissionRepository,
    private val questions: dev.opencode.remote.domain.QuestionRepository,
    private val catalog: dev.opencode.remote.domain.CatalogRepository,
    private val projects: dev.opencode.remote.domain.ProjectRepository,
    @dagger.hilt.android.qualifiers.ApplicationContext private val appContext: android.content.Context,
) : ViewModel() {

    private val _state = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = _state.asStateFlow()

    private var sessionId: String = ""
    private var eventJob: Job? = null
    private var lastFrameAt = 0L

    fun open(id: String) {
        sessionId = id
        load()
        viewModelScope.launch {
            val s = settings.settings.first()
            val link = projects.sessionLinks.first()[id]
            _state.value = _state.value.copy(
                agent = s.defaultAgent,
                websearchOn = s.websearchDefaultOn,
                memoryOn = s.memoryDefaultOn,
                linkedProjectId = link,
            )
            catalog.refresh()
        }
        viewModelScope.launch {
            kotlinx.coroutines.flow.combine(
                catalog.agents, catalog.commands, catalog.providers, catalog.toolIds,
            ) { agents, commands, providers, tools ->
                _state.value = _state.value.copy(
                    agents = agents, commands = commands, providers = providers, toolIds = tools,
                )
            }.collect {}
        }
        eventJob?.cancel()
        eventJob = viewModelScope.launch {
            android.util.Log.d("OC-CHAT", "event collector start ses=$sessionId")
            chat.events.collect { ev ->
                android.util.Log.d("OC-CHAT", "event ${ev.type} ses=${ev.sessionID}")
                if (ev.sessionID != null && ev.sessionID != sessionId) return@collect
                lastFrameAt = System.currentTimeMillis()
                when {
                    ev.type == "session.idle" || ev.type == "session.status" -> {
                        clearStreaming()
                        load()
                    }
                    ev.type == "message.part.delta" || ev.type == "message.part.updated" -> {
                        val key = "${ev.messageID}:${ev.partID}"
                        val delta = ev.delta ?: ""
                        if (delta.isNotEmpty()) {
                            _state.value = _state.value.copy(
                                streamingText = _state.value.streamingText + (key to (
                                    (_state.value.streamingText[key] ?: "") + delta
                                    )),
                            )
                        }
                    }
                    ev.type == "session.error" -> {
                        _state.value = _state.value.copy(
                            error = ev.errorMessage ?: "session error",
                            busy = false,
                        )
                    }
                    ev.type.startsWith("session.") || ev.type.startsWith("message.") -> {
                        // Other session/message events → light reconcile (debounced by load()).
                    }
                }
            }
        }
        // Watchdog: no frame >20s while busy → one REST reconcile (grapeot rule).
        viewModelScope.launch {
            while (true) {
                delay(5_000)
                val st = _state.value
                if (st.busy && lastFrameAt != 0L &&
                    System.currentTimeMillis() - lastFrameAt > 20_000
                ) {
                    android.util.Log.d("OC-CHAT", "watchdog reconcile")
                    load()
                    lastFrameAt = System.currentTimeMillis()
                }
            }
        }
    }

    fun setInput(t: String) {
        _state.value = _state.value.copy(input = t)
    }

    private var dictationBase: String = ""

    /** H4: called when dictation starts; partials/final replace the dictated segment. */
    fun startDictation() {
        dictationBase = _state.value.input
    }

    fun dictationText(hypothesis: String) {
        val sep = if (dictationBase.isBlank()) "" else " "
        _state.value = _state.value.copy(input = dictationBase + sep + hypothesis)
    }

    fun setAgent(agent: String) {
        _state.value = _state.value.copy(agent = agent)
    }

    fun setModel(providerID: String?, modelID: String?, variant: String?) {
        _state.value = _state.value.copy(
            modelProviderID = providerID, modelID = modelID, variant = variant,
        )
    }

    fun setWebsearch(on: Boolean) {
        _state.value = _state.value.copy(websearchOn = on)
    }

    fun setMemory(on: Boolean) {
        _state.value = _state.value.copy(memoryOn = on)
    }

    /** Project system injection (D1/H5): instructions always, memoryNote only when memory on. */
    private suspend fun projectSystem(): String? {
        val pid = _state.value.linkedProjectId ?: return null
        val project = projects.projects.first().firstOrNull { it.id == pid } ?: return null
        val parts = listOfNotNull(
            project.instructions.takeIf { it.isNotBlank() },
            project.memoryNote.takeIf { _state.value.memoryOn && it.isNotBlank() }?.let {
                "Project memory:\n$it"
            },
        )
        return parts.joinToString("\n\n").takeIf { it.isNotBlank() }
    }

    // --- P3: attachments (H2) ---
    fun stageAttachment(att: StagedAttachment) {
        _state.value = _state.value.copy(staged = _state.value.staged + att)
    }

    fun unstageAttachment(id: String) {
        _state.value = _state.value.copy(staged = _state.value.staged.filterNot { it.id == id })
    }

    /** Slash-command candidates for the current input (H12). */
    fun commandSuggestions(): List<dev.opencode.remote.domain.CommandInfo> {
        val input = _state.value.input
        if (!input.startsWith("/")) return emptyList()
        val q = input.drop(1).substringBefore(" ").lowercase()
        return _state.value.commands.filter { it.name.lowercase().startsWith(q) }.take(6)
    }

    fun acceptCommand(cmd: dev.opencode.remote.domain.CommandInfo) {
        _state.value = _state.value.copy(input = "/${cmd.name} ")
    }

    /** Resolve the webfetch tool id for H3 gating (D3); null = leave tools untouched. */
    private fun websearchTools(): Map<String, Boolean>? {
        if (_state.value.websearchOn) return null
        val id = _state.value.toolIds.firstOrNull {
            it.equals("webfetch", ignoreCase = true) || it.contains("webfetch", ignoreCase = true)
        } ?: return mapOf("webfetch" to false)
        return mapOf(id to false)
    }

    fun send() {
        val text = _state.value.input.trim()
        if ((text.isEmpty() && _state.value.staged.isEmpty()) || _state.value.busy) return
        // Slash command path (H12): "/name args..." executes via POST command.
        if (text.startsWith("/")) {
            val name = text.drop(1).substringBefore(" ").lowercase()
            val args = text.drop(1 + text.drop(1).substringBefore(" ").length).trim()
            val match = _state.value.commands.firstOrNull { it.name.lowercase() == name }
            if (match != null) {
                sendCommand(match.name, args)
                return
            }
        }
        viewModelScope.launch {
            val st = _state.value
            val settingsNow = settings.settings.first()
            // Resolve staged attachments off the main thread (IO inside withContext).
            val fileParts = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                st.staged.mapNotNull { att ->
                    resolveAttachment(
                        appContext, att,
                        settingsNow.imageQuality, settingsNow.maxImageDim, settingsNow.maxFileBytes,
                    )?.let { OutPart(type = "file", mime = it.mime, filename = it.filename, url = it.dataUrl) }
                }
            }
            val textParts = if (text.isNotBlank()) {
                listOf(OutPart(type = "text", text = text))
            } else emptyList()
            if (textParts.isEmpty() && fileParts.isEmpty()) return@launch
            val optimistic = ChatMessage(
                id = "local-" + UUID.randomUUID(),
                role = Role.USER,
                parts = textParts.map { ChatPart.Text(it.text ?: "") } +
                    fileParts.map { ChatPart.File(it.mime ?: "", it.filename ?: "") },
                optimistic = true,
            )
            _state.value = st.copy(
                messages = st.messages + optimistic,
                input = "",
                staged = emptyList(),
                busy = true,
                error = null,
            )
            lastFrameAt = System.currentTimeMillis()
            val systemPrompt = projectSystem()
            android.util.Log.d(
                "OC-CHAT",
                "send agent=${st.agent} model=${st.modelID} variant=${st.variant} " +
                    "systemLen=${systemPrompt?.length ?: -1} websearch=${st.websearchOn}",
            )
            chat.send(
                sessionId,
                textParts + fileParts,
                st.agent,
                modelProviderID = st.modelProviderID,
                modelID = st.modelID,
                variant = st.variant,
                tools = websearchTools(),
                system = systemPrompt,
            ).onFailure { err ->
                _state.value = _state.value.copy(
                    messages = _state.value.messages.filterNot { it.id == optimistic.id },
                    input = text,
                    busy = false,
                    error = err.message,
                )
            }
        }
    }

    private fun sendCommand(name: String, args: String) {
        viewModelScope.launch {
            val st = _state.value
            _state.value = st.copy(input = "", busy = true, error = null)
            lastFrameAt = System.currentTimeMillis()
            chat.executeCommand(sessionId, name, args, st.agent).onFailure { err ->
                _state.value = _state.value.copy(busy = false, error = err.message)
            }
        }
    }

    fun abort() {
        viewModelScope.launch {
            chat.abortSession(sessionId)
            _state.value = _state.value.copy(busy = false)
        }
    }

    // --- P2: approvals (H7 + questions) ---
    val sessionPermissions = permissions.pending.map { list ->
        list.filter { it.sessionID == sessionId || it.sessionID.isBlank() }
    }

    val sessionQuestions = questions.pending.map { list ->
        list.filter { it.sessionID == sessionId || it.sessionID.isBlank() }
    }

    fun replyPermission(id: String, kind: dev.opencode.remote.domain.PermissionReplyKind) {
        viewModelScope.launch {
            permissions.reply(id, kind).onFailure {
                _state.value = _state.value.copy(error = it.message)
            }
        }
    }

    fun answerQuestion(questionId: String, answers: List<List<String>>) {
        viewModelScope.launch {
            questions.reply(questionId, answers).onFailure {
                _state.value = _state.value.copy(error = it.message)
            }
        }
    }

    fun cancelQuestion(questionId: String) {
        viewModelScope.launch {
            questions.reject(questionId).onFailure {
                _state.value = _state.value.copy(error = it.message)
            }
        }
    }

    fun retry() {
        load()
        _state.value = _state.value.copy(error = null)
    }

    private fun load() {
        viewModelScope.launch {
            android.util.Log.d("OC-CHAT", "load start ses=$sessionId")
            chat.messages(sessionId).fold(
                onSuccess = { msgs ->
                    android.util.Log.d("OC-CHAT", "load ok n=${msgs.size}")
                    var tin = 0L
                    var tout = 0L
                    var cost = 0.0
                    msgs.forEach { m ->
                        m.parts.forEach { p ->
                            if (p is ChatPart.StepFinish) {
                                tin += p.input
                                tout += p.output
                                cost += p.cost
                            }
                        }
                    }
                    val st = _state.value
                    val limit = st.providers
                        .firstOrNull { it.id == st.modelProviderID }
                        ?.models?.firstOrNull { it.id == st.modelID }
                        ?.contextLimit ?: 0L
                    _state.value = st.copy(
                        messages = mergeStreaming(msgs),
                        busy = false,
                        sessionTokensIn = tin,
                        sessionTokensOut = tout,
                        sessionCost = cost,
                        contextLimit = limit,
                    )
                },
                onFailure = { err ->
                    android.util.Log.d("OC-CHAT", "load fail ${err.message}")
                    _state.value = _state.value.copy(
                        busy = false,
                        error = err.message,
                        offline = err.message?.contains("Unable to resolve", ignoreCase = true) == true,
                    )
                },
            )
        }
    }

    private fun clearStreaming() {
        if (_state.value.streamingText.isNotEmpty()) {
            _state.value = _state.value.copy(streamingText = emptyMap())
        }
    }

    /** Overlay streaming tails onto loaded messages so text never flashes (grapeot anti-flash). */
    private fun mergeStreaming(msgs: List<ChatMessage>): List<ChatMessage> {
        val tails = _state.value.streamingText
        if (tails.isEmpty()) return msgs
        return msgs.map { m ->
            val overlay = m.parts.map { p ->
                val key = tails.keys.firstOrNull { it.startsWith(m.id + ":") }
                if (p is ChatPart.Text && key != null) ChatPart.Text(p.text + (tails[key] ?: "")) else p
            }
            m.copy(parts = overlay)
        }
    }

    override fun onCleared() {
        eventJob?.cancel()
    }
}

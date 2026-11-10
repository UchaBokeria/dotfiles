package dev.opencode.remote.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import dev.opencode.remote.domain.ChatRepository
import dev.opencode.remote.domain.ChatSession
import dev.opencode.remote.domain.SessionBusy
import dev.opencode.remote.domain.SettingsRepository
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

data class SessionRow(
    val session: ChatSession,
    val busy: SessionBusy,
    val temp: Boolean,
)

data class SessionsUiState(
    val rows: List<SessionRow> = emptyList(),
    val query: String = "",
    val showTemp: Boolean = true,
    val refreshing: Boolean = false,
    val error: String? = null,
    val projects: List<dev.opencode.remote.domain.Project> = emptyList(),
    val projectFilter: String? = null,
    val links: Map<String, String> = emptyMap(),
)

/** C1–C3: session list/search/new/temp/rename/delete. */
@HiltViewModel
class SessionsViewModel @Inject constructor(
    private val chat: ChatRepository,
    private val settings: SettingsRepository,
    private val projectsRepo: dev.opencode.remote.domain.ProjectRepository,
) : ViewModel() {

    private val _query = MutableStateFlow("")
    private val _refreshing = MutableStateFlow(false)
    private val _error = MutableStateFlow<String?>(null)
    private val _projectFilter = MutableStateFlow<String?>(null)

    val projects = projectsRepo.projects
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    val uiState: StateFlow<SessionsUiState> = combine(
        combine(chat.sessions, chat.statusMap, chat.tempSessionIds, chat.showTemp, ::SessionQuad),
        combine(_query, _refreshing, _error, ::QueryTriple),
        combine(projectsRepo.projects, projectsRepo.sessionLinks, _projectFilter) { ps, links, filter ->
            Triple(ps, links, filter)
        },
    ) { quad, triple, proj ->
        val (plist, links, filter) = proj
        val q = triple.query.trim().lowercase()
        val rows = quad.sessions
            .filter { quad.showTemp || it.id !in quad.temp }
            .filter { f -> filter == null || links[f.id] == filter }
            .filter { q.isEmpty() || it.title.lowercase().contains(q) || it.id.lowercase().contains(q) }
            .sortedByDescending { it.updatedAt }
            .map { s ->
                SessionRow(
                    session = s,
                    busy = quad.status[s.id]?.toBusy() ?: SessionBusy.IDLE,
                    temp = s.id in quad.temp,
                )
            }
        SessionsUiState(rows, triple.query, quad.showTemp, triple.refreshing, triple.error,
            plist, filter, links)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), SessionsUiState())

    private data class SessionQuad(
        val sessions: List<ChatSession>,
        val status: Map<String, dev.opencode.remote.domain.SessionStatus>,
        val temp: Set<String>,
        val showTemp: Boolean,
    )

    private data class QueryTriple(
        val query: String,
        val refreshing: Boolean,
        val error: String?,
    )

    init {
        refresh()
    }

    fun setQuery(q: String) {
        _query.value = q
    }

    fun setShowTemp(show: Boolean) {
        viewModelScope.launch { chat.setShowTemp(show) }
    }

    fun setProjectFilter(id: String?) {
        _projectFilter.value = id
    }

    fun createSession(temp: Boolean, projectId: String? = null, onCreated: (String) -> Unit) {
        viewModelScope.launch {
            chat.createSession(title = null, temp = temp).fold(
                onSuccess = {
                    if (projectId != null) projectsRepo.linkSession(it.id, projectId)
                    onCreated(it.id)
                },
                onFailure = { _error.value = it.message },
            )
        }
    }

    fun refresh() {
        viewModelScope.launch {
            _refreshing.value = true
            _error.value = null
            chat.refreshSessions().onFailure { _error.value = it.message }
            _refreshing.value = false
        }
    }

    fun createWithDefaultTemp(onCreated: (String) -> Unit) {
        viewModelScope.launch {
            val temp = settings.settings.first().defaultTemporary
            createSession(temp = temp, onCreated = onCreated)
        }
    }

    fun rename(id: String, title: String) {
        viewModelScope.launch {
            chat.renameSession(id, title).onFailure { _error.value = it.message }
        }
    }

    fun delete(id: String) {
        viewModelScope.launch {
            chat.deleteSession(id).onFailure { _error.value = it.message }
        }
    }

    fun purgeTemp() {
        viewModelScope.launch {
            chat.purgeTempSessions().onFailure { _error.value = it.message }
        }
    }
}

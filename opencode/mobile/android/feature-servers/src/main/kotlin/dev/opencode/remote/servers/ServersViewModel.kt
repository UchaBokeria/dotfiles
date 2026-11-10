package dev.opencode.remote.servers

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import dev.opencode.remote.domain.ConnectionState
import dev.opencode.remote.domain.ServerProfile
import dev.opencode.remote.domain.ServerRepository
import java.util.UUID
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

data class ServerUiState(
    val profiles: List<ServerProfile> = emptyList(),
    val activeId: String? = null,
    val connection: ConnectionState = ConnectionState.Disconnected,
)

/** S1/S2: profile CRUD + active switching + health check. */
@HiltViewModel
class ServersViewModel @Inject constructor(
    private val servers: ServerRepository,
) : ViewModel() {

    private val _connection = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
    val connection = _connection.asStateFlow()

    val uiState: StateFlow<ServerUiState> = combine(
        servers.profiles, servers.activeProfileId, _connection,
    ) { profiles, activeId, connection ->
        ServerUiState(profiles, activeId, connection)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), ServerUiState())

    fun saveProfile(
        existing: ServerProfile?,
        name: String,
        baseUrl: String,
        username: String,
        password: String,
        defaultDirectory: String?,
    ) {
        viewModelScope.launch {
            val profile = (existing ?: ServerProfile(
                id = UUID.randomUUID().toString(),
                name = "",
                baseUrl = "",
            )).copy(
                name = name.trim(),
                baseUrl = baseUrl.trim().trimEnd('/'),
                username = username.trim().ifBlank { "opencode" },
                defaultDirectory = defaultDirectory?.trim().orEmpty().ifBlank { null },
            )
            servers.upsertProfile(profile, password.ifBlank { null })
            servers.setActiveProfile(profile.id)
            checkHealth(profile.id)
        }
    }

    fun deleteProfile(id: String) {
        viewModelScope.launch { servers.deleteProfile(id) }
    }

    fun setActive(id: String) {
        viewModelScope.launch {
            servers.setActiveProfile(id)
            checkHealth(id)
        }
    }

    fun checkHealth(id: String) {
        viewModelScope.launch {
            _connection.value = ConnectionState.Connecting
            val profile = servers.profilesSnapshot(id) ?: run {
                _connection.value = ConnectionState.Failed("profile not found")
                return@launch
            }
            servers.checkHealth(profile).fold(
                onSuccess = { _connection.value = ConnectionState.Connected(it) },
                onFailure = { _connection.value = ConnectionState.Failed(it.message ?: "unreachable") },
            )
        }
    }

    fun disconnect() {
        _connection.value = ConnectionState.Disconnected
    }
}

private suspend fun ServerRepository.profilesSnapshot(id: String): ServerProfile? =
    profiles.first().firstOrNull { it.id == id }

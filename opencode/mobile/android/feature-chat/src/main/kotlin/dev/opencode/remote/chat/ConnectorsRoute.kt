package dev.opencode.remote.chat

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import dev.opencode.remote.domain.CatalogRepository
import dev.opencode.remote.domain.McpServerInfo
import javax.inject.Inject
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

@HiltViewModel
class ConnectorsViewModel @Inject constructor(
    private val catalog: CatalogRepository,
) : ViewModel() {
    val servers: StateFlow<List<McpServerInfo>> = catalog.mcpServers
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    init {
        viewModelScope.launch { catalog.refresh() }
    }
}

@Composable
fun ConnectorsRoute(vm: ConnectorsViewModel = hiltViewModel()) {
    val servers by vm.servers.collectAsStateWithLifecycle()
    ConnectorsScreen(servers)
}

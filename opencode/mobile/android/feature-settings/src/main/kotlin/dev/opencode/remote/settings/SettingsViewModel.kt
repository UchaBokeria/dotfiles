package dev.opencode.remote.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import dev.opencode.remote.domain.AppSettings
import dev.opencode.remote.domain.SettingsRepository
import dev.opencode.remote.domain.ThemeMode
import dev.opencode.remote.domain.ThemeRepository
import javax.inject.Inject
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/** X1: settings read/write + export/import. */
@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val settings: SettingsRepository,
    private val themes: ThemeRepository,
) : ViewModel() {

    val state = settings.settings
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), AppSettings())

    fun setDefaultTemporary(v: Boolean) = update { it.copy(defaultTemporary = v) }
    fun setWebsearch(v: Boolean) = update { it.copy(websearchDefaultOn = v) }
    fun setMemory(v: Boolean) = update { it.copy(memoryDefaultOn = v) }
    fun setEnterToSend(v: Boolean) = update { it.copy(enterToSend = v) }
    fun setHaptics(v: Boolean) = update { it.copy(haptics = v) }
    fun setDefaultAgent(v: String) = update { it.copy(defaultAgent = v) }
    fun setThemeScheme(id: String) {
        viewModelScope.launch { themes.setScheme(id) }
    }

    fun setThemeMode(mode: ThemeMode) {
        viewModelScope.launch { themes.setMode(mode) }
    }

    fun exportAsync(onDone: (String) -> Unit) {
        viewModelScope.launch { onDone(settings.exportJson()) }
    }

    fun importJson(json: String, onDone: (Boolean) -> Unit) {
        viewModelScope.launch { onDone(settings.importJson(json).isSuccess) }
    }

    fun setOnboardingDone() = update { it.copy(onboardingDone = true) }

    private fun update(f: (AppSettings) -> AppSettings) {
        viewModelScope.launch { settings.update(f) }
    }
}

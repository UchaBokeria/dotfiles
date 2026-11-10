package dev.opencode.remote.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import dev.opencode.remote.domain.ThemeMode

/** X1: settings screen skeleton — all doc-13 groups present, rows wired incrementally. */
@Composable
fun SettingsScreen(vm: SettingsViewModel = hiltViewModel()) {
    val s by vm.state.collectAsStateWithLifecycle()
    var exported by remember { mutableStateOf("") }
    Column(
        Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding()
            .verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Settings", style = MaterialTheme.typography.headlineMedium)
        Group("Sessions") {
            Toggle("Temporary by default", s.defaultTemporary, vm::setDefaultTemporary)
        }
        Group("Chat") {
            Toggle("Web search default on", s.websearchDefaultOn, vm::setWebsearch)
            Toggle("Memory default on", s.memoryDefaultOn, vm::setMemory)
            Toggle("Enter to send", s.enterToSend, vm::setEnterToSend)
            Toggle("Haptics", s.haptics, vm::setHaptics)
        }
        Group("Agent") {
            Toggle("Default agent is build", s.defaultAgent == "build") {
                vm.setDefaultAgent(if (it) "build" else "ask")
            }
        }
        Group("Theme") {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { vm.setThemeScheme("neon-dark") }) { Text("Neon dark") }
                Button(onClick = { vm.setThemeScheme("neon-light") }) { Text("Neon light") }
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { vm.setThemeMode(ThemeMode.DARK) }) { Text("Dark") }
                Button(onClick = { vm.setThemeMode(ThemeMode.LIGHT) }) { Text("Light") }
                Button(onClick = { vm.setThemeMode(ThemeMode.SYSTEM) }) { Text("Auto") }
            }
        }
        Group("Advanced") {
            Button(onClick = { vm.exportAsync { exported = it } }) { Text("Export JSON") }
            if (exported.isNotEmpty()) {
                OutlinedTextField(exported, {}, readOnly = true, modifier = Modifier.fillMaxWidth())
            }
        }
    }
}

@Composable
private fun Group(title: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.secondary)
        content()
    }
}

@Composable
private fun Toggle(label: String, value: Boolean, onChange: (Boolean) -> Unit) {
    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(label)
        Switch(value, onChange)
    }
}

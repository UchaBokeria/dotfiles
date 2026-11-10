package dev.opencode.remote.servers

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import dev.opencode.remote.domain.ConnectionState
import dev.opencode.remote.domain.ServerProfile

/** S1: server list + add/edit + switch. Edge-to-edge insets per-screen (doc 08 §4). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ServersScreen(vm: ServersViewModel = hiltViewModel()) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    var editing by remember { mutableStateOf<ServerProfile?>(null) }
    var adding by remember { mutableStateOf(false) }

    Scaffold(
        modifier = Modifier.fillMaxSize(),
        topBar = {
            Column(Modifier.statusBarsPadding().padding(16.dp)) {
                Text("Servers", style = MaterialTheme.typography.headlineMedium)
                Text(
                    connectionLine(state.connection),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.secondary,
                )
            }
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { adding = true }) { Text("+") }
        },
    ) { inner ->
        LazyColumn(
            modifier = Modifier.padding(inner).navigationBarsPadding().fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(state.profiles, key = { it.id }) { profile ->
                Card(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp)
                        .clickable { vm.setActive(profile.id) },
                ) {
                    Column(Modifier.padding(16.dp)) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(profile.name, style = MaterialTheme.typography.titleMedium)
                            if (profile.id == state.activeId) Text("● active", color = MaterialTheme.colorScheme.tertiary)
                        }
                        Text(profile.baseUrl, style = MaterialTheme.typography.bodySmall)
                        Text(
                            "user ${profile.username}" +
                                (profile.serverVersion?.let { " · v$it" } ?: ""),
                            style = MaterialTheme.typography.bodySmall,
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(onClick = { vm.checkHealth(profile.id) }) { Text("Test") }
                            OutlinedButton(onClick = { editing = profile }) { Text("Edit") }
                            OutlinedButton(onClick = { vm.deleteProfile(profile.id) }) { Text("Delete") }
                        }
                    }
                }
            }
        }
    }

    if (adding || editing != null) {
        ServerEditor(
            existing = editing,
            onDismiss = { adding = false; editing = null },
            onSave = { name, url, user, pass, dir ->
                vm.saveProfile(editing, name, url, user, pass, dir)
                adding = false; editing = null
            },
        )
    }
}

private fun connectionLine(c: ConnectionState): String = when (c) {
    ConnectionState.Disconnected -> "disconnected"
    ConnectionState.Connecting -> "connecting…"
    is ConnectionState.Connected -> "connected · v${c.health.version}"
    is ConnectionState.Failed -> "failed: ${c.reason}"
}

@Composable
private fun ServerEditor(
    existing: ServerProfile?,
    onDismiss: () -> Unit,
    onSave: (name: String, url: String, user: String, pass: String, dir: String) -> Unit,
) {
    var name by remember { mutableStateOf(existing?.name ?: "") }
    var url by remember { mutableStateOf(existing?.baseUrl ?: "https://opencode.uchabokeria.space") }
    var user by remember { mutableStateOf(existing?.username ?: "opencode") }
    var pass by remember { mutableStateOf("") }
    var dir by remember { mutableStateOf(existing?.defaultDirectory ?: "") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (existing == null) "Add server" else "Edit server") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(name, { name = it }, label = { Text("Name") })
                OutlinedTextField(url, { url = it }, label = { Text("Base URL") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, autoCorrect = false))
                OutlinedTextField(user, { user = it }, label = { Text("Username") },
                    keyboardOptions = KeyboardOptions(autoCorrect = false))
                OutlinedTextField(
                    pass, { pass = it }, label = { Text("Password (blank keeps saved)") },
                    visualTransformation = PasswordVisualTransformation(),
                )
                OutlinedTextField(dir, { dir = it }, label = { Text("Default directory (optional)") },
                    keyboardOptions = KeyboardOptions(autoCorrect = false))
            }
        },
        confirmButton = {
            Button(
                onClick = { onSave(name, url, user, pass, dir) },
                enabled = name.isNotBlank() && url.isNotBlank(),
            ) { Text("Save & connect") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

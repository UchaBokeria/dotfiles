package dev.opencode.remote.chat

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
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.TextButton
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dagger.hilt.android.lifecycle.HiltViewModel
import dev.opencode.remote.domain.Project
import dev.opencode.remote.domain.ProjectRepository
import java.util.UUID
import javax.inject.Inject
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

@HiltViewModel
class ProjectsViewModel @Inject constructor(
    private val projects: ProjectRepository,
) : ViewModel() {
    val state = projects.projects
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    fun save(existing: Project?, name: String, directories: String, instructions: String, memory: String) {
        viewModelScope.launch {
            projects.upsert(
                (existing ?: Project(id = UUID.randomUUID().toString(), name = "")).copy(
                    name = name.trim(),
                    directories = directories.split("\n").map { it.trim() }.filter { it.isNotEmpty() },
                    instructions = instructions,
                    memoryNote = memory,
                ),
            )
        }
    }

    fun delete(id: String) {
        viewModelScope.launch { projects.delete(id) }
    }
}

/** H11: project manager — CRUD + directories + instructions + memory. */
@Composable
fun ProjectsScreen(vm: ProjectsViewModel = hiltViewModel()) {
    val list by vm.state.collectAsStateWithLifecycle()
    var editing by remember { mutableStateOf<Project?>(null) }
    var adding by remember { mutableStateOf(false) }
    Scaffold(
        modifier = Modifier.fillMaxSize(),
        topBar = { Text("Projects", style = MaterialTheme.typography.headlineMedium, modifier = Modifier.statusBarsPadding().padding(16.dp)) },
        floatingActionButton = { FloatingActionButton(onClick = { adding = true }) { Text("+") } },
    ) { inner ->
        LazyColumn(
            Modifier.padding(inner).navigationBarsPadding().fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(list, key = { it.id }) { p ->
                Card(Modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(p.name, style = MaterialTheme.typography.titleMedium)
                        if (p.directories.isNotEmpty()) {
                            Text(p.directories.joinToString("\n"), style = MaterialTheme.typography.bodySmall)
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(onClick = { editing = p }) { Text("Edit") }
                            OutlinedButton(onClick = { vm.delete(p.id) }) { Text("Delete") }
                        }
                    }
                }
            }
        }
    }
    if (adding || editing != null) {
        ProjectEditor(
            existing = editing,
            onDismiss = { adding = false; editing = null },
            onSave = { n, d, i, m ->
                vm.save(editing, n, d, i, m)
                adding = false; editing = null
            },
        )
    }
}

@Composable
private fun ProjectEditor(
    existing: Project?,
    onDismiss: () -> Unit,
    onSave: (name: String, dirs: String, instructions: String, memory: String) -> Unit,
) {
    var name by remember { mutableStateOf(existing?.name ?: "") }
    var dirs by remember { mutableStateOf(existing?.directories?.joinToString("\n") ?: "") }
    var instructions by remember { mutableStateOf(existing?.instructions ?: "") }
    var memory by remember { mutableStateOf(existing?.memoryNote ?: "") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (existing == null) "New project" else "Edit project") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(name, { name = it }, label = { Text("Name") })
                OutlinedTextField(dirs, { dirs = it }, label = { Text("Directories (one per line)") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, autoCorrect = false))
                OutlinedTextField(instructions, { instructions = it }, label = { Text("Instructions") })
                OutlinedTextField(memory, { memory = it }, label = { Text("Memory note") })
            }
        },
        confirmButton = {
            Button(onClick = { onSave(name, dirs, instructions, memory) }, enabled = name.isNotBlank()) {
                Text("Save")
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

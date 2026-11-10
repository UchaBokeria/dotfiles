package dev.opencode.remote.chat

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
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dev.opencode.remote.domain.SessionBusy
import java.text.DateFormat
import java.util.Date

/** C1–C3: session list + search + new/temp + rename/delete. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SessionsScreen(
    onOpenChat: (String) -> Unit,
    onOpenProjects: () -> Unit,
    vm: SessionsViewModel = hiltViewModel(),
) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    var renaming by remember { mutableStateOf<SessionRow?>(null) }
    var deleting by remember { mutableStateOf<SessionRow?>(null) }

    Scaffold(
        modifier = Modifier.fillMaxSize(),
        topBar = {
            Column(Modifier.statusBarsPadding().padding(horizontal = 16.dp, vertical = 8.dp)) {
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("Sessions", style = MaterialTheme.typography.headlineMedium)
                    TextButton(onClick = onOpenProjects) { Text("Projects") }
                }
                OutlinedTextField(
                    value = state.query,
                    onValueChange = vm::setQuery,
                    label = { Text("Search sessions") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("Show temporary", style = MaterialTheme.typography.bodySmall)
                    Switch(state.showTemp, vm::setShowTemp)
                }
                if (state.projects.isNotEmpty()) {
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        FilterChip(
                            selected = state.projectFilter == null,
                            onClick = { vm.setProjectFilter(null) },
                            label = { Text("All") },
                        )
                        state.projects.forEach { p ->
                            FilterChip(
                                selected = state.projectFilter == p.id,
                                onClick = { vm.setProjectFilter(p.id) },
                                label = { Text(p.name) },
                            )
                        }
                    }
                }
                state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
        },
        floatingActionButton = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                FloatingActionButton(onClick = {
                    vm.createSession(temp = true, projectId = state.projectFilter, onCreated = onOpenChat)
                }) {
                    Text("T")
                }
                FloatingActionButton(onClick = { vm.createWithDefaultTemp(onOpenChat) }) {
                    Text("+")
                }
            }
        },
    ) { inner ->
        PullToRefreshBox(
            isRefreshing = state.refreshing,
            onRefresh = vm::refresh,
            modifier = Modifier.padding(inner).navigationBarsPadding().fillMaxSize(),
        ) {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(state.rows, key = { it.session.id }) { row ->
                    Card(
                        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp)
                            .clickable { onOpenChat(row.session.id) },
                    ) {
                        Column(Modifier.padding(16.dp)) {
                            Row(
                                Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Text(
                                    row.session.title.ifBlank { row.session.id.take(12) },
                                    style = MaterialTheme.typography.titleMedium,
                                )
                                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    if (row.temp) Text(
                                        "TEMP",
                                        color = MaterialTheme.colorScheme.secondary,
                                        style = MaterialTheme.typography.labelSmall,
                                    )
                                    Text(
                                        dot(row.busy),
                                        color = dotColor(row.busy),
                                    )
                                }
                            }
                            Text(
                                fmtTime(row.session.updatedAt),
                                style = MaterialTheme.typography.bodySmall,
                            )
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedButton(onClick = { renaming = row }) { Text("Rename") }
                                OutlinedButton(onClick = { deleting = row }) { Text("Delete") }
                            }
                        }
                    }
                }
            }
        }
    }

    renaming?.let { row ->
        var title by remember(row.session.id) { mutableStateOf(row.session.title) }
        AlertDialog(
            onDismissRequest = { renaming = null },
            title = { Text("Rename session") },
            text = {
                OutlinedTextField(title, { title = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
            },
            confirmButton = {
                Button(onClick = { vm.rename(row.session.id, title); renaming = null }) { Text("Save") }
            },
            dismissButton = { TextButton(onClick = { renaming = null }) { Text("Cancel") } },
        )
    }
    deleting?.let { row ->
        AlertDialog(
            onDismissRequest = { deleting = null },
            title = { Text("Delete session?") },
            text = { Text("This destroys the session on the server. Cannot be undone.") },
            confirmButton = {
                Button(onClick = { vm.delete(row.session.id); deleting = null }) { Text("Delete") }
            },
            dismissButton = { TextButton(onClick = { deleting = null }) { Text("Cancel") } },
        )
    }
}

private fun dot(b: SessionBusy): String = when (b) {
    SessionBusy.IDLE -> "●"
    SessionBusy.BUSY -> "◉"
    SessionBusy.RETRY -> "◌"
}

@Composable
private fun dotColor(b: SessionBusy) = when (b) {
    SessionBusy.IDLE -> MaterialTheme.colorScheme.outline
    SessionBusy.BUSY -> MaterialTheme.colorScheme.tertiary
    SessionBusy.RETRY -> MaterialTheme.colorScheme.error
}

private fun fmtTime(ms: Long): String =
    if (ms <= 0) "" else DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT).format(Date(ms))

package dev.opencode.remote.chat

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import dev.opencode.remote.domain.AgentInfo
import dev.opencode.remote.domain.CommandInfo
import dev.opencode.remote.domain.ProviderInfo

/** H8: agent chips (native plan/ask/build first, then custom agents). */
@Composable
fun AgentChipsRow(
    agents: List<AgentInfo>,
    selected: String,
    onSelect: (String) -> Unit,
) {
    val native = listOf("plan", "ask", "build")
    val ordered = (native.filter { n -> agents.any { it.name == n } || true } +
        agents.map { it.name }.filter { it !in native }).distinct()
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        ordered.take(6).forEach { name ->
            FilterChip(
                selected = selected == name,
                onClick = { onSelect(name) },
                label = { Text(name) },
            )
        }
    }
}

/** H9: model chip + bottom sheet (providers → models → effort). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ModelSelector(
    providers: List<ProviderInfo>,
    selectedProvider: String?,
    selectedModel: String?,
    selectedVariant: String?,
    onSelect: (providerID: String?, modelID: String?, variant: String?) -> Unit,
) {
    var open by remember { mutableStateOf(false) }
    var query by remember { mutableStateOf("") }
    var variant by remember { mutableStateOf(selectedVariant) }
    TextButton(onClick = { open = true }) {
        Text(
            listOfNotNull(selectedModel ?: "auto model", variant?.let { "· $it" }).joinToString(""),
            style = MaterialTheme.typography.bodySmall,
        )
    }
    if (open) {
        ModalBottomSheet(onDismissRequest = { open = false }) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Model", style = MaterialTheme.typography.titleMedium)
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    label = { Text("Search models") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    listOf(null to "auto", "none" to "none", "low" to "low", "medium" to "med", "high" to "high", "xhigh" to "xhigh", "max" to "max").forEach { (v, label) ->
                        FilterChip(
                            selected = variant == v,
                            onClick = { variant = v },
                            label = { Text(label) },
                        )
                    }
                }
                TextButton(onClick = {
                    onSelect(null, null, variant)
                    open = false
                }) { Text("Use server default") }
                LazyColumn(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    providers.forEach { p ->
                        val models = p.models.filter {
                            query.isBlank() || it.id.contains(query, ignoreCase = true) ||
                                it.name.contains(query, ignoreCase = true)
                        }
                        if (models.isNotEmpty()) {
                            item(key = "h-" + p.id) {
                                Text(p.name, style = MaterialTheme.typography.titleSmall)
                            }
                            items(models, key = { "m-" + p.id + "-" + it.id }) { m ->
                                Row(
                                    Modifier.fillMaxWidth().padding(vertical = 4.dp)
                                        .clickable {
                                            onSelect(p.id, m.id, variant)
                                            open = false
                                        },
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                ) {
                                    Text(m.name)
                                    if (selectedProvider == p.id && selectedModel == m.id) Text("✓")
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

/** H12: slash-command autocomplete sheet over the composer. */
@Composable
fun CommandSuggestions(
    suggestions: List<CommandInfo>,
    onPick: (CommandInfo) -> Unit,
) {
    if (suggestions.isEmpty()) return
    Column(Modifier.fillMaxWidth().padding(horizontal = 8.dp)) {
        suggestions.forEach { cmd ->
            Row(
                Modifier.fillMaxWidth().padding(vertical = 6.dp)
                    .clickable { onPick(cmd) },
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text("/" + cmd.name, style = MaterialTheme.typography.bodyMedium)
                Text(
                    cmd.description.take(60),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.outline,
                )
            }
        }
    }
}

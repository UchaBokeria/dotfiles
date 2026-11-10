package dev.opencode.remote.chat

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import dev.opencode.remote.domain.PermissionItem
import dev.opencode.remote.domain.PermissionReplyKind
import dev.opencode.remote.domain.QuestionItem

/** H7: permission card — Once / Always / Reject + terminal line after reply (grinev rule). */
@Composable
fun PermissionCard(
    item: PermissionItem,
    onReply: (PermissionReplyKind) -> Unit,
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiaryContainer),
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Permission: ${item.permission}", style = MaterialTheme.typography.titleSmall)
            if (item.patterns.isNotEmpty()) {
                Text(item.patterns.joinToString(", "), style = MaterialTheme.typography.bodySmall)
            }
            item.metadata["filepath"]?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            if (item.replied != null) {
                Text(
                    when (item.replied) {
                        "once" -> "allowed once ✓"
                        "always" -> "always allowed ✓"
                        "reject" -> "rejected ✕"
                        else -> "answered elsewhere"
                    },
                    style = MaterialTheme.typography.bodySmall,
                )
            } else {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { onReply(PermissionReplyKind.REJECT) }) { Text("Reject") }
                    OutlinedButton(onClick = { onReply(PermissionReplyKind.ONCE) }) { Text("Once") }
                    Button(onClick = { onReply(PermissionReplyKind.ALWAYS) }) { Text("Always") }
                }
            }
        }
    }
}

/** AskUserQuestion card — all prompts in order; single-tap / multi-select + Done / custom / cancel. */
@Composable
fun QuestionCard(
    item: QuestionItem,
    onSubmit: (List<List<String>>) -> Unit,
    onCancel: () -> Unit,
) {
    // Selections per prompt index; single-select prompts submit immediately only when alone.
    var selected by remember(item.id) { mutableStateOf(mapOf<Int, Set<String>>()) }
    var customs by remember(item.id) { mutableStateOf(mapOf<Int, String>()) }
    var showCustom by remember(item.id) { mutableStateOf(setOf<Int>()) }
    val aloneSingle = item.questions.size == 1 && !item.questions[0].multiple
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer),
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            item.questions.forEachIndexed { qi, prompt ->
                Text(prompt.header, style = MaterialTheme.typography.titleSmall)
                Text(prompt.question, style = MaterialTheme.typography.bodyMedium)
                prompt.options.forEach { opt ->
                    val on = opt.label in (selected[qi] ?: emptySet())
                    FilterChip(
                        selected = on,
                        onClick = {
                            if (!prompt.multiple && aloneSingle) {
                                onSubmit(listOf(listOf(opt.label)))
                            } else {
                                val cur = selected[qi] ?: emptySet()
                                selected = selected + (qi to (if (on) cur - opt.label else cur + opt.label))
                            }
                        },
                        label = { Text(opt.label) },
                    )
                    if (opt.description.isNotBlank()) {
                        Text(opt.description, style = MaterialTheme.typography.bodySmall)
                    }
                }
                if (prompt.customAllowed && qi !in showCustom) {
                    TextButton(onClick = { showCustom = showCustom + qi }) { Text("Custom answer") }
                }
                if (qi in showCustom) {
                    OutlinedTextField(
                        value = customs[qi] ?: "",
                        onValueChange = { customs = customs + (qi to it) },
                        label = { Text("Custom") },
                        modifier = Modifier.fillMaxWidth(),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text),
                    )
                }
            }
            if (!aloneSingle) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = {
                            onSubmit(item.questions.mapIndexed { qi, _ ->
                                val sel = selected[qi]?.toList() ?: emptyList()
                                val custom = customs[qi]?.takeIf { it.isNotBlank() }?.let { listOf(it) } ?: emptyList()
                                sel + custom
                            })
                        },
                        enabled = item.questions.indices.any { qi ->
                            (selected[qi]?.isNotEmpty() == true) || customs[qi]?.isNotBlank() == true
                        },
                    ) { Text("Done") }
                    TextButton(onClick = onCancel) { Text("Cancel") }
                }
            } else {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (showCustom.isNotEmpty()) {
                        Button(
                            onClick = {
                                onSubmit(listOf(listOf(customs[showCustom.first()] ?: "")))
                            },
                            enabled = customs[showCustom.first()]?.isNotBlank() == true,
                        ) { Text("Send custom") }
                    }
                    TextButton(onClick = onCancel) { Text("Cancel") }
                }
            }
        }
    }
}

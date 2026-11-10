package dev.opencode.remote.chat

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import dev.opencode.remote.domain.McpServerInfo

/** H10 (P2 scope): per-session totals + context meter. Weekly aggregation deferred to P4/Room. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StatsSheet(
    tokensIn: Long,
    tokensOut: Long,
    cost: Double,
    contextLimit: Long,
    modelLabel: String,
) {
    var open by remember { mutableStateOf(false) }
    TextButton(onClick = { open = true }) {
        Text(
            "${fmtK(tokensIn + tokensOut)} · $${"%.4f".format(cost)}",
            style = MaterialTheme.typography.bodySmall,
        )
    }
    if (open) {
        ModalBottomSheet(onDismissRequest = { open = false }) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Session usage", style = MaterialTheme.typography.titleMedium)
                StatRow("Model", modelLabel)
                StatRow("Input tokens", fmtN(tokensIn))
                StatRow("Output tokens", fmtN(tokensOut))
                StatRow("Cost", "$" + "%.4f".format(cost))
                if (contextLimit > 0) {
                    val used = tokensIn + tokensOut
                    val frac = (used.toDouble() / contextLimit).coerceIn(0.0, 1.0)
                    Text("Context ${fmtK(used)} / ${fmtK(contextLimit)} (${(frac * 100).toInt()}%)")
                    LinearProgressIndicator(progress = { frac.toFloat() }, modifier = Modifier.fillMaxWidth())
                } else {
                    Text("Context limit unknown for this model", style = MaterialTheme.typography.bodySmall)
                }
                Text(
                    "Weekly totals need local history — ships with P4.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.outline,
                )
            }
        }
    }
}

private fun fmtN(n: Long): String = "%,d".format(n)

private fun fmtK(n: Long): String = when {
    n >= 1_000_000 -> "%.1fM".format(n / 1_000_000.0)
    n >= 1_000 -> "%.1fk".format(n / 1_000.0)
    else -> "$n"
}

@Composable
private fun StatRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.bodyMedium)
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}

/** H6 (P2 scope): connectors view — MCP server statuses, toggles deferred to P5. */
@Composable
fun ConnectorsScreen(servers: List<McpServerInfo>) {
    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Connectors", style = MaterialTheme.typography.headlineMedium)
        if (servers.isEmpty()) {
            Text("No MCP servers reported by this server.")
        }
        servers.forEach { s ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(s.name, style = MaterialTheme.typography.bodyLarge)
                Text(s.status, style = MaterialTheme.typography.bodySmall)
            }
        }
        Text(
            "Enabling/disabling servers ships with the browser phase (P5).",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.outline,
        )
    }
}

package dev.opencode.remote.chat

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dev.opencode.remote.domain.ChatMessage
import dev.opencode.remote.domain.ChatPart
import dev.opencode.remote.domain.Role

/** H1: thread + composer. Markdown lib in P2 — code fences render monospace for now (spec). */
@Composable
fun ChatScreen(
    sessionId: String,
    onBack: () -> Unit,
    vm: ChatViewModel = hiltViewModel(),
) {
    val state by vm.state.collectAsStateWithLifecycle()
    val perms by vm.sessionPermissions.collectAsStateWithLifecycle(initialValue = emptyList())
    val quests by vm.sessionQuestions.collectAsStateWithLifecycle(initialValue = emptyList())
    LaunchedEffect(sessionId) { vm.open(sessionId) }
    val listState = rememberLazyListState()

    LaunchedEffect(state.messages.size, state.streamingText.values.sumOf { it.length }) {
        if (state.messages.isNotEmpty()) listState.animateScrollToItem(state.messages.size - 1)
    }

    Scaffold(
        modifier = Modifier.fillMaxSize(),
        topBar = {
            Row(
                Modifier.statusBarsPadding().fillMaxWidth().padding(8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedButton(onClick = onBack) { Text("‹") }
                Text(
                    if (state.busy) "working…" else "idle",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.tertiary,
                )
                StatsSheet(
                    tokensIn = state.sessionTokensIn,
                    tokensOut = state.sessionTokensOut,
                    cost = state.sessionCost,
                    contextLimit = state.contextLimit,
                    modelLabel = state.modelID ?: state.agent,
                )
                if (state.busy) OutlinedButton(onClick = vm::abort) { Text("Stop") }
            }
        },
        bottomBar = {
            Column(Modifier.fillMaxWidth().navigationBarsPadding().imePadding()) {
                AgentChipsRow(
                    agents = state.agents,
                    selected = state.agent,
                    onSelect = vm::setAgent,
                )
                Row(
                    Modifier.fillMaxWidth().padding(horizontal = 8.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    ModelSelector(
                        providers = state.providers,
                        selectedProvider = state.modelProviderID,
                        selectedModel = state.modelID,
                        selectedVariant = state.variant,
                        onSelect = vm::setModel,
                    )
                    FilterChip(
                        selected = state.websearchOn,
                        onClick = { vm.setWebsearch(!state.websearchOn) },
                        label = { Text("web") },
                    )
                    FilterChip(
                        selected = state.memoryOn,
                        onClick = { vm.setMemory(!state.memoryOn) },
                        label = { Text("mem") },
                    )
                }
                CommandSuggestions(
                    suggestions = vm.commandSuggestions(),
                    onPick = vm::acceptCommand,
                )
                var attachOpen by remember { mutableStateOf(false) }
                StagedChips(staged = state.staged, onRemove = vm::unstageAttachment)
                if (attachOpen) {
                    AttachSheet(onDismiss = { attachOpen = false }, onStage = vm::stageAttachment)
                }
                Row(
                    Modifier.fillMaxWidth().padding(8.dp),
                    verticalAlignment = Alignment.Bottom,
                ) {
                OutlinedButton(onClick = { attachOpen = true }) { Text("+") }
                DictationButton(onStart = vm::startDictation, onText = {
                    // First chunk after start establishes the segment; VM handles replace-vs-append.
                    vm.dictationText(it)
                })
                OutlinedTextField(
                    value = state.input,
                    onValueChange = vm::setInput,
                    label = { Text("Message") },
                    modifier = Modifier.weight(1f),
                    maxLines = 5,
                    enabled = !state.offline,
                )
                Button(
                    onClick = vm::send,
                    enabled = (state.input.isNotBlank() || state.staged.isNotEmpty()) && !state.busy && !state.offline,
                    modifier = Modifier.padding(start = 8.dp),
                ) {
                    Text(if (state.busy) "…" else "➤")
                }
                }
            }
        }
    ) { inner ->
        Column(Modifier.padding(inner).fillMaxSize()) {
            if (state.offline) {
                Text(
                    "Offline — cached thread, read-only.",
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(8.dp),
                )
            }
            state.error?.let { err ->
                Card(
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
                    modifier = Modifier.fillMaxWidth().padding(8.dp),
                ) {
                    Row(
                        Modifier.padding(12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(err.take(200), modifier = Modifier.weight(1f))
                        OutlinedButton(onClick = vm::retry) { Text("Retry") }
                    }
                }
            }
            LazyColumn(
                state = listState,
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(state.messages, key = { it.id }) { msg ->
                    MessageBubble(msg)
                }
                if (state.streamingText.isNotEmpty()) {
                    item {
                        Card(
                            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                        ) {
                            MarkdownText(
                                state.streamingText.values.joinToString(""),
                                modifier = Modifier.padding(12.dp),
                            )
                        }
                    }
                }
                items(perms, key = { "perm-" + it.id }) { perm ->
                    PermissionCard(perm, onReply = { kind -> vm.replyPermission(perm.id, kind) })
                }
                items(quests, key = { "quest-" + it.id }) { quest ->
                    QuestionCard(
                        quest,
                        onSubmit = { answers -> vm.answerQuestion(quest.id, answers) },
                        onCancel = { vm.cancelQuestion(quest.id) },
                    )
                }
            }
        }
    }
}

@Composable
private fun MessageBubble(msg: ChatMessage) {
    val mine = msg.role == Role.USER
    Box(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
        contentAlignment = if (mine) Alignment.CenterEnd else Alignment.CenterStart,
    ) {
        Card(
            colors = CardDefaults.cardColors(
                containerColor = if (mine) MaterialTheme.colorScheme.primaryContainer
                else MaterialTheme.colorScheme.surfaceVariant,
            ),
            modifier = Modifier.fillMaxWidth(if (mine) 0.85f else 0.95f),
        ) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                if (msg.optimistic) {
                    Text("sending…", style = MaterialTheme.typography.labelSmall)
                }
                if (msg.parts.isEmpty() && msg.error != null) {
                    Text(
                        "error: ${msg.error}",
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                } else {
                    msg.parts.forEach { part -> PartView(part) }
                    msg.error?.let { Text("error: $it", color = MaterialTheme.colorScheme.error) }
                }
            }
        }
    }
}

@Composable
private fun PartView(part: ChatPart) {
    when (part) {
        is ChatPart.Text -> MarkdownText(part.text)
        is ChatPart.Reasoning -> Text(
            "💭 ${part.text.take(300)}",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.outline,
        )
        is ChatPart.Tool -> Text(
            "🔧 ${part.tool} [${part.state}]",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.secondary,
        )
        is ChatPart.StepStart -> Unit
        is ChatPart.StepFinish -> Text(
            "${part.input}↑ ${part.output}↓ · $${"%.4f".format(part.cost)}",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.outline,
        )
        is ChatPart.File -> FilePartView(part.mime, part.filename, part.url)
        is ChatPart.Patch -> Text("🩹 patch: ${part.files} files")
        is ChatPart.Agent -> Text("🤖 agent: ${part.name}")
        is ChatPart.Retry -> Text("↻ retry ${part.attempt}: ${part.error.take(120)}")
        is ChatPart.Compaction -> Text("🗜 ${part.text.take(160)}")
        is ChatPart.Subtask -> Text("📋 subtask: ${part.prompt.take(160)}")
        is ChatPart.Unknown -> Text("[${part.type}]", color = MaterialTheme.colorScheme.outline)
    }
}

/** Plain text with monospace code fences (P1 stopgap; mikepenz renderer in P2). */
@Composable
private fun MonoText(text: String) {
    // Split ``` fences: odd segments render monospace.
    val segments = text.split("```")
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        segments.forEachIndexed { i, seg ->
            if (i % 2 == 1) {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
                    Text(
                        seg.trimStart('\n').trimEnd(),
                        fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace,
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(8.dp),
                    )
                }
            } else if (seg.isNotBlank()) {
                Text(seg.trim(), style = MaterialTheme.typography.bodyLarge)
            }
        }
    }
}

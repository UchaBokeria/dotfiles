package dev.opencode.remote.chat

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import com.mikepenz.markdown.compose.Markdown
import com.mikepenz.markdown.compose.components.markdownComponents
import com.mikepenz.markdown.compose.elements.highlightedCodeFence
import com.mikepenz.markdown.m3.markdownColor
import com.mikepenz.markdown.m3.markdownTypography

/**
 * Agent text renderer (P2): full markdown (tables, lists, links, GFM alerts) +
 * highlighted code fences with language header + copy button (spec §3).
 * 0.41.0 pinned: last line readable by Kotlin 2.2 (stdlib 2.3.21); no streaming
 * state API in this line, so updates re-parse with retained state (no flicker).
 */
@Composable
fun MarkdownText(text: String, modifier: Modifier = Modifier) {
    val components = remember {
        markdownComponents(codeFence = highlightedCodeFence)
    }
    Markdown(
        content = text,
        colors = markdownColor(),
        typography = markdownTypography(),
        components = components,
        retainState = true,
        modifier = modifier,
    )
}

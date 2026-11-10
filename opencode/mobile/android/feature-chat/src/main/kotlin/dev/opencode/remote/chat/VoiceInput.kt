package dev.opencode.remote.chat

import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import java.util.Locale

/** H4-dictation: mic button → platform SpeechRecognizer, partials appended to composer. */
@Composable
fun DictationButton(onStart: () -> Unit, onText: (String) -> Unit) {
    val ctx = LocalContext.current
    var listening by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf<String?>(null) }
    val recognizer = remember {
        if (SpeechRecognizer.isRecognitionAvailable(ctx)) SpeechRecognizer.createSpeechRecognizer(ctx) else null
    }
    DisposableEffect(Unit) {
        onDispose { recognizer?.destroy() }
    }
    val requestPerm = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (!granted) status = "mic denied — enable in Settings"
    }
    OutlinedButton(onClick = {
        if (recognizer == null) {
            status = "speech recognition unavailable"
            return@OutlinedButton
        }
        if (listening) {
            recognizer.stopListening()
            return@OutlinedButton
        }
        requestPerm.launch(android.Manifest.permission.RECORD_AUDIO)
        onStart()
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        }
        recognizer.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(p: Bundle?) { listening = true }
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(v: Float) {}
            override fun onBufferReceived(b: ByteArray?) {}
            override fun onEndOfSpeech() { listening = false }
            override fun onError(e: Int) {
                listening = false
                status = when (e) {
                    SpeechRecognizer.ERROR_NO_MATCH -> "no speech heard"
                    SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "timed out"
                    SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "mic denied — enable in Settings"
                    else -> "dictation error $e"
                }
            }

            override fun onResults(r: Bundle?) {
                listening = false
                r?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull()?.let { onText(it) }
            }

            override fun onPartialResults(r: Bundle?) {
                r?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull()?.let { onText(it) }
            }

            override fun onEvent(type: Int, p: Bundle?) {}
        })
        recognizer.startListening(intent)
    }) {
        Text(if (listening) "●" else "🎤")
    }
    status?.let { Text(it, style = MaterialTheme.typography.labelSmall) }
}

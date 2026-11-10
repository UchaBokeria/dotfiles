package dev.opencode.remote

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import dagger.hilt.android.AndroidEntryPoint
import dev.opencode.remote.domain.ThemeMode
import dev.opencode.remote.domain.ThemeRepository
import dev.opencode.remote.theme.OpencodeTheme
import javax.inject.Inject
import kotlinx.coroutines.flow.combine

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject
    lateinit var themes: ThemeRepository

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge() // forced posture (doc 05 §5, doc 08 §4)
        setContent {
            val themeState by combine(themes.schemeId, themes.mode) { a, b -> a to b }
                .collectAsState(initial = "neon-dark" to ThemeMode.DARK)
            val (schemeId, mode) = themeState
            val scheme = themes.builtinSchemes().firstOrNull { it.id == schemeId }
                ?: dev.opencode.remote.domain.ThemeScheme.NEON_DARK
            OpencodeTheme(scheme = scheme, mode = mode) {
                Surface(Modifier.fillMaxSize()) {
                    AppNav()
                }
            }
        }
    }
}

package dev.opencode.remote.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.remember
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.sp
import dev.opencode.remote.domain.ThemeMode
import dev.opencode.remote.domain.ThemeScheme

/** Extra neon tokens beyond M3 (glow + accent). Engine reads ThemeScheme (T1). */
data class NeonTokens(
    val glow: Color,
    val accentCyan: Color = Color(0xFF00F0FF),
    val accentMagenta: Color = Color(0xFFB537F2),
    val accentAcid: Color = Color(0xFF39FF14),
)

val LocalNeon = compositionLocalOf {
    NeonTokens(glow = Color(0xFF00F0FF))
}

private fun ThemeScheme.toDarkScheme() = darkColorScheme(
    primary = Color(primary),
    secondary = Color(secondary),
    tertiary = Color(tertiary),
    background = Color(background),
    surface = Color(surface),
    error = Color(error),
    onPrimary = Color.Black,
    onSecondary = Color.Black,
    onBackground = Color(0xFFE8E6F5),
    onSurface = Color(0xFFE8E6F5),
)

private fun ThemeScheme.toLightScheme() = lightColorScheme(
    primary = Color(primary),
    secondary = Color(secondary),
    tertiary = Color(tertiary),
    background = Color(background),
    surface = Color(surface),
    error = Color(error),
    onPrimary = Color.White,
    onBackground = Color(0xFF14121F),
    onSurface = Color(0xFF14121F),
)

/**
 * App theme entry (T1/T2). All feature screens use this — never raw colors.
 * Reduced motion / font scale applied by callers via settings (doc 13).
 */
@Composable
fun OpencodeTheme(
    scheme: ThemeScheme = ThemeScheme.NEON_DARK,
    mode: ThemeMode = ThemeMode.DARK,
    useDarkTheme: Boolean = when (mode) {
        ThemeMode.DARK -> true
        ThemeMode.LIGHT -> false
        ThemeMode.SYSTEM -> androidx.compose.foundation.isSystemInDarkTheme()
    },
    content: @Composable () -> Unit,
) {
    val colorScheme = remember(scheme, useDarkTheme) {
        if (useDarkTheme) scheme.toDarkScheme() else scheme.toLightScheme()
    }
    val neon = remember(scheme) {
        NeonTokens(glow = if (scheme.glowEnabled) Color(scheme.primary) else Color.Transparent)
    }
    CompositionLocalProvider(LocalNeon provides neon) {
        MaterialTheme(
            colorScheme = colorScheme,
            typography = MaterialTheme.typography.copy(
                bodyLarge = MaterialTheme.typography.bodyLarge.copy(
                    fontSize = MaterialTheme.typography.bodyLarge.fontSize * scheme.fontScale,
                    lineHeight = MaterialTheme.typography.bodyLarge.lineHeight * scheme.fontScale,
                ),
            ),
            content = content,
        )
    }
}

private operator fun androidx.compose.ui.unit.TextUnit.times(f: Float) =
    (this.value * f).sp

package dev.opencode.remote.domain

import kotlinx.coroutines.flow.Flow

/** Theme mode (T2). */
@kotlinx.serialization.Serializable
enum class ThemeMode { DARK, LIGHT, SYSTEM }

/** A theme scheme: token set identified by id (T1/T3). Built-ins + user JSON later. */
data class ThemeScheme(
    val id: String,
    val name: String,
    // M3 core tokens as ARGB longs; full ramp in :feature-theme, engine reads this.
    val primary: Long,
    val secondary: Long,
    val tertiary: Long,
    val background: Long,
    val surface: Long,
    val error: Long,
    val glowEnabled: Boolean = true,
    val fontScale: Float = 1f,
) {
    companion object {
        // Default dark cyberpunk neon (doc 08 §2 — verbatim).
        val NEON_DARK = ThemeScheme(
            id = "neon-dark",
            name = "Neon Dark",
            primary = 0xFF00F0FF,
            secondary = 0xFFB537F2,
            tertiary = 0xFF39FF14,
            background = 0xFF05010F,
            surface = 0xFF0B0620,
            error = 0xFFFF2A6D,
        )
        val NEON_LIGHT = ThemeScheme(
            id = "neon-light",
            name = "Neon Light",
            primary = 0xFF007A87,
            secondary = 0xFF7B2FBF,
            tertiary = 0xFF1FA806,
            background = 0xFFF6F2FF,
            surface = 0xFFFFFFFF,
            error = 0xFFBA1A1A,
        )
    }
}

interface ThemeRepository {
    val schemeId: Flow<String>
    val mode: Flow<ThemeMode>
    suspend fun setScheme(id: String)
    suspend fun setMode(mode: ThemeMode)
    fun builtinSchemes(): List<ThemeScheme>
}

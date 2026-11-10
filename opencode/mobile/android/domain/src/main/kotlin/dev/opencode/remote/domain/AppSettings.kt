package dev.opencode.remote.domain

import kotlinx.coroutines.flow.Flow

/** App settings, DataStore-backed (X1, doc 13 — v1 schema; groups grow without migration breaks). */
@kotlinx.serialization.Serializable
data class AppSettings(
    // Connection (S3)
    val connectTimeoutMs: Long = 15_000,
    val readTimeoutMs: Long = 60_000,
    val sseBackoffBaseMs: Long = 1_000,
    val sseBackoffMaxMs: Long = 30_000,
    // Sessions (C2)
    val defaultTemporary: Boolean = false,
    val tempAutoPurgeDays: Int = 7,
    val confirmDelete: Boolean = true,
    // Chat (H1/H3/H5)
    val websearchDefaultOn: Boolean = true,
    val memoryDefaultOn: Boolean = true,
    val enterToSend: Boolean = false,
    val haptics: Boolean = true,
    // Agent (H7/H8/H9)
    val defaultAgent: String = "build",
    val permissionModeDefault: String = "unrestricted",
    // Theme (T1–T3)
    val themeSchemeId: String = "neon-dark",
    val themeMode: ThemeMode = ThemeMode.DARK,
    // Attachments (H2)
    val imageQuality: Int = 2, // 0=off(original) 1=light 2=medium
    val maxImageDim: Int = 1600,
    val maxFileBytes: Long = 10_000_000,
    // Onboarding
    val onboardingDone: Boolean = false,
)

interface SettingsRepository {
    val settings: Flow<AppSettings>
    suspend fun update(transform: (AppSettings) -> AppSettings)
    suspend fun exportJson(): String
    suspend fun importJson(json: String): Result<Unit>
}

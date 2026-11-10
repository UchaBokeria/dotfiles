package dev.opencode.remote.domain

import kotlinx.serialization.Serializable

/** A server connection profile (S1). Password lives in EncryptedSharedPreferences, never here. */
@Serializable
data class ServerProfile(
    val id: String,
    val name: String,
    val baseUrl: String,
    val username: String = "opencode",
    val defaultDirectory: String? = null,
    val serverVersion: String? = null,
    val lastUsedAt: Long = 0,
)

/** Result of GET /global/health (S2). */
@Serializable
data class ServerHealth(
    val healthy: Boolean,
    val version: String,
)

/** Connection state machine for a profile. */
sealed interface ConnectionState {
    data object Disconnected : ConnectionState
    data object Connecting : ConnectionState
    data class Connected(val health: ServerHealth) : ConnectionState
    data class Failed(val reason: String) : ConnectionState
}

package dev.opencode.remote.domain

import kotlinx.coroutines.flow.Flow

/** Server profile + credential storage. Secrets never leave :data encrypted. */
interface ServerRepository {
    val profiles: Flow<List<ServerProfile>>
    val activeProfileId: Flow<String?>
    suspend fun upsertProfile(profile: ServerProfile, password: String?)
    suspend fun deleteProfile(id: String)
    suspend fun setActiveProfile(id: String?)
    suspend fun getPassword(profileId: String): String?
    suspend fun checkHealth(profile: ServerProfile): Result<ServerHealth>
}

package dev.opencode.remote.data.repo

import dev.opencode.remote.data.api.ApiFactory
import dev.opencode.remote.domain.ServerRepository
import dev.opencode.remote.domain.SettingsRepository
import javax.inject.Inject
import kotlinx.coroutines.flow.first

/** Active-profile-bound API for repos (auth + directory + timeouts in one place). */
class ActiveApi @Inject constructor(
    private val servers: ServerRepository,
    private val settingsRepo: SettingsRepository,
) {
    suspend fun get(): ApiFactory.BoundApi? {
        val id = servers.activeProfileId.first() ?: return null
        val profile = servers.profiles.first().firstOrNull { it.id == id } ?: return null
        val settings = settingsRepo.settings.first()
        return ApiFactory.bound(profile, servers.getPassword(profile.id), settings)
    }
}

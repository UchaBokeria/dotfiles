package dev.opencode.remote.data.store

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import dev.opencode.remote.domain.AppSettings
import dev.opencode.remote.domain.Project
import dev.opencode.remote.domain.ProjectRepository
import dev.opencode.remote.domain.ServerProfile
import dev.opencode.remote.domain.ServerRepository
import dev.opencode.remote.domain.SettingsRepository
import dev.opencode.remote.domain.ThemeMode
import dev.opencode.remote.domain.ThemeRepository
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.update
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json

private const val PREFS = "opencode_remote"
private const val KEY_PROFILES = "profiles_json"
private const val KEY_ACTIVE = "active_profile"
private const val KEY_SETTINGS = "settings_json"
private const val KEY_THEME_SCHEME = "theme_scheme"
private const val KEY_THEME_MODE = "theme_mode"
private const val KEY_PROJECTS = "projects_json"
private const val KEY_LINKS = "session_links_json"
private const val PASS_PREFIX = "profile_pass_"

private val plainJson = Json { ignoreUnknownKeys = true }

/**
 * Encrypted profile + settings store (grapeot SettingsManager pattern, doc 14 §4).
 * Passwords under per-profile keys; export strips secrets (X1).
 */
@Singleton
class SecureStore @Inject constructor(@ApplicationContext context: Context) :
    ServerRepository, SettingsRepository, ThemeRepository, ProjectRepository {

    private val prefs: SharedPreferences by lazy {
        EncryptedSharedPreferences.create(
            context,
            PREFS,
            MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    private val _profiles = MutableStateFlow(loadProfiles())
    override val profiles: Flow<List<ServerProfile>> = _profiles.asStateFlow()

    private val _activeId = MutableStateFlow(prefsString(KEY_ACTIVE))
    override val activeProfileId: Flow<String?> = _activeId.asStateFlow()

    private val _settings = MutableStateFlow(loadSettings())
    override val settings: Flow<AppSettings> = _settings.asStateFlow()

    // --- ServerRepository ---
    override suspend fun upsertProfile(profile: ServerProfile, password: String?) {
        _profiles.update { list ->
            val now = System.currentTimeMillis()
            val stamped = profile.copy(lastUsedAt = now)
            if (list.any { it.id == profile.id }) list.map { if (it.id == profile.id) stamped else it }
            else list + stamped
        }
        persistProfiles()
        if (password != null) prefs.edit().putString(PASS_PREFIX + profile.id, password).apply()
    }

    override suspend fun deleteProfile(id: String) {
        _profiles.update { it.filterNot { p -> p.id == id } }
        persistProfiles()
        prefs.edit().remove(PASS_PREFIX + id).apply()
        if (_activeId.value == id) setActiveProfile(null)
    }

    override suspend fun setActiveProfile(id: String?) {
        _activeId.value = id
        prefs.edit().putString(KEY_ACTIVE, id).apply()
    }

    override suspend fun getPassword(profileId: String): String? =
        prefs.getString(PASS_PREFIX + profileId, null)

    override suspend fun checkHealth(profile: ServerProfile): Result<dev.opencode.remote.domain.ServerHealth> =
        runCatching {
            val settings = _settings.value
            val api = dev.opencode.remote.data.api.ApiFactory.api(profile, getPassword(profile.id), settings)
            val h = api.health()
            dev.opencode.remote.domain.ServerHealth(h.healthy, h.version)
        }

    // --- SettingsRepository ---
    override suspend fun update(transform: (AppSettings) -> AppSettings) {
        _settings.update(transform)
        prefs.edit().putString(KEY_SETTINGS, plainJson.encodeToString(AppSettings.serializer(), _settings.value)).apply()
    }

    override suspend fun exportJson(): String =
        plainJson.encodeToString(AppSettings.serializer(), _settings.value)

    override suspend fun importJson(json: String): Result<Unit> = runCatching {
        val parsed = plainJson.decodeFromString(AppSettings.serializer(), json)
        _settings.value = parsed
        prefs.edit().putString(KEY_SETTINGS, json).apply()
    }

    // --- ThemeRepository ---
    override val schemeId: Flow<String> = settings.map { it.themeSchemeId }
    override val mode: Flow<ThemeMode> = settings.map { it.themeMode }

    override suspend fun setScheme(id: String) = update { it.copy(themeSchemeId = id) }
    override suspend fun setMode(mode: ThemeMode) = update { it.copy(themeMode = mode) }
    override fun builtinSchemes() = listOf(
        dev.opencode.remote.domain.ThemeScheme.NEON_DARK,
        dev.opencode.remote.domain.ThemeScheme.NEON_LIGHT,
    )

    // --- ProjectRepository (D1; Room migration in P4) ---
    private val _projects = MutableStateFlow(loadProjects())
    override val projects: Flow<List<Project>> = _projects.asStateFlow()

    private val _links = MutableStateFlow(loadLinks())
    override val sessionLinks: Flow<Map<String, String>> = _links.asStateFlow()

    override suspend fun upsert(project: Project) {
        _projects.update { list ->
            if (list.any { it.id == project.id }) list.map { if (it.id == project.id) project else it }
            else list + project
        }
        prefs.edit().putString(
            KEY_PROJECTS,
            plainJson.encodeToString(ListSerializer(Project.serializer()), _projects.value),
        ).apply()
    }

    override suspend fun delete(id: String) {
        _projects.update { it.filterNot { p -> p.id == id } }
        prefs.edit().putString(
            KEY_PROJECTS,
            plainJson.encodeToString(ListSerializer(Project.serializer()), _projects.value),
        ).apply()
        _links.update { it.filterValues { pid -> pid != id } }
        persistLinks()
    }

    override suspend fun linkSession(sessionId: String, projectId: String?) {
        _links.update {
            if (projectId == null) it - sessionId else it + (sessionId to projectId)
        }
        persistLinks()
    }

    private fun loadProjects(): List<Project> = try {
        prefsString(KEY_PROJECTS)?.let {
            plainJson.decodeFromString(ListSerializer(Project.serializer()), it)
        } ?: emptyList()
    } catch (_: Exception) {
        emptyList()
    }

    private fun loadLinks(): Map<String, String> = try {
        prefsString(KEY_LINKS)?.let { raw ->
            plainJson.decodeFromString(
                ListSerializer(dev.opencode.remote.domain.SessionLink.serializer()), raw,
            ).associate { it.sessionId to it.projectId }
        } ?: emptyMap()
    } catch (_: Exception) {
        emptyMap()
    }

    private fun persistLinks() {
        val rows = _links.value.map { (s, p) -> dev.opencode.remote.domain.SessionLink(s, p) }
        prefs.edit().putString(
            KEY_LINKS,
            plainJson.encodeToString(ListSerializer(dev.opencode.remote.domain.SessionLink.serializer()), rows),
        ).apply()
    }

    // --- internals ---
    private fun prefsString(key: String): String? = try {
        prefs.getString(key, null)
    } catch (_: Exception) {
        null
    }

    private fun loadProfiles(): List<ServerProfile> = try {
        prefsString(KEY_PROFILES)?.let {
            plainJson.decodeFromString(ListSerializer(ServerProfile.serializer()), it)
        } ?: emptyList()
    } catch (_: Exception) {
        emptyList()
    }

    private fun persistProfiles() {
        prefs.edit().putString(
            KEY_PROFILES,
            plainJson.encodeToString(ListSerializer(ServerProfile.serializer()), _profiles.value),
        ).apply()
    }

    private fun loadSettings(): AppSettings = try {
        prefsString(KEY_SETTINGS)?.let {
            plainJson.decodeFromString(AppSettings.serializer(), it)
        } ?: AppSettings(
            themeSchemeId = prefsString(KEY_THEME_SCHEME) ?: "neon-dark",
            themeMode = runCatching { ThemeMode.valueOf(prefsString(KEY_THEME_MODE) ?: "DARK") }
                .getOrDefault(ThemeMode.DARK),
        )
    } catch (_: Exception) {
        AppSettings()
    }
}

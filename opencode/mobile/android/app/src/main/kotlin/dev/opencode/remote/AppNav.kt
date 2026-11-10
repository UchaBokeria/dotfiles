package dev.opencode.remote

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.NavType
import androidx.navigation.navArgument
import dev.opencode.remote.chat.ChatScreen
import dev.opencode.remote.chat.ConnectorsRoute
import dev.opencode.remote.chat.ProjectsScreen
import dev.opencode.remote.chat.SessionsScreen
import dev.opencode.remote.servers.ServersScreen
import dev.opencode.remote.settings.SettingsScreen
import dev.opencode.remote.settings.SettingsViewModel

private object Routes {
    const val SERVERS = "servers"
    const val SESSIONS = "sessions"
    const val CHAT = "chat/{sessionId}"
    const val PROJECTS = "projects"
    const val CONNECTORS = "connectors"
    const val ONBOARDING = "onboarding"
    const val SETTINGS = "settings"
}

/** P0 nav: onboarding gate → servers (+ settings). Chat lands in P1. */
@Composable
fun AppNav() {
    val nav = rememberNavController()
    val settingsVm: SettingsViewModel = hiltViewModel()
    val settings by settingsVm.state.collectAsStateWithLifecycle()
    val start = if (settings.onboardingDone) Routes.SERVERS else Routes.ONBOARDING

    Scaffold(
        bottomBar = {
            val entry by nav.currentBackStackEntryAsState()
            if (entry?.destination?.route != Routes.ONBOARDING) {
                NavigationBar {
                    NavigationBarItem(
                        selected = entry?.destination?.route == Routes.SERVERS,
                        onClick = { nav.navigate(Routes.SERVERS) { launchSingleTop = true } },
                        icon = { Text("⌁") },
                        label = { Text("Servers") },
                    )
                    NavigationBarItem(
                        selected = entry?.destination?.route == Routes.SESSIONS,
                        onClick = { nav.navigate(Routes.SESSIONS) { launchSingleTop = true } },
                        icon = { Text("💬") },
                        label = { Text("Sessions") },
                    )
                    NavigationBarItem(
                        selected = entry?.destination?.route == Routes.CONNECTORS,
                        onClick = { nav.navigate(Routes.CONNECTORS) { launchSingleTop = true } },
                        icon = { Text("🔌") },
                        label = { Text("Connect") },
                    )
                    NavigationBarItem(
                        selected = entry?.destination?.route == Routes.SETTINGS,
                        onClick = { nav.navigate(Routes.SETTINGS) { launchSingleTop = true } },
                        icon = { Text("⚙") },
                        label = { Text("Settings") },
                    )
                }
            }
        },
    ) { inner ->
        NavHost(nav, startDestination = start, Modifier.padding(inner)) {
            composable(Routes.ONBOARDING) {
                OnboardingScreen(onDone = {
                    settingsVm.setOnboardingDone()
                    nav.navigate(Routes.SERVERS) { popUpTo(Routes.ONBOARDING) { inclusive = true } }
                })
            }
            composable(Routes.SERVERS) { ServersScreen() }
            composable(Routes.SESSIONS) {
                SessionsScreen(
                    onOpenChat = { id -> nav.navigate("chat/$id") },
                    onOpenProjects = { nav.navigate(Routes.PROJECTS) },
                )
            }
            composable(Routes.PROJECTS) { ProjectsScreen() }
            composable(Routes.CONNECTORS) { ConnectorsRoute() }
            composable(
                Routes.CHAT,
                arguments = listOf(navArgument("sessionId") { type = NavType.StringType }),
            ) { backStack ->
                val id = backStack.arguments?.getString("sessionId") ?: return@composable
                ChatScreen(sessionId = id, onBack = { nav.popBackStack() })
            }
            composable(Routes.SETTINGS) { SettingsScreen() }
        }
    }
}

/** X5 skeleton: Welcome → Servers → Theme → Permissions → Ready (full aggressive perms in P0b). */
@Composable
private fun OnboardingScreen(onDone: () -> Unit) {
    Column(
        Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("opencode", style = MaterialTheme.typography.displayMedium, color = MaterialTheme.colorScheme.primary)
        Text("Your PC's agent, in your pocket. No cloud, no Firebase — your hardware.")
        Text("1. Add your server (opencode.uchabokeria.space).")
        Text("2. Pick the neon. More schemes later.")
        Text("3. Grant permissions aggressively — notifications, mic, camera, battery.")
        Text("4. Chat from anywhere (P1).")
        Button(onClick = onDone) { Text("Get started") }
    }
}

pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
    versionCatalogs {
        // default `libs` catalog auto-loads from gradle/libs.versions.toml
    }
}
rootProject.name = "opencode-remote"
include(":app", ":domain", ":data", ":feature-theme", ":feature-servers", ":feature-settings", ":feature-chat")

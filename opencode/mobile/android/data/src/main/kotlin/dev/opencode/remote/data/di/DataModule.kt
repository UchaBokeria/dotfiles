package dev.opencode.remote.data.di

import android.content.Context
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import dev.opencode.remote.data.store.SecureStore
import dev.opencode.remote.domain.ServerRepository
import dev.opencode.remote.domain.SettingsRepository
import dev.opencode.remote.domain.ThemeRepository
import dev.opencode.remote.domain.ProjectRepository
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class DataModule {
    @Binds
    @Singleton
    abstract fun bindServerRepository(store: SecureStore): ServerRepository

    @Binds
    @Singleton
    abstract fun bindSettingsRepository(store: SecureStore): SettingsRepository

    @Binds
    @Singleton
    abstract fun bindThemeRepository(store: SecureStore): ThemeRepository

    @Binds
    @Singleton
    abstract fun bindProjectRepository(store: SecureStore): ProjectRepository
}

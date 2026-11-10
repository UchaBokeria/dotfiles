package dev.opencode.remote.data.di

import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import dev.opencode.remote.data.repo.ChatRepositoryImpl
import dev.opencode.remote.data.repo.PermissionRepositoryImpl
import dev.opencode.remote.data.repo.QuestionRepositoryImpl
import dev.opencode.remote.data.repo.CatalogRepositoryImpl
import dev.opencode.remote.domain.ChatRepository
import dev.opencode.remote.domain.PermissionRepository
import dev.opencode.remote.domain.QuestionRepository
import dev.opencode.remote.domain.CatalogRepository
import dev.opencode.remote.domain.ServerRepository
import javax.inject.Singleton
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit

@Module
@InstallIn(SingletonComponent::class)
object ChatModule {

    @Provides
    @Singleton
    fun provideHttpClient(): OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()

    @Provides
    @Singleton
    fun provideChatRepository(impl: ChatRepositoryImpl): ChatRepository = impl

    @Provides
    @Singleton
    fun providePermissionRepository(impl: PermissionRepositoryImpl): PermissionRepository = impl

    @Provides
    @Singleton
    fun provideQuestionRepository(impl: QuestionRepositoryImpl): QuestionRepository = impl

    @Provides
    @Singleton
    fun provideCatalogRepository(impl: CatalogRepositoryImpl): CatalogRepository = impl
}

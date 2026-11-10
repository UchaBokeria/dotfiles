package dev.opencode.remote.data.repo;

import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.Provider;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import dev.opencode.remote.domain.PermissionRepository;
import dev.opencode.remote.domain.QuestionRepository;
import dev.opencode.remote.domain.ServerRepository;
import javax.annotation.processing.Generated;
import okhttp3.OkHttpClient;

@ScopeMetadata("javax.inject.Singleton")
@QualifierMetadata
@DaggerGenerated
@Generated(
    value = "dagger.internal.codegen.ComponentProcessor",
    comments = "https://dagger.dev"
)
@SuppressWarnings({
    "unchecked",
    "rawtypes",
    "KotlinInternal",
    "KotlinInternalInJava",
    "cast",
    "deprecation",
    "nullness:initialization.field.uninitialized"
})
public final class ChatRepositoryImpl_Factory implements Factory<ChatRepositoryImpl> {
  private final Provider<ServerRepository> serversProvider;

  private final Provider<PermissionRepository> permissionsProvider;

  private final Provider<QuestionRepository> questionsProvider;

  private final Provider<OkHttpClient> httpProvider;

  private ChatRepositoryImpl_Factory(Provider<ServerRepository> serversProvider,
      Provider<PermissionRepository> permissionsProvider,
      Provider<QuestionRepository> questionsProvider, Provider<OkHttpClient> httpProvider) {
    this.serversProvider = serversProvider;
    this.permissionsProvider = permissionsProvider;
    this.questionsProvider = questionsProvider;
    this.httpProvider = httpProvider;
  }

  @Override
  public ChatRepositoryImpl get() {
    return newInstance(serversProvider.get(), permissionsProvider.get(), questionsProvider.get(), httpProvider.get());
  }

  public static ChatRepositoryImpl_Factory create(Provider<ServerRepository> serversProvider,
      Provider<PermissionRepository> permissionsProvider,
      Provider<QuestionRepository> questionsProvider, Provider<OkHttpClient> httpProvider) {
    return new ChatRepositoryImpl_Factory(serversProvider, permissionsProvider, questionsProvider, httpProvider);
  }

  public static ChatRepositoryImpl newInstance(ServerRepository servers,
      PermissionRepository permissions, QuestionRepository questions, OkHttpClient http) {
    return new ChatRepositoryImpl(servers, permissions, questions, http);
  }
}

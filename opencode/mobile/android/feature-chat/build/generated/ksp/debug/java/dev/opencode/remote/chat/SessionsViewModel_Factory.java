package dev.opencode.remote.chat;

import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.Provider;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import dev.opencode.remote.domain.ChatRepository;
import dev.opencode.remote.domain.ProjectRepository;
import dev.opencode.remote.domain.SettingsRepository;
import javax.annotation.processing.Generated;

@ScopeMetadata
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
public final class SessionsViewModel_Factory implements Factory<SessionsViewModel> {
  private final Provider<ChatRepository> chatProvider;

  private final Provider<SettingsRepository> settingsProvider;

  private final Provider<ProjectRepository> projectsRepoProvider;

  private SessionsViewModel_Factory(Provider<ChatRepository> chatProvider,
      Provider<SettingsRepository> settingsProvider,
      Provider<ProjectRepository> projectsRepoProvider) {
    this.chatProvider = chatProvider;
    this.settingsProvider = settingsProvider;
    this.projectsRepoProvider = projectsRepoProvider;
  }

  @Override
  public SessionsViewModel get() {
    return newInstance(chatProvider.get(), settingsProvider.get(), projectsRepoProvider.get());
  }

  public static SessionsViewModel_Factory create(Provider<ChatRepository> chatProvider,
      Provider<SettingsRepository> settingsProvider,
      Provider<ProjectRepository> projectsRepoProvider) {
    return new SessionsViewModel_Factory(chatProvider, settingsProvider, projectsRepoProvider);
  }

  public static SessionsViewModel newInstance(ChatRepository chat, SettingsRepository settings,
      ProjectRepository projectsRepo) {
    return new SessionsViewModel(chat, settings, projectsRepo);
  }
}

package dev.opencode.remote.chat;

import android.content.Context;
import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.Provider;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import dev.opencode.remote.domain.CatalogRepository;
import dev.opencode.remote.domain.ChatRepository;
import dev.opencode.remote.domain.PermissionRepository;
import dev.opencode.remote.domain.ProjectRepository;
import dev.opencode.remote.domain.QuestionRepository;
import dev.opencode.remote.domain.SettingsRepository;
import javax.annotation.processing.Generated;

@ScopeMetadata
@QualifierMetadata("dagger.hilt.android.qualifiers.ApplicationContext")
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
public final class ChatViewModel_Factory implements Factory<ChatViewModel> {
  private final Provider<ChatRepository> chatProvider;

  private final Provider<SettingsRepository> settingsProvider;

  private final Provider<PermissionRepository> permissionsProvider;

  private final Provider<QuestionRepository> questionsProvider;

  private final Provider<CatalogRepository> catalogProvider;

  private final Provider<ProjectRepository> projectsProvider;

  private final Provider<Context> appContextProvider;

  private ChatViewModel_Factory(Provider<ChatRepository> chatProvider,
      Provider<SettingsRepository> settingsProvider,
      Provider<PermissionRepository> permissionsProvider,
      Provider<QuestionRepository> questionsProvider, Provider<CatalogRepository> catalogProvider,
      Provider<ProjectRepository> projectsProvider, Provider<Context> appContextProvider) {
    this.chatProvider = chatProvider;
    this.settingsProvider = settingsProvider;
    this.permissionsProvider = permissionsProvider;
    this.questionsProvider = questionsProvider;
    this.catalogProvider = catalogProvider;
    this.projectsProvider = projectsProvider;
    this.appContextProvider = appContextProvider;
  }

  @Override
  public ChatViewModel get() {
    return newInstance(chatProvider.get(), settingsProvider.get(), permissionsProvider.get(), questionsProvider.get(), catalogProvider.get(), projectsProvider.get(), appContextProvider.get());
  }

  public static ChatViewModel_Factory create(Provider<ChatRepository> chatProvider,
      Provider<SettingsRepository> settingsProvider,
      Provider<PermissionRepository> permissionsProvider,
      Provider<QuestionRepository> questionsProvider, Provider<CatalogRepository> catalogProvider,
      Provider<ProjectRepository> projectsProvider, Provider<Context> appContextProvider) {
    return new ChatViewModel_Factory(chatProvider, settingsProvider, permissionsProvider, questionsProvider, catalogProvider, projectsProvider, appContextProvider);
  }

  public static ChatViewModel newInstance(ChatRepository chat, SettingsRepository settings,
      PermissionRepository permissions, QuestionRepository questions, CatalogRepository catalog,
      ProjectRepository projects, Context appContext) {
    return new ChatViewModel(chat, settings, permissions, questions, catalog, projects, appContext);
  }
}

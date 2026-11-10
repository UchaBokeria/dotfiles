package dev.opencode.remote.data.di;

import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.Preconditions;
import dagger.internal.Provider;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import dev.opencode.remote.data.repo.ChatRepositoryImpl;
import dev.opencode.remote.domain.ChatRepository;
import javax.annotation.processing.Generated;

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
public final class ChatModule_ProvideChatRepositoryFactory implements Factory<ChatRepository> {
  private final Provider<ChatRepositoryImpl> implProvider;

  private ChatModule_ProvideChatRepositoryFactory(Provider<ChatRepositoryImpl> implProvider) {
    this.implProvider = implProvider;
  }

  @Override
  public ChatRepository get() {
    return provideChatRepository(implProvider.get());
  }

  public static ChatModule_ProvideChatRepositoryFactory create(
      Provider<ChatRepositoryImpl> implProvider) {
    return new ChatModule_ProvideChatRepositoryFactory(implProvider);
  }

  public static ChatRepository provideChatRepository(ChatRepositoryImpl impl) {
    return Preconditions.checkNotNullFromProvides(ChatModule.INSTANCE.provideChatRepository(impl));
  }
}

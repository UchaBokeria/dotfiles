package dev.opencode.remote.data.di;

import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.Preconditions;
import dagger.internal.Provider;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import dev.opencode.remote.data.repo.PermissionRepositoryImpl;
import dev.opencode.remote.domain.PermissionRepository;
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
public final class ChatModule_ProvidePermissionRepositoryFactory implements Factory<PermissionRepository> {
  private final Provider<PermissionRepositoryImpl> implProvider;

  private ChatModule_ProvidePermissionRepositoryFactory(
      Provider<PermissionRepositoryImpl> implProvider) {
    this.implProvider = implProvider;
  }

  @Override
  public PermissionRepository get() {
    return providePermissionRepository(implProvider.get());
  }

  public static ChatModule_ProvidePermissionRepositoryFactory create(
      Provider<PermissionRepositoryImpl> implProvider) {
    return new ChatModule_ProvidePermissionRepositoryFactory(implProvider);
  }

  public static PermissionRepository providePermissionRepository(PermissionRepositoryImpl impl) {
    return Preconditions.checkNotNullFromProvides(ChatModule.INSTANCE.providePermissionRepository(impl));
  }
}

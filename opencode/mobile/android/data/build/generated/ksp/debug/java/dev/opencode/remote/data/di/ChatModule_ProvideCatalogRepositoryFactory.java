package dev.opencode.remote.data.di;

import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.Preconditions;
import dagger.internal.Provider;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import dev.opencode.remote.data.repo.CatalogRepositoryImpl;
import dev.opencode.remote.domain.CatalogRepository;
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
public final class ChatModule_ProvideCatalogRepositoryFactory implements Factory<CatalogRepository> {
  private final Provider<CatalogRepositoryImpl> implProvider;

  private ChatModule_ProvideCatalogRepositoryFactory(Provider<CatalogRepositoryImpl> implProvider) {
    this.implProvider = implProvider;
  }

  @Override
  public CatalogRepository get() {
    return provideCatalogRepository(implProvider.get());
  }

  public static ChatModule_ProvideCatalogRepositoryFactory create(
      Provider<CatalogRepositoryImpl> implProvider) {
    return new ChatModule_ProvideCatalogRepositoryFactory(implProvider);
  }

  public static CatalogRepository provideCatalogRepository(CatalogRepositoryImpl impl) {
    return Preconditions.checkNotNullFromProvides(ChatModule.INSTANCE.provideCatalogRepository(impl));
  }
}

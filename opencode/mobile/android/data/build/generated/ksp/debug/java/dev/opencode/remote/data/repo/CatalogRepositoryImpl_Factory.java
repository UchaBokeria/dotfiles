package dev.opencode.remote.data.repo;

import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.Provider;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
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
public final class CatalogRepositoryImpl_Factory implements Factory<CatalogRepositoryImpl> {
  private final Provider<ActiveApi> activeProvider;

  private CatalogRepositoryImpl_Factory(Provider<ActiveApi> activeProvider) {
    this.activeProvider = activeProvider;
  }

  @Override
  public CatalogRepositoryImpl get() {
    return newInstance(activeProvider.get());
  }

  public static CatalogRepositoryImpl_Factory create(Provider<ActiveApi> activeProvider) {
    return new CatalogRepositoryImpl_Factory(activeProvider);
  }

  public static CatalogRepositoryImpl newInstance(ActiveApi active) {
    return new CatalogRepositoryImpl(active);
  }
}

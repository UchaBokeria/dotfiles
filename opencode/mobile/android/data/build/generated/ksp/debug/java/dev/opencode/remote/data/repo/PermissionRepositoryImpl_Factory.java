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
public final class PermissionRepositoryImpl_Factory implements Factory<PermissionRepositoryImpl> {
  private final Provider<ActiveApi> activeProvider;

  private PermissionRepositoryImpl_Factory(Provider<ActiveApi> activeProvider) {
    this.activeProvider = activeProvider;
  }

  @Override
  public PermissionRepositoryImpl get() {
    return newInstance(activeProvider.get());
  }

  public static PermissionRepositoryImpl_Factory create(Provider<ActiveApi> activeProvider) {
    return new PermissionRepositoryImpl_Factory(activeProvider);
  }

  public static PermissionRepositoryImpl newInstance(ActiveApi active) {
    return new PermissionRepositoryImpl(active);
  }
}

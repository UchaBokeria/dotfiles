package dev.opencode.remote.chat;

import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.Provider;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import dev.opencode.remote.domain.CatalogRepository;
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
public final class ConnectorsViewModel_Factory implements Factory<ConnectorsViewModel> {
  private final Provider<CatalogRepository> catalogProvider;

  private ConnectorsViewModel_Factory(Provider<CatalogRepository> catalogProvider) {
    this.catalogProvider = catalogProvider;
  }

  @Override
  public ConnectorsViewModel get() {
    return newInstance(catalogProvider.get());
  }

  public static ConnectorsViewModel_Factory create(Provider<CatalogRepository> catalogProvider) {
    return new ConnectorsViewModel_Factory(catalogProvider);
  }

  public static ConnectorsViewModel newInstance(CatalogRepository catalog) {
    return new ConnectorsViewModel(catalog);
  }
}

package dev.opencode.remote.servers;

import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.Provider;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import dev.opencode.remote.domain.ServerRepository;
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
public final class ServersViewModel_Factory implements Factory<ServersViewModel> {
  private final Provider<ServerRepository> serversProvider;

  private ServersViewModel_Factory(Provider<ServerRepository> serversProvider) {
    this.serversProvider = serversProvider;
  }

  @Override
  public ServersViewModel get() {
    return newInstance(serversProvider.get());
  }

  public static ServersViewModel_Factory create(Provider<ServerRepository> serversProvider) {
    return new ServersViewModel_Factory(serversProvider);
  }

  public static ServersViewModel newInstance(ServerRepository servers) {
    return new ServersViewModel(servers);
  }
}

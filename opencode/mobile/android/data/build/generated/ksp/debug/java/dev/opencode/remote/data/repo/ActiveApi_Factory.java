package dev.opencode.remote.data.repo;

import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.Provider;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import dev.opencode.remote.domain.ServerRepository;
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
public final class ActiveApi_Factory implements Factory<ActiveApi> {
  private final Provider<ServerRepository> serversProvider;

  private final Provider<SettingsRepository> settingsRepoProvider;

  private ActiveApi_Factory(Provider<ServerRepository> serversProvider,
      Provider<SettingsRepository> settingsRepoProvider) {
    this.serversProvider = serversProvider;
    this.settingsRepoProvider = settingsRepoProvider;
  }

  @Override
  public ActiveApi get() {
    return newInstance(serversProvider.get(), settingsRepoProvider.get());
  }

  public static ActiveApi_Factory create(Provider<ServerRepository> serversProvider,
      Provider<SettingsRepository> settingsRepoProvider) {
    return new ActiveApi_Factory(serversProvider, settingsRepoProvider);
  }

  public static ActiveApi newInstance(ServerRepository servers, SettingsRepository settingsRepo) {
    return new ActiveApi(servers, settingsRepo);
  }
}

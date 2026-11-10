package dev.opencode.remote.settings;

import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.Provider;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import dev.opencode.remote.domain.SettingsRepository;
import dev.opencode.remote.domain.ThemeRepository;
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
public final class SettingsViewModel_Factory implements Factory<SettingsViewModel> {
  private final Provider<SettingsRepository> settingsProvider;

  private final Provider<ThemeRepository> themesProvider;

  private SettingsViewModel_Factory(Provider<SettingsRepository> settingsProvider,
      Provider<ThemeRepository> themesProvider) {
    this.settingsProvider = settingsProvider;
    this.themesProvider = themesProvider;
  }

  @Override
  public SettingsViewModel get() {
    return newInstance(settingsProvider.get(), themesProvider.get());
  }

  public static SettingsViewModel_Factory create(Provider<SettingsRepository> settingsProvider,
      Provider<ThemeRepository> themesProvider) {
    return new SettingsViewModel_Factory(settingsProvider, themesProvider);
  }

  public static SettingsViewModel newInstance(SettingsRepository settings, ThemeRepository themes) {
    return new SettingsViewModel(settings, themes);
  }
}

package dev.opencode.remote;

import dagger.MembersInjector;
import dagger.internal.DaggerGenerated;
import dagger.internal.InjectedFieldSignature;
import dagger.internal.Provider;
import dagger.internal.QualifierMetadata;
import dev.opencode.remote.domain.ThemeRepository;
import javax.annotation.processing.Generated;

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
public final class MainActivity_MembersInjector implements MembersInjector<MainActivity> {
  private final Provider<ThemeRepository> themesProvider;

  private MainActivity_MembersInjector(Provider<ThemeRepository> themesProvider) {
    this.themesProvider = themesProvider;
  }

  @Override
  public void injectMembers(MainActivity instance) {
    injectThemes(instance, themesProvider.get());
  }

  public static MembersInjector<MainActivity> create(Provider<ThemeRepository> themesProvider) {
    return new MainActivity_MembersInjector(themesProvider);
  }

  @InjectedFieldSignature("dev.opencode.remote.MainActivity.themes")
  public static void injectThemes(MainActivity instance, ThemeRepository themes) {
    instance.themes = themes;
  }
}

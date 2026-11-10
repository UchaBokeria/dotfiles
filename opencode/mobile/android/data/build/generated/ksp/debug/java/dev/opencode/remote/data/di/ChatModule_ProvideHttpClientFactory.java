package dev.opencode.remote.data.di;

import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.Preconditions;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import javax.annotation.processing.Generated;
import okhttp3.OkHttpClient;

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
public final class ChatModule_ProvideHttpClientFactory implements Factory<OkHttpClient> {
  @Override
  public OkHttpClient get() {
    return provideHttpClient();
  }

  public static ChatModule_ProvideHttpClientFactory create() {
    return InstanceHolder.INSTANCE;
  }

  public static OkHttpClient provideHttpClient() {
    return Preconditions.checkNotNullFromProvides(ChatModule.INSTANCE.provideHttpClient());
  }

  private static final class InstanceHolder {
    static final ChatModule_ProvideHttpClientFactory INSTANCE = new ChatModule_ProvideHttpClientFactory();
  }
}

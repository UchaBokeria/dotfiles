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
public final class QuestionRepositoryImpl_Factory implements Factory<QuestionRepositoryImpl> {
  private final Provider<ActiveApi> activeProvider;

  private QuestionRepositoryImpl_Factory(Provider<ActiveApi> activeProvider) {
    this.activeProvider = activeProvider;
  }

  @Override
  public QuestionRepositoryImpl get() {
    return newInstance(activeProvider.get());
  }

  public static QuestionRepositoryImpl_Factory create(Provider<ActiveApi> activeProvider) {
    return new QuestionRepositoryImpl_Factory(activeProvider);
  }

  public static QuestionRepositoryImpl newInstance(ActiveApi active) {
    return new QuestionRepositoryImpl(active);
  }
}

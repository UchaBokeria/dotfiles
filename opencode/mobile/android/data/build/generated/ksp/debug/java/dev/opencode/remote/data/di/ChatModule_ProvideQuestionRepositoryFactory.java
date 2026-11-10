package dev.opencode.remote.data.di;

import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.Preconditions;
import dagger.internal.Provider;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import dev.opencode.remote.data.repo.QuestionRepositoryImpl;
import dev.opencode.remote.domain.QuestionRepository;
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
public final class ChatModule_ProvideQuestionRepositoryFactory implements Factory<QuestionRepository> {
  private final Provider<QuestionRepositoryImpl> implProvider;

  private ChatModule_ProvideQuestionRepositoryFactory(
      Provider<QuestionRepositoryImpl> implProvider) {
    this.implProvider = implProvider;
  }

  @Override
  public QuestionRepository get() {
    return provideQuestionRepository(implProvider.get());
  }

  public static ChatModule_ProvideQuestionRepositoryFactory create(
      Provider<QuestionRepositoryImpl> implProvider) {
    return new ChatModule_ProvideQuestionRepositoryFactory(implProvider);
  }

  public static QuestionRepository provideQuestionRepository(QuestionRepositoryImpl impl) {
    return Preconditions.checkNotNullFromProvides(ChatModule.INSTANCE.provideQuestionRepository(impl));
  }
}

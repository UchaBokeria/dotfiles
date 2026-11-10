package dev.opencode.remote.chat;

import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.Provider;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import dev.opencode.remote.domain.ProjectRepository;
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
public final class ProjectsViewModel_Factory implements Factory<ProjectsViewModel> {
  private final Provider<ProjectRepository> projectsProvider;

  private ProjectsViewModel_Factory(Provider<ProjectRepository> projectsProvider) {
    this.projectsProvider = projectsProvider;
  }

  @Override
  public ProjectsViewModel get() {
    return newInstance(projectsProvider.get());
  }

  public static ProjectsViewModel_Factory create(Provider<ProjectRepository> projectsProvider) {
    return new ProjectsViewModel_Factory(projectsProvider);
  }

  public static ProjectsViewModel newInstance(ProjectRepository projects) {
    return new ProjectsViewModel(projects);
  }
}

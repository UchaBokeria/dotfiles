package dev.opencode.remote;

import android.app.Activity;
import android.app.Service;
import android.view.View;
import androidx.fragment.app.Fragment;
import androidx.lifecycle.SavedStateHandle;
import androidx.lifecycle.ViewModel;
import dagger.hilt.android.ActivityRetainedLifecycle;
import dagger.hilt.android.ViewModelLifecycle;
import dagger.hilt.android.internal.builders.ActivityComponentBuilder;
import dagger.hilt.android.internal.builders.ActivityRetainedComponentBuilder;
import dagger.hilt.android.internal.builders.FragmentComponentBuilder;
import dagger.hilt.android.internal.builders.ServiceComponentBuilder;
import dagger.hilt.android.internal.builders.ViewComponentBuilder;
import dagger.hilt.android.internal.builders.ViewModelComponentBuilder;
import dagger.hilt.android.internal.builders.ViewWithFragmentComponentBuilder;
import dagger.hilt.android.internal.lifecycle.DefaultViewModelFactories;
import dagger.hilt.android.internal.lifecycle.DefaultViewModelFactories_InternalFactoryFactory_Factory;
import dagger.hilt.android.internal.managers.ActivityRetainedComponentManager_LifecycleModule_ProvideActivityRetainedLifecycleFactory;
import dagger.hilt.android.internal.managers.SavedStateHandleHolder;
import dagger.hilt.android.internal.modules.ApplicationContextModule;
import dagger.hilt.android.internal.modules.ApplicationContextModule_ProvideContextFactory;
import dagger.internal.DaggerGenerated;
import dagger.internal.DoubleCheck;
import dagger.internal.LazyClassKeyMap;
import dagger.internal.MapBuilder;
import dagger.internal.Preconditions;
import dagger.internal.Provider;
import dev.opencode.remote.chat.ChatViewModel;
import dev.opencode.remote.chat.ChatViewModel_HiltModules;
import dev.opencode.remote.chat.ChatViewModel_HiltModules_BindsModule_Binds_LazyMapKey;
import dev.opencode.remote.chat.ChatViewModel_HiltModules_KeyModule_Provide_LazyMapKey;
import dev.opencode.remote.chat.ConnectorsViewModel;
import dev.opencode.remote.chat.ConnectorsViewModel_HiltModules;
import dev.opencode.remote.chat.ConnectorsViewModel_HiltModules_BindsModule_Binds_LazyMapKey;
import dev.opencode.remote.chat.ConnectorsViewModel_HiltModules_KeyModule_Provide_LazyMapKey;
import dev.opencode.remote.chat.ProjectsViewModel;
import dev.opencode.remote.chat.ProjectsViewModel_HiltModules;
import dev.opencode.remote.chat.ProjectsViewModel_HiltModules_BindsModule_Binds_LazyMapKey;
import dev.opencode.remote.chat.ProjectsViewModel_HiltModules_KeyModule_Provide_LazyMapKey;
import dev.opencode.remote.chat.SessionsViewModel;
import dev.opencode.remote.chat.SessionsViewModel_HiltModules;
import dev.opencode.remote.chat.SessionsViewModel_HiltModules_BindsModule_Binds_LazyMapKey;
import dev.opencode.remote.chat.SessionsViewModel_HiltModules_KeyModule_Provide_LazyMapKey;
import dev.opencode.remote.data.di.ChatModule_ProvideCatalogRepositoryFactory;
import dev.opencode.remote.data.di.ChatModule_ProvideChatRepositoryFactory;
import dev.opencode.remote.data.di.ChatModule_ProvideHttpClientFactory;
import dev.opencode.remote.data.di.ChatModule_ProvidePermissionRepositoryFactory;
import dev.opencode.remote.data.di.ChatModule_ProvideQuestionRepositoryFactory;
import dev.opencode.remote.data.repo.ActiveApi;
import dev.opencode.remote.data.repo.CatalogRepositoryImpl;
import dev.opencode.remote.data.repo.ChatRepositoryImpl;
import dev.opencode.remote.data.repo.PermissionRepositoryImpl;
import dev.opencode.remote.data.repo.QuestionRepositoryImpl;
import dev.opencode.remote.data.store.SecureStore;
import dev.opencode.remote.domain.CatalogRepository;
import dev.opencode.remote.domain.ChatRepository;
import dev.opencode.remote.domain.PermissionRepository;
import dev.opencode.remote.domain.QuestionRepository;
import dev.opencode.remote.servers.ServersViewModel;
import dev.opencode.remote.servers.ServersViewModel_HiltModules;
import dev.opencode.remote.servers.ServersViewModel_HiltModules_BindsModule_Binds_LazyMapKey;
import dev.opencode.remote.servers.ServersViewModel_HiltModules_KeyModule_Provide_LazyMapKey;
import dev.opencode.remote.settings.SettingsViewModel;
import dev.opencode.remote.settings.SettingsViewModel_HiltModules;
import dev.opencode.remote.settings.SettingsViewModel_HiltModules_BindsModule_Binds_LazyMapKey;
import dev.opencode.remote.settings.SettingsViewModel_HiltModules_KeyModule_Provide_LazyMapKey;
import java.util.Collections;
import java.util.Map;
import java.util.Set;
import javax.annotation.processing.Generated;
import okhttp3.OkHttpClient;

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
public final class DaggerOpencodeApp_HiltComponents_SingletonC {
  private DaggerOpencodeApp_HiltComponents_SingletonC() {
  }

  public static Builder builder() {
    return new Builder();
  }

  public static final class Builder {
    private ApplicationContextModule applicationContextModule;

    private Builder() {
    }

    public Builder applicationContextModule(ApplicationContextModule applicationContextModule) {
      this.applicationContextModule = Preconditions.checkNotNull(applicationContextModule);
      return this;
    }

    public OpencodeApp_HiltComponents.SingletonC build() {
      Preconditions.checkBuilderRequirement(applicationContextModule, ApplicationContextModule.class);
      return new SingletonCImpl(applicationContextModule);
    }
  }

  private static final class ActivityRetainedCBuilder implements OpencodeApp_HiltComponents.ActivityRetainedC.Builder {
    private final SingletonCImpl singletonCImpl;

    private SavedStateHandleHolder savedStateHandleHolder;

    private ActivityRetainedCBuilder(SingletonCImpl singletonCImpl) {
      this.singletonCImpl = singletonCImpl;
    }

    @Override
    public ActivityRetainedCBuilder savedStateHandleHolder(
        SavedStateHandleHolder savedStateHandleHolder) {
      this.savedStateHandleHolder = Preconditions.checkNotNull(savedStateHandleHolder);
      return this;
    }

    @Override
    public OpencodeApp_HiltComponents.ActivityRetainedC build() {
      Preconditions.checkBuilderRequirement(savedStateHandleHolder, SavedStateHandleHolder.class);
      return new ActivityRetainedCImpl(singletonCImpl, savedStateHandleHolder);
    }
  }

  private static final class ActivityCBuilder implements OpencodeApp_HiltComponents.ActivityC.Builder {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private Activity activity;

    private ActivityCBuilder(SingletonCImpl singletonCImpl,
        ActivityRetainedCImpl activityRetainedCImpl) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;
    }

    @Override
    public ActivityCBuilder activity(Activity activity) {
      this.activity = Preconditions.checkNotNull(activity);
      return this;
    }

    @Override
    public OpencodeApp_HiltComponents.ActivityC build() {
      Preconditions.checkBuilderRequirement(activity, Activity.class);
      return new ActivityCImpl(singletonCImpl, activityRetainedCImpl, activity);
    }
  }

  private static final class FragmentCBuilder implements OpencodeApp_HiltComponents.FragmentC.Builder {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private final ActivityCImpl activityCImpl;

    private Fragment fragment;

    private FragmentCBuilder(SingletonCImpl singletonCImpl,
        ActivityRetainedCImpl activityRetainedCImpl, ActivityCImpl activityCImpl) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;
      this.activityCImpl = activityCImpl;
    }

    @Override
    public FragmentCBuilder fragment(Fragment fragment) {
      this.fragment = Preconditions.checkNotNull(fragment);
      return this;
    }

    @Override
    public OpencodeApp_HiltComponents.FragmentC build() {
      Preconditions.checkBuilderRequirement(fragment, Fragment.class);
      return new FragmentCImpl(singletonCImpl, activityRetainedCImpl, activityCImpl, fragment);
    }
  }

  private static final class ViewWithFragmentCBuilder implements OpencodeApp_HiltComponents.ViewWithFragmentC.Builder {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private final ActivityCImpl activityCImpl;

    private final FragmentCImpl fragmentCImpl;

    private View view;

    private ViewWithFragmentCBuilder(SingletonCImpl singletonCImpl,
        ActivityRetainedCImpl activityRetainedCImpl, ActivityCImpl activityCImpl,
        FragmentCImpl fragmentCImpl) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;
      this.activityCImpl = activityCImpl;
      this.fragmentCImpl = fragmentCImpl;
    }

    @Override
    public ViewWithFragmentCBuilder view(View view) {
      this.view = Preconditions.checkNotNull(view);
      return this;
    }

    @Override
    public OpencodeApp_HiltComponents.ViewWithFragmentC build() {
      Preconditions.checkBuilderRequirement(view, View.class);
      return new ViewWithFragmentCImpl(singletonCImpl, activityRetainedCImpl, activityCImpl, fragmentCImpl, view);
    }
  }

  private static final class ViewCBuilder implements OpencodeApp_HiltComponents.ViewC.Builder {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private final ActivityCImpl activityCImpl;

    private View view;

    private ViewCBuilder(SingletonCImpl singletonCImpl, ActivityRetainedCImpl activityRetainedCImpl,
        ActivityCImpl activityCImpl) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;
      this.activityCImpl = activityCImpl;
    }

    @Override
    public ViewCBuilder view(View view) {
      this.view = Preconditions.checkNotNull(view);
      return this;
    }

    @Override
    public OpencodeApp_HiltComponents.ViewC build() {
      Preconditions.checkBuilderRequirement(view, View.class);
      return new ViewCImpl(singletonCImpl, activityRetainedCImpl, activityCImpl, view);
    }
  }

  private static final class ViewModelCBuilder implements OpencodeApp_HiltComponents.ViewModelC.Builder {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private SavedStateHandle savedStateHandle;

    private ViewModelLifecycle viewModelLifecycle;

    private ViewModelCBuilder(SingletonCImpl singletonCImpl,
        ActivityRetainedCImpl activityRetainedCImpl) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;
    }

    @Override
    public ViewModelCBuilder savedStateHandle(SavedStateHandle handle) {
      this.savedStateHandle = Preconditions.checkNotNull(handle);
      return this;
    }

    @Override
    public ViewModelCBuilder viewModelLifecycle(ViewModelLifecycle viewModelLifecycle) {
      this.viewModelLifecycle = Preconditions.checkNotNull(viewModelLifecycle);
      return this;
    }

    @Override
    public OpencodeApp_HiltComponents.ViewModelC build() {
      Preconditions.checkBuilderRequirement(savedStateHandle, SavedStateHandle.class);
      Preconditions.checkBuilderRequirement(viewModelLifecycle, ViewModelLifecycle.class);
      return new ViewModelCImpl(singletonCImpl, activityRetainedCImpl, savedStateHandle, viewModelLifecycle);
    }
  }

  private static final class ServiceCBuilder implements OpencodeApp_HiltComponents.ServiceC.Builder {
    private final SingletonCImpl singletonCImpl;

    private Service service;

    private ServiceCBuilder(SingletonCImpl singletonCImpl) {
      this.singletonCImpl = singletonCImpl;
    }

    @Override
    public ServiceCBuilder service(Service service) {
      this.service = Preconditions.checkNotNull(service);
      return this;
    }

    @Override
    public OpencodeApp_HiltComponents.ServiceC build() {
      Preconditions.checkBuilderRequirement(service, Service.class);
      return new ServiceCImpl(singletonCImpl, service);
    }
  }

  private static final class ViewWithFragmentCImpl extends OpencodeApp_HiltComponents.ViewWithFragmentC {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private final ActivityCImpl activityCImpl;

    private final FragmentCImpl fragmentCImpl;

    private final ViewWithFragmentCImpl viewWithFragmentCImpl = this;

    ViewWithFragmentCImpl(SingletonCImpl singletonCImpl,
        ActivityRetainedCImpl activityRetainedCImpl, ActivityCImpl activityCImpl,
        FragmentCImpl fragmentCImpl, View viewParam) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;
      this.activityCImpl = activityCImpl;
      this.fragmentCImpl = fragmentCImpl;


    }
  }

  private static final class FragmentCImpl extends OpencodeApp_HiltComponents.FragmentC {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private final ActivityCImpl activityCImpl;

    private final FragmentCImpl fragmentCImpl = this;

    FragmentCImpl(SingletonCImpl singletonCImpl, ActivityRetainedCImpl activityRetainedCImpl,
        ActivityCImpl activityCImpl, Fragment fragmentParam) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;
      this.activityCImpl = activityCImpl;


    }

    @Override
    public DefaultViewModelFactories.InternalFactoryFactory getHiltInternalFactoryFactory() {
      return activityCImpl.getHiltInternalFactoryFactory();
    }

    @Override
    public ViewWithFragmentComponentBuilder viewWithFragmentComponentBuilder() {
      return new ViewWithFragmentCBuilder(singletonCImpl, activityRetainedCImpl, activityCImpl, fragmentCImpl);
    }
  }

  private static final class ViewCImpl extends OpencodeApp_HiltComponents.ViewC {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private final ActivityCImpl activityCImpl;

    private final ViewCImpl viewCImpl = this;

    ViewCImpl(SingletonCImpl singletonCImpl, ActivityRetainedCImpl activityRetainedCImpl,
        ActivityCImpl activityCImpl, View viewParam) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;
      this.activityCImpl = activityCImpl;


    }
  }

  private static final class ActivityCImpl extends OpencodeApp_HiltComponents.ActivityC {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private final ActivityCImpl activityCImpl = this;

    ActivityCImpl(SingletonCImpl singletonCImpl, ActivityRetainedCImpl activityRetainedCImpl,
        Activity activityParam) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;


    }

    @Override
    public DefaultViewModelFactories.InternalFactoryFactory getHiltInternalFactoryFactory() {
      return DefaultViewModelFactories_InternalFactoryFactory_Factory.newInstance(getViewModelKeys(), new ViewModelCBuilder(singletonCImpl, activityRetainedCImpl));
    }

    @Override
    public Map<Class<?>, Boolean> getViewModelKeys() {
      return LazyClassKeyMap.<Boolean>of(MapBuilder.<String, Boolean>newMapBuilder(6).put(ChatViewModel_HiltModules_KeyModule_Provide_LazyMapKey.lazyClassKeyName, ChatViewModel_HiltModules.KeyModule.provide()).put(ConnectorsViewModel_HiltModules_KeyModule_Provide_LazyMapKey.lazyClassKeyName, ConnectorsViewModel_HiltModules.KeyModule.provide()).put(ProjectsViewModel_HiltModules_KeyModule_Provide_LazyMapKey.lazyClassKeyName, ProjectsViewModel_HiltModules.KeyModule.provide()).put(ServersViewModel_HiltModules_KeyModule_Provide_LazyMapKey.lazyClassKeyName, ServersViewModel_HiltModules.KeyModule.provide()).put(SessionsViewModel_HiltModules_KeyModule_Provide_LazyMapKey.lazyClassKeyName, SessionsViewModel_HiltModules.KeyModule.provide()).put(SettingsViewModel_HiltModules_KeyModule_Provide_LazyMapKey.lazyClassKeyName, SettingsViewModel_HiltModules.KeyModule.provide()).build());
    }

    @Override
    public ViewModelComponentBuilder getViewModelComponentBuilder() {
      return new ViewModelCBuilder(singletonCImpl, activityRetainedCImpl);
    }

    @Override
    public FragmentComponentBuilder fragmentComponentBuilder() {
      return new FragmentCBuilder(singletonCImpl, activityRetainedCImpl, activityCImpl);
    }

    @Override
    public ViewComponentBuilder viewComponentBuilder() {
      return new ViewCBuilder(singletonCImpl, activityRetainedCImpl, activityCImpl);
    }

    @Override
    public void injectMainActivity(MainActivity arg0) {
      injectMainActivity2(arg0);
    }

    private MainActivity injectMainActivity2(MainActivity instance) {
      MainActivity_MembersInjector.injectThemes(instance, singletonCImpl.secureStoreProvider.get());
      return instance;
    }
  }

  private static final class ViewModelCImpl extends OpencodeApp_HiltComponents.ViewModelC {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private final ViewModelCImpl viewModelCImpl = this;

    Provider<ChatViewModel> chatViewModelProvider;

    Provider<ConnectorsViewModel> connectorsViewModelProvider;

    Provider<ProjectsViewModel> projectsViewModelProvider;

    Provider<ServersViewModel> serversViewModelProvider;

    Provider<SessionsViewModel> sessionsViewModelProvider;

    Provider<SettingsViewModel> settingsViewModelProvider;

    ViewModelCImpl(SingletonCImpl singletonCImpl, ActivityRetainedCImpl activityRetainedCImpl,
        SavedStateHandle savedStateHandleParam, ViewModelLifecycle viewModelLifecycleParam) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;

      initialize(savedStateHandleParam, viewModelLifecycleParam);

    }

    @SuppressWarnings("unchecked")
    private void initialize(final SavedStateHandle savedStateHandleParam,
        final ViewModelLifecycle viewModelLifecycleParam) {
      this.chatViewModelProvider = new SwitchingProvider<>(singletonCImpl, activityRetainedCImpl, viewModelCImpl, 0);
      this.connectorsViewModelProvider = new SwitchingProvider<>(singletonCImpl, activityRetainedCImpl, viewModelCImpl, 1);
      this.projectsViewModelProvider = new SwitchingProvider<>(singletonCImpl, activityRetainedCImpl, viewModelCImpl, 2);
      this.serversViewModelProvider = new SwitchingProvider<>(singletonCImpl, activityRetainedCImpl, viewModelCImpl, 3);
      this.sessionsViewModelProvider = new SwitchingProvider<>(singletonCImpl, activityRetainedCImpl, viewModelCImpl, 4);
      this.settingsViewModelProvider = new SwitchingProvider<>(singletonCImpl, activityRetainedCImpl, viewModelCImpl, 5);
    }

    @Override
    public Map<Class<?>, javax.inject.Provider<ViewModel>> getHiltViewModelMap() {
      return LazyClassKeyMap.<javax.inject.Provider<ViewModel>>of(MapBuilder.<String, javax.inject.Provider<ViewModel>>newMapBuilder(6).put(ChatViewModel_HiltModules_BindsModule_Binds_LazyMapKey.lazyClassKeyName, ((Provider) (chatViewModelProvider))).put(ConnectorsViewModel_HiltModules_BindsModule_Binds_LazyMapKey.lazyClassKeyName, ((Provider) (connectorsViewModelProvider))).put(ProjectsViewModel_HiltModules_BindsModule_Binds_LazyMapKey.lazyClassKeyName, ((Provider) (projectsViewModelProvider))).put(ServersViewModel_HiltModules_BindsModule_Binds_LazyMapKey.lazyClassKeyName, ((Provider) (serversViewModelProvider))).put(SessionsViewModel_HiltModules_BindsModule_Binds_LazyMapKey.lazyClassKeyName, ((Provider) (sessionsViewModelProvider))).put(SettingsViewModel_HiltModules_BindsModule_Binds_LazyMapKey.lazyClassKeyName, ((Provider) (settingsViewModelProvider))).build());
    }

    @Override
    public Map<Class<?>, Object> getHiltViewModelAssistedMap() {
      return Collections.<Class<?>, Object>emptyMap();
    }

    private static final class SwitchingProvider<T> implements Provider<T> {
      private final SingletonCImpl singletonCImpl;

      private final ActivityRetainedCImpl activityRetainedCImpl;

      private final ViewModelCImpl viewModelCImpl;

      private final int id;

      SwitchingProvider(SingletonCImpl singletonCImpl, ActivityRetainedCImpl activityRetainedCImpl,
          ViewModelCImpl viewModelCImpl, int id) {
        this.singletonCImpl = singletonCImpl;
        this.activityRetainedCImpl = activityRetainedCImpl;
        this.viewModelCImpl = viewModelCImpl;
        this.id = id;
      }

      @Override
      @SuppressWarnings("unchecked")
      public T get() {
        switch (id) {
          case 0: // dev.opencode.remote.chat.ChatViewModel
          return (T) new ChatViewModel(singletonCImpl.provideChatRepositoryProvider.get(), singletonCImpl.secureStoreProvider.get(), singletonCImpl.providePermissionRepositoryProvider.get(), singletonCImpl.provideQuestionRepositoryProvider.get(), singletonCImpl.provideCatalogRepositoryProvider.get(), singletonCImpl.secureStoreProvider.get(), ApplicationContextModule_ProvideContextFactory.provideContext(singletonCImpl.applicationContextModule));

          case 1: // dev.opencode.remote.chat.ConnectorsViewModel
          return (T) new ConnectorsViewModel(singletonCImpl.provideCatalogRepositoryProvider.get());

          case 2: // dev.opencode.remote.chat.ProjectsViewModel
          return (T) new ProjectsViewModel(singletonCImpl.secureStoreProvider.get());

          case 3: // dev.opencode.remote.servers.ServersViewModel
          return (T) new ServersViewModel(singletonCImpl.secureStoreProvider.get());

          case 4: // dev.opencode.remote.chat.SessionsViewModel
          return (T) new SessionsViewModel(singletonCImpl.provideChatRepositoryProvider.get(), singletonCImpl.secureStoreProvider.get(), singletonCImpl.secureStoreProvider.get());

          case 5: // dev.opencode.remote.settings.SettingsViewModel
          return (T) new SettingsViewModel(singletonCImpl.secureStoreProvider.get(), singletonCImpl.secureStoreProvider.get());

          default: throw new AssertionError(id);
        }
      }
    }
  }

  private static final class ActivityRetainedCImpl extends OpencodeApp_HiltComponents.ActivityRetainedC {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl = this;

    Provider<ActivityRetainedLifecycle> provideActivityRetainedLifecycleProvider;

    ActivityRetainedCImpl(SingletonCImpl singletonCImpl,
        SavedStateHandleHolder savedStateHandleHolderParam) {
      this.singletonCImpl = singletonCImpl;

      initialize(savedStateHandleHolderParam);

    }

    @SuppressWarnings("unchecked")
    private void initialize(final SavedStateHandleHolder savedStateHandleHolderParam) {
      this.provideActivityRetainedLifecycleProvider = DoubleCheck.provider(new SwitchingProvider<ActivityRetainedLifecycle>(singletonCImpl, activityRetainedCImpl, 0));
    }

    @Override
    public ActivityComponentBuilder activityComponentBuilder() {
      return new ActivityCBuilder(singletonCImpl, activityRetainedCImpl);
    }

    @Override
    public ActivityRetainedLifecycle getActivityRetainedLifecycle() {
      return provideActivityRetainedLifecycleProvider.get();
    }

    private static final class SwitchingProvider<T> implements Provider<T> {
      private final SingletonCImpl singletonCImpl;

      private final ActivityRetainedCImpl activityRetainedCImpl;

      private final int id;

      SwitchingProvider(SingletonCImpl singletonCImpl, ActivityRetainedCImpl activityRetainedCImpl,
          int id) {
        this.singletonCImpl = singletonCImpl;
        this.activityRetainedCImpl = activityRetainedCImpl;
        this.id = id;
      }

      @Override
      @SuppressWarnings("unchecked")
      public T get() {
        switch (id) {
          case 0: // dagger.hilt.android.ActivityRetainedLifecycle
          return (T) ActivityRetainedComponentManager_LifecycleModule_ProvideActivityRetainedLifecycleFactory.provideActivityRetainedLifecycle();

          default: throw new AssertionError(id);
        }
      }
    }
  }

  private static final class ServiceCImpl extends OpencodeApp_HiltComponents.ServiceC {
    private final SingletonCImpl singletonCImpl;

    private final ServiceCImpl serviceCImpl = this;

    ServiceCImpl(SingletonCImpl singletonCImpl, Service serviceParam) {
      this.singletonCImpl = singletonCImpl;


    }
  }

  private static final class SingletonCImpl extends OpencodeApp_HiltComponents.SingletonC {
    private final ApplicationContextModule applicationContextModule;

    private final SingletonCImpl singletonCImpl = this;

    Provider<SecureStore> secureStoreProvider;

    Provider<PermissionRepositoryImpl> permissionRepositoryImplProvider;

    Provider<PermissionRepository> providePermissionRepositoryProvider;

    Provider<QuestionRepositoryImpl> questionRepositoryImplProvider;

    Provider<QuestionRepository> provideQuestionRepositoryProvider;

    Provider<OkHttpClient> provideHttpClientProvider;

    Provider<ChatRepositoryImpl> chatRepositoryImplProvider;

    Provider<ChatRepository> provideChatRepositoryProvider;

    Provider<CatalogRepositoryImpl> catalogRepositoryImplProvider;

    Provider<CatalogRepository> provideCatalogRepositoryProvider;

    SingletonCImpl(ApplicationContextModule applicationContextModuleParam) {
      this.applicationContextModule = applicationContextModuleParam;
      initialize(applicationContextModuleParam);

    }

    ActiveApi activeApi() {
      return new ActiveApi(secureStoreProvider.get(), secureStoreProvider.get());
    }

    @SuppressWarnings("unchecked")
    private void initialize(final ApplicationContextModule applicationContextModuleParam) {
      this.secureStoreProvider = DoubleCheck.provider(new SwitchingProvider<SecureStore>(singletonCImpl, 0));
      this.permissionRepositoryImplProvider = DoubleCheck.provider(new SwitchingProvider<PermissionRepositoryImpl>(singletonCImpl, 4));
      this.providePermissionRepositoryProvider = DoubleCheck.provider(new SwitchingProvider<PermissionRepository>(singletonCImpl, 3));
      this.questionRepositoryImplProvider = DoubleCheck.provider(new SwitchingProvider<QuestionRepositoryImpl>(singletonCImpl, 6));
      this.provideQuestionRepositoryProvider = DoubleCheck.provider(new SwitchingProvider<QuestionRepository>(singletonCImpl, 5));
      this.provideHttpClientProvider = DoubleCheck.provider(new SwitchingProvider<OkHttpClient>(singletonCImpl, 7));
      this.chatRepositoryImplProvider = DoubleCheck.provider(new SwitchingProvider<ChatRepositoryImpl>(singletonCImpl, 2));
      this.provideChatRepositoryProvider = DoubleCheck.provider(new SwitchingProvider<ChatRepository>(singletonCImpl, 1));
      this.catalogRepositoryImplProvider = DoubleCheck.provider(new SwitchingProvider<CatalogRepositoryImpl>(singletonCImpl, 9));
      this.provideCatalogRepositoryProvider = DoubleCheck.provider(new SwitchingProvider<CatalogRepository>(singletonCImpl, 8));
    }

    @Override
    public Set<Boolean> getDisableFragmentGetContextFix() {
      return Collections.<Boolean>emptySet();
    }

    @Override
    public ActivityRetainedComponentBuilder retainedComponentBuilder() {
      return new ActivityRetainedCBuilder(singletonCImpl);
    }

    @Override
    public ServiceComponentBuilder serviceComponentBuilder() {
      return new ServiceCBuilder(singletonCImpl);
    }

    @Override
    public void injectOpencodeApp(OpencodeApp opencodeApp) {
    }

    private static final class SwitchingProvider<T> implements Provider<T> {
      private final SingletonCImpl singletonCImpl;

      private final int id;

      SwitchingProvider(SingletonCImpl singletonCImpl, int id) {
        this.singletonCImpl = singletonCImpl;
        this.id = id;
      }

      @Override
      @SuppressWarnings("unchecked")
      public T get() {
        switch (id) {
          case 0: // dev.opencode.remote.data.store.SecureStore
          return (T) new SecureStore(ApplicationContextModule_ProvideContextFactory.provideContext(singletonCImpl.applicationContextModule));

          case 1: // dev.opencode.remote.domain.ChatRepository
          return (T) ChatModule_ProvideChatRepositoryFactory.provideChatRepository(singletonCImpl.chatRepositoryImplProvider.get());

          case 2: // dev.opencode.remote.data.repo.ChatRepositoryImpl
          return (T) new ChatRepositoryImpl(singletonCImpl.secureStoreProvider.get(), singletonCImpl.providePermissionRepositoryProvider.get(), singletonCImpl.provideQuestionRepositoryProvider.get(), singletonCImpl.provideHttpClientProvider.get());

          case 3: // dev.opencode.remote.domain.PermissionRepository
          return (T) ChatModule_ProvidePermissionRepositoryFactory.providePermissionRepository(singletonCImpl.permissionRepositoryImplProvider.get());

          case 4: // dev.opencode.remote.data.repo.PermissionRepositoryImpl
          return (T) new PermissionRepositoryImpl(singletonCImpl.activeApi());

          case 5: // dev.opencode.remote.domain.QuestionRepository
          return (T) ChatModule_ProvideQuestionRepositoryFactory.provideQuestionRepository(singletonCImpl.questionRepositoryImplProvider.get());

          case 6: // dev.opencode.remote.data.repo.QuestionRepositoryImpl
          return (T) new QuestionRepositoryImpl(singletonCImpl.activeApi());

          case 7: // okhttp3.OkHttpClient
          return (T) ChatModule_ProvideHttpClientFactory.provideHttpClient();

          case 8: // dev.opencode.remote.domain.CatalogRepository
          return (T) ChatModule_ProvideCatalogRepositoryFactory.provideCatalogRepository(singletonCImpl.catalogRepositoryImplProvider.get());

          case 9: // dev.opencode.remote.data.repo.CatalogRepositoryImpl
          return (T) new CatalogRepositoryImpl(singletonCImpl.activeApi());

          default: throw new AssertionError(id);
        }
      }
    }
  }
}

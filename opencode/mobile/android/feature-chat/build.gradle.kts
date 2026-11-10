plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.compose.compiler)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.hilt)
    alias(libs.plugins.ksp)
}

android {
    namespace = "dev.opencode.remote.chat"
    compileSdk = 36
    defaultConfig { minSdk = 26 }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures { compose = true }
}

dependencies {
    implementation(project(":domain"))
    implementation(project(":feature-theme"))
    implementation(project(":data"))
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.material3)
    implementation(libs.androidx.lifecycle.runtime)
    implementation(libs.androidx.lifecycle.common)
    implementation(libs.androidx.lifecycle.viewmodel)
    implementation(libs.hilt.android)
    implementation(libs.hilt.navigation)
    implementation(libs.markdown.m3)
    implementation(libs.markdown.code)
    testImplementation(libs.junit)
    testImplementation(libs.coroutines.test)
    ksp(libs.hilt.compiler)
}

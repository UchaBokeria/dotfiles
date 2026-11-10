plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.compose.compiler)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.hilt)
    alias(libs.plugins.ksp)
}

android {
    namespace = "dev.opencode.remote.servers"
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
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.material3)
    implementation(libs.androidx.lifecycle.runtime)
    implementation(libs.androidx.lifecycle.common)
    implementation(libs.androidx.lifecycle.viewmodel)
    implementation(libs.hilt.android)
    implementation(libs.hilt.navigation)
    ksp(libs.hilt.compiler)
}

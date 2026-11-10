plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.compose.compiler)
    alias(libs.plugins.hilt)
    alias(libs.plugins.ksp)
}

android {
    namespace = "dev.opencode.remote.theme"
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
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.material3)
    implementation(libs.androidx.activity.compose)
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
}

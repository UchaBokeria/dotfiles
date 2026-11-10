plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.compose.compiler)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.hilt)
    alias(libs.plugins.ksp)
}

android {
    namespace = "dev.opencode.remote"
    compileSdk = 36
    defaultConfig {
        applicationId = "dev.opencode.remote"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0-p0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
        }
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures { compose = true }
}

dependencies {
    implementation(project(":domain"))
    implementation(project(":data"))
    implementation(project(":feature-theme"))
    implementation(project(":feature-servers"))
    implementation(project(":feature-settings"))
    implementation(project(":feature-chat"))
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.material3)
    implementation(libs.compose.material.icons)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime)
    implementation(libs.androidx.lifecycle.viewmodel)
    implementation(libs.androidx.navigation)
    implementation(libs.hilt.android)
    implementation(libs.hilt.navigation)
    ksp(libs.hilt.compiler)
}

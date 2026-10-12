plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

val canonicalVersion = rootProject.file("../VERSION").readText().trim()

android {
    namespace = "com.asanda.structuralpro"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.asanda.structuralpro"
        minSdk = 29
        targetSdk = 35
        versionCode = 1
        versionName = canonicalVersion
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.compose.ui:ui:1.7.6")
    implementation("androidx.compose.material3:material3:1.3.1")
}

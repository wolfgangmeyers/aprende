plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.ksp)
    alias(libs.plugins.hilt)
}

android {
    namespace = "com.magicalhippie.aprende"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.magicalhippie.aprende"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"

        // Custom runner so Hilt can swap in HiltTestApplication for instrumented tests.
        testInstrumentationRunner = "com.magicalhippie.aprende.HiltTestRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    buildFeatures {
        compose = true
    }

    compileOptions {
        isCoreLibraryDesugaringEnabled = true
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    testOptions {
        // Required so Robolectric Compose/resource tests can read merged resources.
        unitTests.isIncludeAndroidResources = true
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

// Export Room schemas to a versioned, reviewable location (D2 — content.db carries
// its own @Database version; migration tests read these JSON schemas).
ksp {
    arg("room.schemaLocation", "$projectDir/schemas")
}

dependencies {
    // --- Core / lifecycle ---
    coreLibraryDesugaring(libs.desugar.jdk.libs)
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)

    // --- Compose (BOM-aligned) ---
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    debugImplementation(libs.androidx.compose.ui.tooling)
    debugImplementation(libs.androidx.compose.ui.test.manifest)

    // --- Navigation ---
    implementation(libs.androidx.navigation.compose)

    // --- Hilt ---
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
    implementation(libs.androidx.hilt.navigation.compose)

    // --- Room ---
    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)

    // --- DataStore ---
    implementation(libs.androidx.datastore.preferences)

    // --- Coroutines ---
    implementation(libs.kotlinx.coroutines.android)

    // --- Serialization (versioned backup JSON codec — SPEC §11) ---
    implementation(libs.kotlinx.serialization.json)

    // --- JVM unit tests (incl. Robolectric Compose) ---
    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.turbine)
    testImplementation(libs.robolectric)
    testImplementation(libs.androidx.room.testing)
    // Compose test rule resolved through the BOM for unit (Robolectric) tests.
    testImplementation(platform(libs.androidx.compose.bom))
    testImplementation(libs.androidx.compose.ui.test.junit4)

    // --- Instrumented tests ---
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    androidTestImplementation(libs.hilt.android.testing)
    kspAndroidTest(libs.hilt.compiler)
}

package com.magicalhippie.aprende

import android.app.Application
import android.content.Context
import androidx.test.runner.AndroidJUnitRunner
import dagger.hilt.android.testing.HiltTestApplication

/**
 * Custom instrumentation runner for Hilt instrumented tests.
 *
 * Swaps the app's [AprendeApplication] for Hilt's generated [HiltTestApplication]
 * so `@HiltAndroidTest` classes get a test-configurable component. Wired via
 * `testInstrumentationRunner` in app/build.gradle.kts.
 */
class HiltTestRunner : AndroidJUnitRunner() {
    override fun newApplication(
        cl: ClassLoader?,
        className: String?,
        context: Context?,
    ): Application {
        return super.newApplication(cl, HiltTestApplication::class.java.name, context)
    }
}

package com.magicalhippie.aprende

import android.app.Application
import dagger.hilt.android.HiltAndroidApp

/**
 * Application entry point. [HiltAndroidApp] triggers Hilt's code generation and
 * creates the application-level dependency container (SingletonComponent), which
 * all other Hilt entry points (Activities, ViewModels) attach to.
 */
@HiltAndroidApp
class AprendeApplication : Application()

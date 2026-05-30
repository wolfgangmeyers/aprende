package com.magicalhippie.aprende.data.settings

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.preferencesDataStore
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * Hilt bindings for the Preferences DataStore that backs [SettingsRepositoryImpl] (SPEC §10.2).
 *
 * The `preferencesDataStore` delegate creates a single per-process instance keyed by name, so
 * we resolve it once off the application Context and provide it as a singleton.
 */
private val Context.settingsDataStore: DataStore<Preferences> by preferencesDataStore(
    name = SettingsRepositoryImpl.DATASTORE_NAME,
)

@Module
@InstallIn(SingletonComponent::class)
object SettingsDataModule {

    @Provides
    @Singleton
    fun provideSettingsDataStore(
        @ApplicationContext context: Context,
    ): DataStore<Preferences> = context.settingsDataStore
}

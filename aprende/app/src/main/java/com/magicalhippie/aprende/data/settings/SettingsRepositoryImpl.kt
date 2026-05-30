package com.magicalhippie.aprende.data.settings

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import com.magicalhippie.aprende.domain.repository.SettingsRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject

/**
 * Preferences-DataStore-backed [SettingsRepository] (SPEC §10.2).
 *
 * **Deviation from SPEC §10.2 (documented):** the spec says "Proto DataStore", but we use
 * **Preferences DataStore** instead. Proto would require adding the `protobuf` Gradle plugin
 * + `.proto` schema codegen (build complexity we are avoiding for now), whereas
 * `androidx.datastore:datastore-preferences` is already a wired dependency. The set of
 * settings here is a small flat scalar set, which Preferences handles cleanly. Revisit if we
 * ever need a richer typed settings object — at which point Proto's schema/codegen earns its
 * keep. Each setting is a typed Preferences key, read as `Flow`, written via `edit { }`.
 */
class SettingsRepositoryImpl @Inject constructor(
    private val dataStore: DataStore<Preferences>,
) : SettingsRepository {

    override val ttsLocale: Flow<String> =
        dataStore.data.map { it[KEY_TTS_LOCALE] ?: DEFAULT_TTS_LOCALE }

    override suspend fun setTtsLocale(value: String) {
        dataStore.edit { it[KEY_TTS_LOCALE] = value }
    }

    override val speakingEnabled: Flow<Boolean> =
        dataStore.data.map { it[KEY_SPEAKING_ENABLED] ?: DEFAULT_SPEAKING_ENABLED }

    override suspend fun setSpeakingEnabled(value: Boolean) {
        dataStore.edit { it[KEY_SPEAKING_ENABLED] = value }
    }

    override val dailyGoalXp: Flow<Int> =
        dataStore.data.map { it[KEY_DAILY_GOAL_XP] ?: DEFAULT_DAILY_GOAL_XP }

    override suspend fun setDailyGoalXp(value: Int) {
        dataStore.edit { it[KEY_DAILY_GOAL_XP] = value }
    }

    override val accentBarEnabled: Flow<Boolean> =
        dataStore.data.map { it[KEY_ACCENT_BAR_ENABLED] ?: DEFAULT_ACCENT_BAR_ENABLED }

    override suspend fun setAccentBarEnabled(value: Boolean) {
        dataStore.edit { it[KEY_ACCENT_BAR_ENABLED] = value }
    }

    companion object {
        const val DATASTORE_NAME: String = "settings"

        // Typed Preferences keys.
        val KEY_TTS_LOCALE = stringPreferencesKey("tts_locale")
        val KEY_SPEAKING_ENABLED = booleanPreferencesKey("speaking_enabled")
        val KEY_DAILY_GOAL_XP = intPreferencesKey("daily_goal_xp")
        val KEY_ACCENT_BAR_ENABLED = booleanPreferencesKey("accent_bar_enabled")

        // Defaults (SPEC §9 daily goal default Regular = 20; §12.6 default Spanish locale).
        const val DEFAULT_TTS_LOCALE = "es-ES"
        const val DEFAULT_SPEAKING_ENABLED = false
        const val DEFAULT_DAILY_GOAL_XP = 20
        const val DEFAULT_ACCENT_BAR_ENABLED = true
    }
}

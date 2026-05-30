package com.magicalhippie.aprende.domain.repository

import kotlinx.coroutines.flow.Flow

/**
 * App-level scalar settings (SPEC §10.2: "lightweight scalars/flags live in DataStore, not
 * Room"). Declared in the domain layer; backed by a DataStore implementation in the data
 * layer. Each setting is observable as a `Flow` and written by a suspend setter.
 */
interface SettingsRepository {
    /** TTS voice/locale, e.g. "es-ES" / "es-MX" (SPEC §12.6). */
    val ttsLocale: Flow<String>
    suspend fun setTtsLocale(value: String)

    /** Whether speaking exercises are enabled (capability-gated — SPEC §11.0 Tier 2). */
    val speakingEnabled: Flow<Boolean>
    suspend fun setSpeakingEnabled(value: Boolean)

    /** Daily XP goal tier (SPEC §9). */
    val dailyGoalXp: Flow<Int>
    suspend fun setDailyGoalXp(value: Int)

    /** Whether the accent-input bar is shown (SPEC §5/§10.2 accent-bar prefs). */
    val accentBarEnabled: Flow<Boolean>
    suspend fun setAccentBarEnabled(value: Boolean)
}

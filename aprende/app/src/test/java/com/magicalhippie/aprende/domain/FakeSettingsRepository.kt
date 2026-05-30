package com.magicalhippie.aprende.domain

import com.magicalhippie.aprende.domain.repository.SettingsRepository
import kotlinx.coroutines.flow.MutableStateFlow

/** In-memory [SettingsRepository] for JVM unit tests. */
class FakeSettingsRepository(dailyGoal: Int = 20) : SettingsRepository {
    override val ttsLocale = MutableStateFlow("es-ES")
    override suspend fun setTtsLocale(value: String) { ttsLocale.value = value }

    override val speakingEnabled = MutableStateFlow(false)
    override suspend fun setSpeakingEnabled(value: Boolean) { speakingEnabled.value = value }

    override val dailyGoalXp = MutableStateFlow(dailyGoal)
    override suspend fun setDailyGoalXp(value: Int) { dailyGoalXp.value = value }

    override val accentBarEnabled = MutableStateFlow(true)
    override suspend fun setAccentBarEnabled(value: Boolean) { accentBarEnabled.value = value }
}

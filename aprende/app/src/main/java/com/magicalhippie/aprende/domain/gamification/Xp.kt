package com.magicalhippie.aprende.domain.gamification

import com.magicalhippie.aprende.domain.model.DailyActivity
import com.magicalhippie.aprende.domain.repository.ProgressRepository
import com.magicalhippie.aprende.domain.repository.SettingsRepository
import kotlinx.coroutines.flow.first
import java.time.Clock
import java.time.LocalDate
import javax.inject.Inject

/** XP award values (SPEC §9). */
object Xp {
    const val STANDARD_LESSON: Int = 10
    const val FINAL_LESSON: Int = 20
    const val MAX_COMBO_BONUS: Int = 5
}

/** What a completed lesson awarded (for the completion UI). */
data class LessonRewards(
    val xpEarned: Int,
    val dayTotalXp: Int,
    val dailyGoalMet: Boolean,
    val streakAdvanced: Boolean,
)

/**
 * Awards XP for a completed lesson and advances the daily goal + streak (SPEC §7 step 6, §9).
 * This is the gamification hook the lesson flow (P1.4) calls on completion — it deliberately
 * lives here, not in [com.magicalhippie.aprende.domain.session.LessonSession], so the session
 * stays decoupled from gamification.
 */
class AwardLessonRewardsUseCase @Inject constructor(
    private val progress: ProgressRepository,
    private val settings: SettingsRepository,
    private val streak: StreakUseCase,
    private val clock: Clock,
) {
    suspend fun award(xpEarned: Int): LessonRewards {
        val today = LocalDate.now(clock).toString()
        val goalXp = settings.dailyGoalXp.first()

        val existing = progress.getDailyActivity(today)
        val dayTotal = (existing?.xpEarned ?: 0) + xpEarned
        val goalMet = dayTotal >= goalXp
        val goalNewlyMet = goalMet && existing?.goalMet != true
        progress.upsertDailyActivity(DailyActivity(localDate = today, xpEarned = dayTotal, goalMet = goalMet))

        val stats = progress.getUserStats() ?: NEW_USER_STATS
        progress.upsertUserStats(stats.copy(totalXp = stats.totalXp + xpEarned))

        // Advancing the streak re-reads/writes stats AFTER the XP write, preserving totalXp.
        val streakAdvanced = if (goalNewlyMet) {
            streak.onDailyGoalMet()
            true
        } else {
            false
        }

        return LessonRewards(xpEarned = xpEarned, dayTotalXp = dayTotal, dailyGoalMet = goalMet, streakAdvanced = streakAdvanced)
    }
}

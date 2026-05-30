package com.magicalhippie.aprende.domain.gamification

import com.magicalhippie.aprende.domain.model.UserStats
import com.magicalhippie.aprende.domain.repository.ProgressRepository
import java.time.Clock
import java.time.LocalDate
import javax.inject.Inject

/**
 * Pure streak math (SPEC §9, §12.3): the streak advances when the daily goal is met. A missed
 * day breaks the streak UNLESS enough streak freezes are available to cover the gap (each
 * freeze covers one missed day). Day identity is the local date (epoch-day), computed against
 * an injected clock — so it is testable across midnight/DST and resists clock-rollback.
 */
object Streak {
    /**
     * Apply "the daily goal was met on [today]" to [stats]. Returns updated stats:
     *  - first ever goal → streak 1
     *  - already counted today, or [today] before the last active day (clock anomaly, §6.7) → unchanged
     *  - consecutive day → streak + 1
     *  - gap with enough freezes → streak + 1, freezes -= missed days
     *  - gap without enough freezes → streak resets to 1
     */
    fun applyGoalMet(stats: UserStats, today: LocalDate): UserStats {
        val last = stats.lastActiveLocalDate?.let(LocalDate::parse)
            ?: return stats.copy(streakLength = 1, lastActiveLocalDate = today.toString())
        if (!today.isAfter(last)) return stats // already counted today, or clock moved backward
        val gap = today.toEpochDay() - last.toEpochDay()
        if (gap == 1L) {
            return stats.copy(streakLength = stats.streakLength + 1, lastActiveLocalDate = today.toString())
        }
        val missedDays = (gap - 1).toInt()
        return if (stats.streakFreezes >= missedDays) {
            stats.copy(
                streakLength = stats.streakLength + 1,
                streakFreezes = stats.streakFreezes - missedDays,
                lastActiveLocalDate = today.toString(),
            )
        } else {
            stats.copy(streakLength = 1, lastActiveLocalDate = today.toString())
        }
    }
}

/** Advances the streak when today's goal is newly met (called by [AwardLessonRewardsUseCase]). */
class StreakUseCase @Inject constructor(
    private val progress: ProgressRepository,
    private val clock: Clock,
) {
    suspend fun onDailyGoalMet(): UserStats {
        val today = LocalDate.now(clock)
        val updated = Streak.applyGoalMet(progress.getUserStats() ?: NEW_USER_STATS, today)
        progress.upsertUserStats(updated)
        return updated
    }
}

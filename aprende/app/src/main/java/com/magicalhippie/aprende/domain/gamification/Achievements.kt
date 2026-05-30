package com.magicalhippie.aprende.domain.gamification

import com.magicalhippie.aprende.domain.repository.ProgressRepository
import java.time.Clock
import javax.inject.Inject

/** The learner counter an achievement tracks (SPEC §9). */
enum class AchievementMetric { STREAK_DAYS, WORDS_LEARNED, TOTAL_XP }

/** A 10-level achievement: each threshold the metric crosses unlocks the next level. */
data class AchievementDef(
    val id: String,
    val metric: AchievementMetric,
    val thresholds: List<Int>,
)

/** An achievement whose level just increased. */
data class UnlockedAchievement(val id: String, val level: Int)

/**
 * Achievement definitions + pure level computation (SPEC §9). Tiers mirror Duolingo's
 * 10-level achievements (e.g. Wildfire streak 3→365, Word Collector 50→2000, XP Olympian
 * 100→30000). All client-evaluable from local counters.
 */
object Achievements {
    val DEFINITIONS: List<AchievementDef> = listOf(
        AchievementDef("wildfire", AchievementMetric.STREAK_DAYS, listOf(3, 7, 14, 30, 50, 100, 150, 200, 300, 365)),
        AchievementDef("word_collector", AchievementMetric.WORDS_LEARNED, listOf(50, 100, 250, 500, 750, 1000, 1250, 1500, 1750, 2000)),
        AchievementDef("xp_olympian", AchievementMetric.TOTAL_XP, listOf(100, 500, 1000, 2000, 5000, 10000, 15000, 20000, 25000, 30000)),
    )

    /** The level a metric value reaches = number of thresholds met (0..thresholds.size). */
    fun levelFor(thresholds: List<Int>, value: Int): Int = thresholds.count { value >= it }
}

/**
 * Evaluates all achievements against the learner's current counters, persists any whose level
 * increased, and returns the newly-unlocked levels (for the celebration UI). Client-only.
 */
class EvaluateAchievementsUseCase @Inject constructor(
    private val progress: ProgressRepository,
    private val clock: Clock,
) {
    suspend fun evaluate(): List<UnlockedAchievement> {
        val stats = progress.getUserStats() ?: NEW_USER_STATS
        val unlocked = mutableListOf<UnlockedAchievement>()
        for (def in Achievements.DEFINITIONS) {
            val value = when (def.metric) {
                AchievementMetric.STREAK_DAYS -> stats.streakLength
                AchievementMetric.WORDS_LEARNED -> stats.wordsLearned
                AchievementMetric.TOTAL_XP -> stats.totalXp
            }
            val newLevel = Achievements.levelFor(def.thresholds, value)
            if (newLevel > progress.getAchievementLevel(def.id)) {
                progress.unlockAchievement(def.id, newLevel, clock.millis())
                unlocked.add(UnlockedAchievement(def.id, newLevel))
            }
        }
        return unlocked
    }
}

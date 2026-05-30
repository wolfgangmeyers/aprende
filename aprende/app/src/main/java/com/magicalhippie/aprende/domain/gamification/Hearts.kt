package com.magicalhippie.aprende.domain.gamification

import com.magicalhippie.aprende.domain.model.UserStats
import com.magicalhippie.aprende.domain.repository.ProgressRepository
import java.time.Clock
import javax.inject.Inject
import kotlin.math.max
import kotlin.math.min

/**
 * Pure heart math (SPEC §9): a free learner has 5 hearts, loses one per mistake, and
 * regenerates one roughly every 5 hours. Regen is **lazy** (SPEC §6.5): current hearts are
 * derived from the stored count + elapsed time since [UserStats.heartsLostAtMillis] — never a
 * background job. `heartsLostAtMillis == null` means "at full".
 */
object Hearts {
    const val MAX: Int = 5
    const val REGEN_INTERVAL_MILLIS: Long = 5L * 60 * 60 * 1000 // ~5 hours
    const val GEM_REFILL_COST: Int = 350

    /** Current hearts now, banking lazy regeneration since the last loss. */
    fun current(stats: UserStats, nowMillis: Long): Int {
        val anchor = stats.heartsLostAtMillis ?: return MAX
        val regenerated = stats.hearts + ((nowMillis - anchor) / REGEN_INTERVAL_MILLIS).toInt()
        return min(MAX, max(0, regenerated))
    }

    fun loseOne(stats: UserStats, nowMillis: Long): UserStats {
        val next = max(0, current(stats, nowMillis) - 1)
        return stats.copy(hearts = next, heartsLostAtMillis = if (next >= MAX) null else nowMillis)
    }

    /** +1 heart (e.g. from completing a practice session). */
    fun gainOne(stats: UserStats, nowMillis: Long): UserStats {
        val next = min(MAX, current(stats, nowMillis) + 1)
        return stats.copy(hearts = next, heartsLostAtMillis = if (next >= MAX) null else nowMillis)
    }

    fun fullRefill(stats: UserStats): UserStats = stats.copy(hearts = MAX, heartsLostAtMillis = null)
}

/**
 * Hearts operations against persisted state (SPEC §9). The lesson flow gates on [hasHearts]
 * and calls [loseHeart] on each mistake; practice completion calls [refillOneFromPractice];
 * the shop calls [refillFullWithGems].
 */
class HeartsUseCase @Inject constructor(
    private val progress: ProgressRepository,
    private val clock: Clock,
) {
    suspend fun currentHearts(): Int = Hearts.current(stats(), clock.millis())

    suspend fun hasHearts(): Boolean = currentHearts() > 0

    suspend fun loseHeart(): Int {
        val updated = Hearts.loseOne(stats(), clock.millis())
        progress.upsertUserStats(updated)
        return Hearts.current(updated, clock.millis())
    }

    suspend fun refillOneFromPractice(): Int {
        val updated = Hearts.gainOne(stats(), clock.millis())
        progress.upsertUserStats(updated)
        return Hearts.current(updated, clock.millis())
    }

    /** Full refill for gems; returns false (no change) if the learner can't afford it. */
    suspend fun refillFullWithGems(): Boolean {
        val s = stats()
        if (s.gems < Hearts.GEM_REFILL_COST) return false
        progress.upsertUserStats(Hearts.fullRefill(s).copy(gems = s.gems - Hearts.GEM_REFILL_COST))
        return true
    }

    private suspend fun stats(): UserStats = progress.getUserStats() ?: NEW_USER_STATS
}

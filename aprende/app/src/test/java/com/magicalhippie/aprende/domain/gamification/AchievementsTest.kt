package com.magicalhippie.aprende.domain.gamification

import com.magicalhippie.aprende.domain.FakeProgressRepository
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset

class AchievementsTest {

    private val clock = Clock.fixed(Instant.parse("2026-01-01T12:00:00Z"), ZoneOffset.UTC)

    @Test
    fun `level equals the number of thresholds met`() {
        val thresholds = listOf(3, 7, 14, 30)
        assertEquals(0, Achievements.levelFor(thresholds, 2))
        assertEquals(1, Achievements.levelFor(thresholds, 3))
        assertEquals(2, Achievements.levelFor(thresholds, 13))
        assertEquals(4, Achievements.levelFor(thresholds, 100))
    }

    @Test
    fun `evaluation unlocks newly-reached levels and is idempotent`() = runTest {
        val repo = FakeProgressRepository()
        // streak 7 -> wildfire level 2 (3,7 met); 60 words -> word_collector level 1 (50 met)
        repo.upsertUserStats(NEW_USER_STATS.copy(streakLength = 7, wordsLearned = 60, totalXp = 50))
        val useCase = EvaluateAchievementsUseCase(repo, clock)

        val unlocked = useCase.evaluate()
        assertTrue(unlocked.any { it.id == "wildfire" && it.level == 2 })
        assertTrue(unlocked.any { it.id == "word_collector" && it.level == 1 })
        assertEquals(2, repo.getAchievementLevel("wildfire"))

        // Re-evaluating with no counter change unlocks nothing new.
        assertTrue("idempotent", useCase.evaluate().isEmpty())
    }
}

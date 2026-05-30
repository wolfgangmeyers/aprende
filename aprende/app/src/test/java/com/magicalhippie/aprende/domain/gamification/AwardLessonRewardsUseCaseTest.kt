package com.magicalhippie.aprende.domain.gamification

import com.magicalhippie.aprende.domain.FakeProgressRepository
import com.magicalhippie.aprende.domain.FakeSettingsRepository
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset

/** XP award + daily goal + streak advance on lesson completion (SPEC §7 step 6, §9). */
class AwardLessonRewardsUseCaseTest {

    private val clock = Clock.fixed(Instant.parse("2026-01-01T12:00:00Z"), ZoneOffset.UTC)
    private val repo = FakeProgressRepository()
    private val settings = FakeSettingsRepository(dailyGoal = 20)
    private val useCase = AwardLessonRewardsUseCase(repo, settings, StreakUseCase(repo, clock), clock)

    @Test
    fun `xp accumulates and the streak advances only when the daily goal is newly met`() = runTest {
        val first = useCase.award(Xp.STANDARD_LESSON) // 10 of 20
        assertEquals(10, first.dayTotalXp)
        assertFalse("goal not met yet", first.dailyGoalMet)
        assertFalse(first.streakAdvanced)
        assertEquals(0, repo.getUserStats()!!.streakLength)

        val second = useCase.award(Xp.STANDARD_LESSON) // 20 of 20 -> met
        assertEquals(20, second.dayTotalXp)
        assertTrue(second.dailyGoalMet)
        assertTrue("streak advances on the newly-met goal", second.streakAdvanced)

        val stats = repo.getUserStats()!!
        assertEquals(20, stats.totalXp)
        assertEquals(1, stats.streakLength)
        assertTrue(repo.getDailyActivity("2026-01-01")!!.goalMet)
    }

    @Test
    fun `meeting the goal again the same day does not advance the streak twice`() = runTest {
        useCase.award(20) // meets goal -> streak 1
        val again = useCase.award(10) // already met today
        assertFalse(again.streakAdvanced)
        assertEquals(1, repo.getUserStats()!!.streakLength)
        assertEquals(30, repo.getUserStats()!!.totalXp)
    }
}

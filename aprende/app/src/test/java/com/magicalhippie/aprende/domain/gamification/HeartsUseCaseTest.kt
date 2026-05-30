package com.magicalhippie.aprende.domain.gamification

import com.magicalhippie.aprende.domain.FakeProgressRepository
import com.magicalhippie.aprende.domain.MutableClock
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** AC8: hearts gate after 5 mistakes, lazy regeneration, practice refill, gem refill. */
class HeartsUseCaseTest {

    private val clock = MutableClock()
    private val repo = FakeProgressRepository()
    private val hearts = HeartsUseCase(repo, clock)

    @Test
    fun `a fresh learner has five hearts`() = runTest {
        assertEquals(5, hearts.currentHearts())
        assertTrue(hearts.hasHearts())
    }

    @Test
    fun `AC8 - five mistakes exhaust hearts and gate the session`() = runTest {
        repeat(5) { hearts.loseHeart() }
        assertEquals(0, hearts.currentHearts())
        assertFalse(hearts.hasHearts())
    }

    @Test
    fun `AC8 - hearts regenerate lazily, one per interval`() = runTest {
        repeat(5) { hearts.loseHeart() }
        assertEquals(0, hearts.currentHearts())
        clock.advanceMillis(Hearts.REGEN_INTERVAL_MILLIS)
        assertEquals(1, hearts.currentHearts())
        clock.advanceMillis(2 * Hearts.REGEN_INTERVAL_MILLIS)
        assertEquals(3, hearts.currentHearts())
    }

    @Test
    fun `AC8 - completing a practice refills one heart`() = runTest {
        repeat(3) { hearts.loseHeart() } // 5 -> 2
        assertEquals(2, hearts.currentHearts())
        hearts.refillOneFromPractice()
        assertEquals(3, hearts.currentHearts())
    }

    @Test
    fun `gem refill needs enough gems and refills to full`() = runTest {
        // Not enough gems -> no change.
        repeat(3) { hearts.loseHeart() }
        assertFalse(hearts.refillFullWithGems())
        assertEquals(2, hearts.currentHearts())

        // Top up gems, then a full refill succeeds and debits the cost.
        repo.upsertUserStats(repo.getUserStats()!!.copy(gems = Hearts.GEM_REFILL_COST))
        assertTrue(hearts.refillFullWithGems())
        assertEquals(5, hearts.currentHearts())
        assertEquals(0, repo.getUserStats()!!.gems)
    }
}

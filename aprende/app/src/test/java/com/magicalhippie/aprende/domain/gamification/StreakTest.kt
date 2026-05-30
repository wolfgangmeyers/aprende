package com.magicalhippie.aprende.domain.gamification

import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.LocalDate

/** AC13: the streak survives a missed day iff a freeze covers it (and the freeze is consumed). */
class StreakTest {

    private fun stats(streak: Int, freezes: Int, lastActive: String?) =
        NEW_USER_STATS.copy(streakLength = streak, streakFreezes = freezes, lastActiveLocalDate = lastActive)

    private fun d(s: String) = LocalDate.parse(s)

    @Test
    fun `first goal sets streak to one`() {
        val r = Streak.applyGoalMet(stats(0, 0, null), d("2026-01-01"))
        assertEquals(1, r.streakLength)
        assertEquals("2026-01-01", r.lastActiveLocalDate)
    }

    @Test
    fun `a consecutive day increments the streak`() {
        val r = Streak.applyGoalMet(stats(5, 0, "2026-01-01"), d("2026-01-02"))
        assertEquals(6, r.streakLength)
    }

    @Test
    fun `same-day goal does not double-count`() {
        val r = Streak.applyGoalMet(stats(5, 1, "2026-01-03"), d("2026-01-03"))
        assertEquals(5, r.streakLength)
        assertEquals(1, r.streakFreezes)
    }

    @Test
    fun `AC13 - one missed day with a freeze keeps the streak and consumes the freeze`() {
        val r = Streak.applyGoalMet(stats(5, 1, "2026-01-01"), d("2026-01-03")) // missed Jan 2
        assertEquals(6, r.streakLength)
        assertEquals(0, r.streakFreezes)
    }

    @Test
    fun `AC13 - one missed day without a freeze resets the streak`() {
        val r = Streak.applyGoalMet(stats(5, 0, "2026-01-01"), d("2026-01-03"))
        assertEquals(1, r.streakLength)
    }

    @Test
    fun `two missed days need two freezes`() {
        val reset = Streak.applyGoalMet(stats(5, 1, "2026-01-01"), d("2026-01-04"))
        assertEquals("one freeze cannot cover two missed days", 1, reset.streakLength)
        val kept = Streak.applyGoalMet(stats(5, 2, "2026-01-01"), d("2026-01-04"))
        assertEquals(6, kept.streakLength)
        assertEquals(0, kept.streakFreezes)
    }

    @Test
    fun `a backward clock does not alter the streak (tamper guard)`() {
        val r = Streak.applyGoalMet(stats(5, 1, "2026-01-10"), d("2026-01-05"))
        assertEquals(5, r.streakLength)
        assertEquals("2026-01-10", r.lastActiveLocalDate)
    }
}

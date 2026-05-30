package com.magicalhippie.aprende.domain.srs

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset

/**
 * Grade derivation (SPEC §6.4) and use-case wiring, with a fixed [Clock] so timestamps
 * are deterministic (SPEC §12.3).
 */
class ScheduleReviewUseCaseTest {

    private val now = Instant.parse("2026-01-01T12:00:00Z")
    private val clock = Clock.fixed(now, ZoneOffset.UTC)
    private val useCase = ScheduleReviewUseCase(clock, Fsrs())

    @Test
    fun `clean correct answer grades Good`() {
        assertEquals(FsrsRating.GOOD, useCase.gradeFor(ExerciseOutcome(correct = true)))
    }

    @Test
    fun `correct with a hint grades Hard`() {
        assertEquals(FsrsRating.HARD, useCase.gradeFor(ExerciseOutcome(correct = true, usedHint = true)))
    }

    @Test
    fun `correct with a forgiven typo grades Hard`() {
        assertEquals(FsrsRating.HARD, useCase.gradeFor(ExerciseOutcome(correct = true, forgivenTypo = true)))
    }

    @Test
    fun `any wrong answer grades Again — even if a hint was used`() {
        assertEquals(FsrsRating.AGAIN, useCase.gradeFor(ExerciseOutcome(correct = false)))
        assertEquals(FsrsRating.AGAIN, useCase.gradeFor(ExerciseOutcome(correct = false, usedHint = true)))
    }

    @Test
    fun `first review stamps the clock's now and uses the Good initial state`() {
        val state = useCase.review(previous = null, outcome = ExerciseOutcome(correct = true))
        assertEquals(now.toEpochMilli(), state.lastReviewMillis)
        assertEquals(2.3065, state.stability, 1e-6) // Good initial stability
    }

    @Test
    fun `a clean correct first answer schedules later than a wrong first answer (AC5)`() {
        val correct = useCase.review(previous = null, outcome = ExerciseOutcome(correct = true))
        val wrong = useCase.review(previous = null, outcome = ExerciseOutcome(correct = false))
        assertTrue(
            "Good first review must be due later than Again first review",
            correct.dueAtMillis > wrong.dueAtMillis,
        )
        assertTrue("Good initial stability exceeds Again's", correct.stability > wrong.stability)
    }
}

package com.magicalhippie.aprende.domain.srs

import com.magicalhippie.aprende.domain.FakeProgressRepository
import com.magicalhippie.aprende.domain.model.ItemType
import com.magicalhippie.aprende.domain.model.SrsState
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Clock
import java.time.Instant
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.temporal.ChronoUnit

/** A test [Clock] whose instant can be advanced (FSRS stability only grows when time elapses). */
private class MutableClock(var instant: Instant, private val zone: ZoneId = ZoneOffset.UTC) : Clock() {
    override fun instant(): Instant = instant
    override fun getZone(): ZoneId = zone
    override fun withZone(z: ZoneId): Clock = MutableClock(instant, z)
    fun advanceDays(days: Long) { instant = instant.plus(days, ChronoUnit.DAYS) }
}

/** P1.3: recording an answer updates the target item's SRS state (fan-out rule §6.4a). */
class RecordAnswerUseCaseTest {

    private val start = Instant.parse("2026-01-01T12:00:00Z")
    private val clock = MutableClock(start)
    private val repo = FakeProgressRepository()
    private val useCase = RecordAnswerUseCase(repo, ScheduleReviewUseCase(clock, Fsrs()))

    @Test
    fun `first correct answer creates a Learning item with incremented counters`() = runTest {
        val item = useCase.record(targetItemId = 1, targetItemType = ItemType.LEXEME, outcome = ExerciseOutcome(correct = true))
        assertEquals(SrsState.LEARNING, item.lifecycle)
        assertEquals(1, item.timesSeen)
        assertEquals(1, item.timesCorrect)
        assertEquals(0, item.timesWrong)
        assertEquals(2.3065, item.state.stability, 1e-6) // Good initial
        assertTrue("due in the future", item.state.dueAtMillis > start.toEpochMilli())
        assertEquals(item, repo.getSrsItem(1, ItemType.LEXEME))
    }

    @Test
    fun `a wrong answer marks the item Relearning and counts a miss`() = runTest {
        val item = useCase.record(1, ItemType.LEXEME, ExerciseOutcome(correct = false))
        assertEquals(SrsState.RELEARNING, item.lifecycle)
        assertEquals(1, item.timesWrong)
        assertEquals(0, item.timesCorrect)
    }

    @Test
    fun `recording the target item does NOT touch other items (fan-out rule)`() = runTest {
        useCase.record(1, ItemType.LEXEME, ExerciseOutcome(correct = true))
        assertEquals(1, repo.srsCount())
        assertNull("incidental item 2 must be untouched", repo.getSrsItem(2, ItemType.LEXEME))
    }

    @Test
    fun `a later correct review advances to Review and grows stability`() = runTest {
        val first = useCase.record(1, ItemType.LEXEME, ExerciseOutcome(correct = true))
        clock.advanceDays(2) // FSRS recall stability only grows when time has elapsed (R < 1)
        val second = useCase.record(1, ItemType.LEXEME, ExerciseOutcome(correct = true))
        assertEquals(SrsState.REVIEW, second.lifecycle)
        assertEquals(2, second.timesSeen)
        assertTrue("stability grows on a spaced successful recall", second.state.stability > first.state.stability)
    }
}

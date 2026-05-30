package com.magicalhippie.aprende.domain.session

import com.magicalhippie.aprende.domain.FakeProgressRepository
import com.magicalhippie.aprende.domain.exercise
import com.magicalhippie.aprende.domain.grading.GradeResult
import com.magicalhippie.aprende.domain.grading.GradeVerdict
import com.magicalhippie.aprende.domain.model.ItemType
import com.magicalhippie.aprende.domain.srs.Fsrs
import com.magicalhippie.aprende.domain.srs.RecordAnswerUseCase
import com.magicalhippie.aprende.domain.srs.ScheduleReviewUseCase
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset

class LessonSessionTest {

    private val clock = Clock.fixed(Instant.parse("2026-01-01T12:00:00Z"), ZoneOffset.UTC)
    private val correct = GradeResult(GradeVerdict.CORRECT)
    private val wrong = GradeResult(GradeVerdict.WRONG)

    private fun factory(progress: FakeProgressRepository) =
        LessonSessionFactory(RecordAnswerUseCase(progress, ScheduleReviewUseCase(clock, Fsrs())), progress, clock)

    private fun plan(vararg ids: Long): LessonPlan {
        val exercises = ids.map { exercise(id = it * 10, targetItemId = it) }
        return LessonPlan(exercises, exercises.mapTo(HashSet()) { it.exerciseId })
    }

    @Test
    fun `an all-correct session completes after exactly the planned number of answers`() = runTest {
        val progress = FakeProgressRepository()
        val session = factory(progress).create(plan(1, 2))

        assertFalse(session.isComplete)
        val r1 = session.submit(correct)
        assertFalse("not complete after first of two", r1.complete)
        val r2 = session.submit(correct)
        assertTrue("complete after second", r2.complete)

        assertTrue(session.isComplete)
        assertEquals(2, session.presentedCount)
        assertEquals(0, session.mistakesMade)
        // SRS updated for both target items.
        assertNotNull(progress.getSrsItem(1, ItemType.LEXEME))
        assertNotNull(progress.getSrsItem(2, ItemType.LEXEME))
    }

    @Test
    fun `a wrong answer re-queues the exercise (dynamic length) and records a mistake (AC7)`() = runTest {
        val progress = FakeProgressRepository()
        val session = factory(progress).create(plan(1))

        val r1 = session.submit(wrong)
        assertFalse(r1.complete)
        assertTrue("wrong answer re-queued", r1.requeued)
        assertFalse(session.isComplete)
        assertEquals(1, session.mistakesMade)
        // AC7: the mistake is captured in the persistent queue.
        assertEquals(1, progress.allMistakes().size)
        assertEquals(10L, progress.allMistakes().first().exerciseId)

        // The same exercise is presented again and answered correctly -> session ends.
        val r2 = session.submit(correct)
        assertTrue("complete once the re-queued item is answered correctly", r2.complete)
        assertEquals("1 planned but 2 presented (dynamic length)", 2, session.presentedCount)

        // SRS saw both attempts on the same target item.
        val srs = progress.getSrsItem(1, ItemType.LEXEME)!!
        assertEquals(2, srs.timesSeen)
        assertEquals(1, srs.timesWrong)
        assertEquals(1, srs.timesCorrect)
    }

    @Test
    fun `summary reflects the planned vs presented counts`() = runTest {
        val progress = FakeProgressRepository()
        val session = factory(progress).create(plan(1, 2))
        session.submit(wrong)    // item 1 wrong -> requeued
        session.submit(correct)  // item 2 correct
        session.submit(correct)  // item 1 correct -> complete
        val s = session.summary()
        assertEquals(2, s.plannedCount)
        assertEquals(3, s.presentedCount)
        assertEquals(1, s.mistakesMade)
        assertTrue(s.completed)
    }
}

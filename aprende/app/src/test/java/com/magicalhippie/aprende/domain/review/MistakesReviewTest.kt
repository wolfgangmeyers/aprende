package com.magicalhippie.aprende.domain.review

import com.magicalhippie.aprende.domain.FakeContentRepository
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
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset

/** AC7: a lesson mistake reappears in a Mistakes review and leaves the queue when fixed. */
class MistakesReviewTest {

    private val clock = Clock.fixed(Instant.parse("2026-01-01T12:00:00Z"), ZoneOffset.UTC)
    private val correct = GradeResult(GradeVerdict.CORRECT)
    private val wrong = GradeResult(GradeVerdict.WRONG)

    private val content = FakeContentRepository(
        exercisesByNode = mapOf(1L to listOf(exercise(id = 10, targetItemId = 1))),
    )

    private fun recordAnswer(progress: FakeProgressRepository) =
        RecordAnswerUseCase(progress, ScheduleReviewUseCase(clock, Fsrs()))

    @Test
    fun `a queued mistake appears in the review and is cleared on a correct answer (AC7)`() = runTest {
        val progress = FakeProgressRepository()
        progress.enqueueMistake(exerciseId = 10, itemId = 1, itemType = ItemType.LEXEME, missedAtMillis = 0L)

        val plan = GenerateMistakesReviewUseCase(progress, content).generate()
        assertEquals("the mistake's exercise appears in the review", 1, plan.size)
        assertEquals(1, progress.allMistakes().size) // peeked, not yet cleared

        val session = MistakesReviewSessionFactory(recordAnswer(progress), progress).create(plan)
        val result = session.submit(correct)

        assertTrue(result.complete)
        assertEquals(1, session.clearedCount)
        assertTrue("the fixed mistake left the queue", progress.allMistakes().isEmpty())
    }

    @Test
    fun `a wrong answer keeps the mistake until it is answered correctly`() = runTest {
        val progress = FakeProgressRepository()
        progress.enqueueMistake(exerciseId = 10, itemId = 1, itemType = ItemType.LEXEME, missedAtMillis = 0L)
        val plan = GenerateMistakesReviewUseCase(progress, content).generate()
        val session = MistakesReviewSessionFactory(recordAnswer(progress), progress).create(plan)

        val first = session.submit(wrong)
        assertFalse(first.complete)
        assertTrue(first.requeued)
        assertEquals("still queued after a wrong attempt", 1, progress.allMistakes().size)

        val second = session.submit(correct)
        assertTrue(second.complete)
        assertTrue(progress.allMistakes().isEmpty())
    }

    @Test
    fun `an orphaned mistake (missing exercise) is cleared, not stuck`() = runTest {
        val progress = FakeProgressRepository()
        progress.enqueueMistake(exerciseId = 999, itemId = 1, itemType = ItemType.LEXEME, missedAtMillis = 0L)
        val plan = GenerateMistakesReviewUseCase(progress, content).generate()
        assertEquals(0, plan.size)
        assertTrue("orphan cleared from the queue", progress.allMistakes().isEmpty())
    }
}

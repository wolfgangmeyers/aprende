package com.magicalhippie.aprende.ui.review

import com.magicalhippie.aprende.domain.FakeContentRepository
import com.magicalhippie.aprende.domain.FakeProgressRepository
import com.magicalhippie.aprende.domain.exercise
import com.magicalhippie.aprende.domain.grading.GradeAnswerUseCase
import com.magicalhippie.aprende.domain.model.ItemType
import com.magicalhippie.aprende.domain.model.SentenceText
import com.magicalhippie.aprende.domain.review.GenerateMistakesReviewUseCase
import com.magicalhippie.aprende.domain.review.MistakesReviewSessionFactory
import com.magicalhippie.aprende.domain.srs.Fsrs
import com.magicalhippie.aprende.domain.srs.RecordAnswerUseCase
import com.magicalhippie.aprende.domain.srs.ScheduleReviewUseCase
import com.magicalhippie.aprende.ui.lesson.Feedback
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset

/**
 * ViewModel test for the Mistakes-review screen (P1.7, AC7 in the UI). Drives
 * [MistakesReviewViewModel] over the in-memory fakes: a queued mistake is presented, a correct
 * typed answer clears it from the persistent queue, and the VM reports completion + cleared count.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class MistakesReviewViewModelTest {

    private val dispatcher = StandardTestDispatcher()
    private val clock = Clock.fixed(Instant.parse("2026-01-01T12:00:00Z"), ZoneOffset.UTC)

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    private fun content() = FakeContentRepository(
        exercisesByNode = mapOf(1L to listOf(exercise(id = 10, targetItemId = 1))),
        acceptedAnswers = mapOf((10L to "ES_TO_EN") to listOf("I have a dog")),
        sentences = mapOf(10L to SentenceText(10, "Tengo un perro.", "I have a dog.")),
    )

    private fun vm(progress: FakeProgressRepository, content: FakeContentRepository): MistakesReviewViewModel {
        val record = RecordAnswerUseCase(progress, ScheduleReviewUseCase(clock, Fsrs()))
        return MistakesReviewViewModel(
            generate = GenerateMistakesReviewUseCase(progress, content),
            sessionFactory = MistakesReviewSessionFactory(record, progress),
            content = content,
            grader = GradeAnswerUseCase(),
        )
    }

    @Test
    fun `correct answer clears the queued mistake and completes (AC7)`() = runTest(dispatcher) {
        val progress = FakeProgressRepository()
        progress.enqueueMistake(exerciseId = 10, itemId = 1, itemType = ItemType.LEXEME, missedAtMillis = 0L)
        val viewModel = vm(progress, content())
        advanceUntilIdle()

        // The queued mistake is presented as a typed exercise.
        assertEquals("Tengo un perro.", viewModel.uiState.value.prompt)

        viewModel.onTypedInputChange("I have a dog")
        viewModel.submit()
        advanceUntilIdle()

        assertEquals(Feedback.CORRECT, viewModel.uiState.value.feedback)
        assertTrue("mistake left the queue (AC7)", progress.allMistakes().isEmpty())

        viewModel.onContinue()
        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertTrue(state.complete)
        assertEquals(1, state.clearedCount)
    }

    @Test
    fun `empty queue shows the no-mistakes completion state`() = runTest(dispatcher) {
        val progress = FakeProgressRepository()
        val viewModel = vm(progress, content())
        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertTrue(state.complete)
        assertTrue(state.empty)
    }
}

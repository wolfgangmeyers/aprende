package com.magicalhippie.aprende.ui.lesson

import androidx.lifecycle.SavedStateHandle
import com.magicalhippie.aprende.domain.FakeContentRepository
import com.magicalhippie.aprende.domain.FakeProgressRepository
import com.magicalhippie.aprende.domain.FakeSettingsRepository
import com.magicalhippie.aprende.domain.MutableClock
import com.magicalhippie.aprende.domain.exercise
import com.magicalhippie.aprende.domain.gamification.AwardLessonRewardsUseCase
import com.magicalhippie.aprende.domain.gamification.EvaluateAchievementsUseCase
import com.magicalhippie.aprende.domain.gamification.HeartsUseCase
import com.magicalhippie.aprende.domain.gamification.StreakUseCase
import com.magicalhippie.aprende.domain.grading.GradeAnswerUseCase
import com.magicalhippie.aprende.domain.model.SentenceText
import com.magicalhippie.aprende.domain.session.CompleteNodeUseCase
import com.magicalhippie.aprende.domain.session.GenerateLessonUseCase
import com.magicalhippie.aprende.domain.session.LessonSessionFactory
import com.magicalhippie.aprende.domain.srs.Fsrs
import com.magicalhippie.aprende.domain.srs.RecordAnswerUseCase
import com.magicalhippie.aprende.domain.srs.ScheduleReviewUseCase
import com.magicalhippie.aprende.ui.navigation.Routes
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

/**
 * AC12 — process-death survival. Drives the lesson partway, then constructs a brand-new
 * [LessonViewModel] from the SAME [SavedStateHandle] (exactly what the framework does after a
 * system-initiated process death, §12.3) and asserts the new ViewModel resumes the same
 * exercise position and the same in-progress typed input — proving the durable in-session
 * snapshot (current queue + input) round-trips through the Bundle-backed handle.
 */
class LessonViewModelSavedStateTest {

    private val testDispatcher = StandardTestDispatcher()

    @Before fun setUp() { Dispatchers.setMain(testDispatcher) }
    @After fun tearDown() { Dispatchers.resetMain() }

    @Test
    fun `new ViewModel from same SavedStateHandle resumes the same exercise and input`() =
        runTest(testDispatcher) {
            val handle = SavedStateHandle(mapOf(Routes.ARG_NODE_ID to 1L))

            // First instance: complete the first exercise correctly, then type into the second.
            val vm1 = newViewModel(handle)
            runCurrent()
            val firstPrompt = vm1.uiState.value.prompt

            vm1.onTypedInputChange("i have a dog")
            vm1.submit(); runCurrent()
            vm1.onContinue(); runCurrent()

            val secondPrompt = vm1.uiState.value.prompt
            assertEquals("El agua está fría.", secondPrompt)
            vm1.onTypedInputChange("partial answ") // in-progress, NOT submitted

            // Simulate process death: a fresh ViewModel rehydrates from the same handle.
            val vm2 = newViewModel(handle)
            runCurrent()

            assertEquals("resumes same exercise", secondPrompt, vm2.uiState.value.prompt)
            assertEquals("restores in-progress input", "partial answ", vm2.uiState.value.typedInput)
            // It did NOT restart at the first exercise.
            assertEquals(false, vm2.uiState.value.prompt == firstPrompt)
        }

    @Test
    fun `english to spanish exercise prompts with English and grades Spanish answer`() =
        runTest(testDispatcher) {
            val handle = SavedStateHandle(mapOf(Routes.ARG_NODE_ID to 1L))
            val vm = newViewModel(
                handle,
                exercises = listOf(
                    exercise(id = 1, targetItemId = 1, type = "TYPED_TRANSLATION")
                        .copy(sentenceId = 1, direction = "EN_TO_ES"),
                ),
                acceptedAnswers = mapOf((1L to "EN_TO_ES") to listOf("tengo un perro")),
                sentences = mapOf(1L to SentenceText(1, "Tengo un perro.", "I have a dog.")),
            )
            runCurrent()

            assertEquals("I have a dog.", vm.uiState.value.prompt)
            assertEquals("Type this in Spanish", vm.uiState.value.instruction)

            vm.onTypedInputChange("Tengo un perro.")
            vm.submit()
            runCurrent()

            assertEquals(Feedback.CORRECT, vm.uiState.value.feedback)
        }

    @Test
    fun `multiple choice renders metadata options and grades by correct index`() =
        runTest(testDispatcher) {
            val handle = SavedStateHandle(mapOf(Routes.ARG_NODE_ID to 1L))
            val vm = newViewModel(
                handle,
                exercises = listOf(
                    exercise(id = 1, targetItemId = 1, type = "MULTIPLE_CHOICE").copy(
                        sentenceId = 1,
                        promptHint = """{"multipleChoice":{"choices":["we're going home","i have a dog","i want water","i have the water"],"correctIndex":1}}""",
                    ),
                ),
                acceptedAnswers = mapOf((1L to "ES_TO_EN") to listOf("i have a dog")),
                sentences = mapOf(1L to SentenceText(1, "Tengo un perro.", "I have a dog.")),
            )
            runCurrent()

            assertEquals("Tengo un perro.", vm.uiState.value.prompt)
            assertEquals(ExerciseKind.MULTIPLE_CHOICE, vm.uiState.value.kind)
            assertEquals(
                listOf("we're going home", "i have a dog", "i want water", "i have the water"),
                vm.uiState.value.choices,
            )
            assertEquals(1, vm.uiState.value.correctChoiceIndex)

            vm.onChoiceSelected(0)
            vm.submit()
            runCurrent()

            assertEquals(Feedback.INCORRECT, vm.uiState.value.feedback)

            vm.onContinue()
            runCurrent()
            vm.onChoiceSelected(1)
            vm.submit()
            runCurrent()

            assertEquals(Feedback.CORRECT, vm.uiState.value.feedback)
        }

    private fun newViewModel(
        handle: SavedStateHandle,
        exercises: List<com.magicalhippie.aprende.domain.model.Exercise> = listOf(
            exercise(id = 1, targetItemId = 1, type = "TYPED_TRANSLATION").copy(sentenceId = 1),
            exercise(id = 2, targetItemId = 2, type = "TYPED_TRANSLATION").copy(sentenceId = 2),
        ),
        acceptedAnswers: Map<Pair<Long, String>, List<String>> = mapOf(
            (1L to "ES_TO_EN") to listOf("i have a dog"),
            (2L to "ES_TO_EN") to listOf("the water is cold"),
        ),
        sentences: Map<Long, SentenceText> = mapOf(
            1L to SentenceText(1, "Tengo un perro.", "I have a dog."),
            2L to SentenceText(2, "El agua está fría.", "The water is cold."),
        ),
    ): LessonViewModel {
        val clock = MutableClock()
        val content = FakeContentRepository(
            exercisesByNode = mapOf(1L to exercises),
            acceptedAnswers = acceptedAnswers,
            sentences = sentences,
        )
        val progress = FakeProgressRepository()
        val settings = FakeSettingsRepository()
        val schedule = ScheduleReviewUseCase(clock, Fsrs())
        val record = RecordAnswerUseCase(progress, schedule)
        val factory = LessonSessionFactory(record, progress, clock)
        val streak = StreakUseCase(progress, clock)
        return LessonViewModel(
            savedState = handle,
            generateLesson = GenerateLessonUseCase(content, progress),
            sessionFactory = factory,
            content = content,
            progress = progress,
            grader = GradeAnswerUseCase(),
            hearts = HeartsUseCase(progress, clock),
            awardRewards = AwardLessonRewardsUseCase(progress, settings, streak, clock),
            evaluateAchievements = EvaluateAchievementsUseCase(progress, clock),
            completeNode = CompleteNodeUseCase(progress, clock),
        )
    }
}

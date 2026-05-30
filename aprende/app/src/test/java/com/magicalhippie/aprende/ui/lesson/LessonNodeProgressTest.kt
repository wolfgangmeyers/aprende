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
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Regression for the node-progression write (SPEC §7 step 6, §4.4): completing a lesson must
 * write `node_progress` for the Path node, so the node shows complete and the next node unlocks.
 */
class LessonNodeProgressTest {

    private val testDispatcher = StandardTestDispatcher()

    @Before fun setUp() { Dispatchers.setMain(testDispatcher) }
    @After fun tearDown() { Dispatchers.resetMain() }

    @Test
    fun `completing a lesson writes node_progress for the node`() = runTest(testDispatcher) {
        val clock = MutableClock()
        val content = FakeContentRepository(
            exercisesByNode = mapOf(
                1L to listOf(exercise(id = 1, targetItemId = 1, type = "TYPED_TRANSLATION").copy(sentenceId = 1)),
            ),
            acceptedAnswers = mapOf((1L to "ES_TO_EN") to listOf("i have a dog")),
            sentences = mapOf(1L to SentenceText(1, "Tengo un perro.", "I have a dog.")),
        )
        val progress = FakeProgressRepository()
        val settings = FakeSettingsRepository()
        val schedule = ScheduleReviewUseCase(clock, Fsrs())
        val record = RecordAnswerUseCase(progress, schedule)
        val vm = LessonViewModel(
            savedState = SavedStateHandle(mapOf(Routes.ARG_NODE_ID to 1L)),
            generateLesson = GenerateLessonUseCase(content, progress),
            sessionFactory = LessonSessionFactory(record, progress, clock),
            content = content,
            progress = progress,
            grader = GradeAnswerUseCase(),
            hearts = HeartsUseCase(progress, clock),
            awardRewards = AwardLessonRewardsUseCase(progress, settings, StreakUseCase(progress, clock), clock),
            evaluateAchievements = EvaluateAchievementsUseCase(progress, clock),
            completeNode = CompleteNodeUseCase(progress, clock),
        )
        runCurrent()
        assertNull("node not complete before finishing", progress.getNodeProgress(1))

        // Answer the only exercise correctly and advance past feedback → lesson completes.
        vm.onTypedInputChange("i have a dog")
        vm.submit(); runCurrent()
        vm.onContinue(); runCurrent()

        assertTrue("lesson finished", vm.uiState.value.finished)
        val np = progress.getNodeProgress(1)
        assertNotNull("node_progress written on lesson completion", np)
        assertEquals(1, np!!.level)
        assertNotNull("completion timestamp recorded", np.completedAtMillis)
    }

    @Test
    fun `answering mid-lesson does NOT write node_progress until the lesson finishes`() = runTest(testDispatcher) {
        val clock = MutableClock()
        val content = FakeContentRepository(
            exercisesByNode = mapOf(
                1L to listOf(
                    exercise(id = 1, targetItemId = 1, type = "TYPED_TRANSLATION").copy(sentenceId = 1),
                    exercise(id = 2, targetItemId = 2, type = "TYPED_TRANSLATION").copy(sentenceId = 2),
                ),
            ),
            acceptedAnswers = mapOf(
                (1L to "ES_TO_EN") to listOf("i have a dog"),
                (2L to "ES_TO_EN") to listOf("the water is cold"),
            ),
            sentences = mapOf(
                1L to SentenceText(1, "Tengo un perro.", "I have a dog."),
                2L to SentenceText(2, "El agua está fría.", "The water is cold."),
            ),
        )
        val progress = FakeProgressRepository()
        val clk = clock
        val record = RecordAnswerUseCase(progress, ScheduleReviewUseCase(clk, Fsrs()))
        val vm = LessonViewModel(
            savedState = SavedStateHandle(mapOf(Routes.ARG_NODE_ID to 1L)),
            generateLesson = GenerateLessonUseCase(content, progress),
            sessionFactory = LessonSessionFactory(record, progress, clk),
            content = content,
            progress = progress,
            grader = GradeAnswerUseCase(),
            hearts = HeartsUseCase(progress, clk),
            awardRewards = AwardLessonRewardsUseCase(progress, FakeSettingsRepository(), StreakUseCase(progress, clk), clk),
            evaluateAchievements = EvaluateAchievementsUseCase(progress, clk),
            completeNode = CompleteNodeUseCase(progress, clk),
        )
        runCurrent()

        // Answer the FIRST of two exercises and advance — the lesson is NOT finished yet.
        vm.onTypedInputChange("i have a dog")
        vm.submit(); runCurrent()
        vm.onContinue(); runCurrent()

        assertFalse("not finished after only the first exercise", vm.uiState.value.finished)
        assertNull("node_progress must NOT be written mid-lesson", progress.getNodeProgress(1))
    }
}

package com.magicalhippie.aprende

import androidx.lifecycle.SavedStateHandle
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.magicalhippie.aprende.data.content.ContentDatabase
import com.magicalhippie.aprende.data.content.ContentRepositoryImpl
import com.magicalhippie.aprende.data.progress.PROGRESS_MIGRATIONS
import com.magicalhippie.aprende.data.progress.ProgressDatabase
import com.magicalhippie.aprende.data.progress.ProgressRepositoryImpl
import com.magicalhippie.aprende.domain.repository.SettingsRepository
import com.magicalhippie.aprende.domain.gamification.AwardLessonRewardsUseCase
import com.magicalhippie.aprende.domain.gamification.EvaluateAchievementsUseCase
import com.magicalhippie.aprende.domain.gamification.HeartsUseCase
import com.magicalhippie.aprende.domain.gamification.StreakUseCase
import com.magicalhippie.aprende.domain.grading.GradeAnswerUseCase
import com.magicalhippie.aprende.domain.repository.ContentRepository
import com.magicalhippie.aprende.domain.repository.ProgressRepository
import com.magicalhippie.aprende.domain.session.CompleteNodeUseCase
import com.magicalhippie.aprende.domain.session.GenerateLessonUseCase
import com.magicalhippie.aprende.domain.session.LessonSessionFactory
import com.magicalhippie.aprende.domain.srs.Fsrs
import com.magicalhippie.aprende.domain.srs.RecordAnswerUseCase
import com.magicalhippie.aprende.domain.srs.ScheduleReviewUseCase
import com.magicalhippie.aprende.ui.lesson.Feedback
import com.magicalhippie.aprende.ui.lesson.LessonViewModel
import com.magicalhippie.aprende.ui.navigation.Routes
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset

/**
 * AC1 (headline E2E) — open the app and complete a full Tier-0 lesson FULLY OFFLINE, then
 * assert XP increased and the streak advanced.
 *
 * Why an instrumented (androidTest) test rather than Robolectric: this exercises the REAL
 * bundled `content.db` via Room `createFromAsset`, which needs the actual asset loader +
 * SQLite (awkward/unreliable under Robolectric). It uses NO network and NO TTS/STT — only the
 * Tier-0 typed/word-bank loop (SPEC §11.0) — so airplane mode would not change the outcome.
 *
 * It builds the dependency graph by hand (no Hilt) so the test is self-contained and
 * deterministic via a fixed [Clock]. `progress.db` is the real Room DB (in a temp instance).
 */
@RunWith(AndroidJUnit4::class)
class Ac1OfflineLessonE2ETest {

    private lateinit var contentDb: ContentDatabase
    private lateinit var progressDb: ProgressDatabase
    private val clock: Clock = Clock.fixed(Instant.parse("2026-03-01T12:00:00Z"), ZoneOffset.UTC)

    @Before
    fun setUp() {
        val ctx = ApplicationProvider.getApplicationContext<android.content.Context>()
        // The real bundled curriculum asset (createFromAsset) — the offline content source.
        contentDb = Room.databaseBuilder(ctx, ContentDatabase::class.java, "ac1_content.db")
            .createFromAsset("database/content.db")
            .fallbackToDestructiveMigration()
            .build()
        // Real progress DB (fresh instance for the test).
        progressDb = Room.inMemoryDatabaseBuilder(ctx, ProgressDatabase::class.java)
            .addMigrations(*PROGRESS_MIGRATIONS)
            .build()
    }

    @After
    fun tearDown() {
        contentDb.close()
        progressDb.close()
        ApplicationProvider.getApplicationContext<android.content.Context>()
            .deleteDatabase("ac1_content.db")
    }

    @Test
    fun completeTier0Lesson_offline_increasesXpAndAdvancesStreak() = runBlocking {
        val content: ContentRepository = ContentRepositoryImpl(
            lexemeDao = contentDb.lexemeDao(),
            exerciseDao = contentDb.exerciseDao(),
            conjugationDao = contentDb.conjugationDao(),
            nodeDao = contentDb.nodeDao(),
            acceptedAnswerDao = contentDb.acceptedAnswerDao(),
            sentenceDao = contentDb.sentenceDao(),
            attributionDao = contentDb.attributionDao(),
        )
        val progress: ProgressRepository = ProgressRepositoryImpl(
            srsItemDao = progressDb.srsItemDao(),
            mistakeDao = progressDb.mistakeDao(),
            dailyActivityDao = progressDb.dailyActivityDao(),
            userStatsDao = progressDb.userStatsDao(),
            achievementDao = progressDb.achievementDao(),
            nodeProgressDao = progressDb.nodeProgressDao(),
        )
        val settings: SettingsRepository = FixedSettings(dailyGoalXp = 10)

        // Sanity: there IS a bundled node + exercises to learn (offline content present).
        val nodes = content.nodes()
        assertTrue("bundled content.db must ship at least one node", nodes.isNotEmpty())
        val nodeId = nodes.first().nodeId

        val schedule = ScheduleReviewUseCase(clock, Fsrs())
        val record = RecordAnswerUseCase(progress, schedule)
        val factory = LessonSessionFactory(record, progress, clock)
        val streak = StreakUseCase(progress, clock)

        val vm = LessonViewModel(
            savedState = SavedStateHandle(mapOf(Routes.ARG_NODE_ID to nodeId)),
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

        // Drive the lesson to completion: for each exercise, answer correctly using the
        // vetted accepted answer, then continue. Guard with an upper bound for safety.
        var guard = 0
        while (!vm.uiState.value.finished && guard++ < 50) {
            waitUntilReady(vm)
            val state = vm.uiState.value
            if (state.finished) break
            answerCurrentCorrectly(vm, content)
            // submit -> feedback shown -> continue advances/completes.
            waitFor { vm.uiState.value.feedback != Feedback.NONE || vm.uiState.value.finished }
            if (!vm.uiState.value.finished) vm.onContinue()
        }

        assertTrue("lesson should complete offline", vm.uiState.value.finished)

        val stats = progress.getUserStats()!!
        assertTrue("XP increased", stats.totalXp > 0)
        assertEquals("XP equals one standard lesson", 10, stats.totalXp)
        assertTrue("streak advanced", stats.streakLength >= 1)
        assertEquals("completion UI shows XP", 10, vm.uiState.value.xpEarned)
        assertTrue("completion UI shows streak", vm.uiState.value.streak >= 1)

        // Node progression persisted end-to-end (§7 step 6, §4.4).
        val nodeProgress = progress.getNodeProgress(nodeId)
        assertNotNull("completing the lesson records node_progress", nodeProgress)
        assertTrue("node marked complete (crown level >= 1)", nodeProgress!!.level >= 1)
    }

    /** Build + submit a correct answer for whatever exercise type is on screen (Tier-0 only). */
    private suspend fun answerCurrentCorrectly(vm: LessonViewModel, content: ContentRepository) {
        val state = vm.uiState.value
        when (state.kind) {
            com.magicalhippie.aprende.ui.lesson.ExerciseKind.TYPED_TRANSLATION -> {
                val answer = firstAcceptedFor(content, state) ?: ""
                vm.onTypedInputChange(answer)
            }
            com.magicalhippie.aprende.ui.lesson.ExerciseKind.WORD_BANK -> {
                // Re-create the correct ordering by tapping tiles in the accepted-answer order.
                val answer = firstAcceptedFor(content, state) ?: ""
                answer.trim().split(Regex("\\s+")).forEach { token ->
                    if (token.isNotEmpty()) vm.onTileSelected(token)
                }
            }
            com.magicalhippie.aprende.ui.lesson.ExerciseKind.MULTIPLE_CHOICE -> {
                val answer = firstAcceptedFor(content, state)
                val idx = state.choices.indexOf(answer)
                vm.onChoiceSelected(if (idx >= 0) idx else 0)
            }
        }
        vm.submit()
    }

    /** The vetted first accepted answer for the on-screen exercise's sentence/direction. */
    private suspend fun firstAcceptedFor(content: ContentRepository, state: com.magicalhippie.aprende.ui.lesson.LessonUiState): String? {
        // Look it up the same way the VM does: by the prompt's sentence. We re-resolve via the
        // node's exercises matched on the rendered prompt's Spanish text.
        val nodeExercises = content.nodes().flatMap { content.exercisesForNode(it.nodeId) }
        for (ex in nodeExercises) {
            val st = content.sentenceText(ex.sentenceId) ?: continue
            if (st.spanishText == state.prompt) {
                return content.acceptedAnswers(ex.sentenceId, ex.direction).firstOrNull()
            }
        }
        return null
    }

    private fun waitUntilReady(vm: LessonViewModel) = waitFor { !vm.uiState.value.loading }

    private inline fun waitFor(timeoutMs: Long = 5_000, predicate: () -> Boolean) {
        val deadline = System.currentTimeMillis() + timeoutMs
        while (!predicate() && System.currentTimeMillis() < deadline) {
            Thread.sleep(10)
        }
    }

    /** Minimal in-memory [SettingsRepository] for the E2E (a low goal so one lesson meets it). */
    private class FixedSettings(dailyGoalXp: Int) : SettingsRepository {
        override val ttsLocale: Flow<String> = MutableStateFlow("es-ES")
        override suspend fun setTtsLocale(value: String) {}
        override val speakingEnabled: Flow<Boolean> = MutableStateFlow(false)
        override suspend fun setSpeakingEnabled(value: Boolean) {}
        override val dailyGoalXp: Flow<Int> = MutableStateFlow(dailyGoalXp)
        override suspend fun setDailyGoalXp(value: Int) {}
        override val accentBarEnabled: Flow<Boolean> = MutableStateFlow(true)
        override suspend fun setAccentBarEnabled(value: Boolean) {}
    }
}

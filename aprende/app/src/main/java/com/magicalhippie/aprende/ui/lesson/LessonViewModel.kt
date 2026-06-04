package com.magicalhippie.aprende.ui.lesson

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.magicalhippie.aprende.domain.gamification.AwardLessonRewardsUseCase
import com.magicalhippie.aprende.domain.gamification.EvaluateAchievementsUseCase
import com.magicalhippie.aprende.domain.gamification.Hearts
import com.magicalhippie.aprende.domain.gamification.HeartsUseCase
import com.magicalhippie.aprende.domain.gamification.Xp
import com.magicalhippie.aprende.domain.grading.GradeAnswerUseCase
import com.magicalhippie.aprende.domain.grading.GradeResult
import com.magicalhippie.aprende.domain.model.Exercise
import com.magicalhippie.aprende.domain.repository.ContentRepository
import com.magicalhippie.aprende.domain.repository.ProgressRepository
import com.magicalhippie.aprende.domain.session.CompleteNodeUseCase
import com.magicalhippie.aprende.domain.session.GenerateLessonUseCase
import com.magicalhippie.aprende.domain.session.LessonPlan
import com.magicalhippie.aprende.domain.session.LessonSession
import com.magicalhippie.aprende.domain.session.LessonSessionFactory
import com.magicalhippie.aprende.ui.navigation.Routes
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

/** What kind of exercise the lesson is currently rendering (Tier-0 types only — SPEC §11.0). */
enum class ExerciseKind { TYPED_TRANSLATION, WORD_BANK, MULTIPLE_CHOICE }

/** Transient feedback after a submitted answer. */
enum class Feedback { NONE, CORRECT, INCORRECT }

/**
 * Immutable lesson UI state (unidirectional data flow, §12.1). All rendering derives from this.
 * Process-death-durable fields (current queue position + in-progress input) are mirrored in
 * [SavedStateHandle] inside the ViewModel (§12.3 — the mechanism AC12 verifies).
 */
data class LessonUiState(
    val loading: Boolean = true,
    val finished: Boolean = false,
    /** True when hearts hit 0 mid-lesson and the session is gated (SPEC §9). */
    val heartsGate: Boolean = false,
    val hearts: Int = Hearts.MAX,
    val prompt: String = "",
    val instruction: String = "",
    val kind: ExerciseKind = ExerciseKind.TYPED_TRANSLATION,
    // --- per-type presentation ---
    val typedInput: String = "",
    val wordBankTiles: List<String> = emptyList(),
    val selectedTiles: List<String> = emptyList(),
    val choices: List<String> = emptyList(),
    val selectedChoice: Int = -1,
    val correctChoiceIndex: Int = -1,
    // --- feedback + completion ---
    val feedback: Feedback = Feedback.NONE,
    val correctAnswer: String = "",
    val xpEarned: Int = 0,
    val streak: Int = 0,
    val mistakesMade: Int = 0,
)

/**
 * Drives one lesson session for a tapped Path node (SPEC §7). Tier-0 only — NO TTS/STT, so
 * AC1 is fully offline with zero audio.
 *
 * Architecture:
 *  - The [LessonSession] (domain) is the authoritative SRS/mistake sink: every processed answer
 *    calls [LessonSession.submit], which updates the target item's FSRS state and appends wrong
 *    answers to the persistent mistake queue (§6.4a/§8). It is transient (not Parcelable), so it
 *    is rebuilt on process-death restore.
 *  - The UI's progression (a small queue of remaining exercise ids + the in-progress input) is
 *    mirrored in [SavedStateHandle] so it survives system-initiated process death (§12.3). The
 *    queue mirrors the session's own dynamic re-queue (wrong answers go to the back, so they
 *    must be answered correctly before the lesson ends) and stays small by construction
 *    (≤ ~20 ids — well clear of the Bundle TransactionTooLargeException ceiling).
 *  - On completion the gamification hooks run: [AwardLessonRewardsUseCase] (XP + streak) and
 *    [EvaluateAchievementsUseCase].
 */
@HiltViewModel
class LessonViewModel @Inject constructor(
    private val savedState: SavedStateHandle,
    private val generateLesson: GenerateLessonUseCase,
    private val sessionFactory: LessonSessionFactory,
    private val content: ContentRepository,
    private val progress: ProgressRepository,
    private val grader: GradeAnswerUseCase,
    private val hearts: HeartsUseCase,
    private val awardRewards: AwardLessonRewardsUseCase,
    private val evaluateAchievements: EvaluateAchievementsUseCase,
    private val completeNode: CompleteNodeUseCase,
) : ViewModel() {

    private val nodeId: Long = savedState.get<Long>(Routes.ARG_NODE_ID) ?: 1L

    private lateinit var plan: LessonPlan
    private lateinit var session: LessonSession
    private val byId: MutableMap<Long, Exercise> = mutableMapOf()

    private val _uiState = MutableStateFlow(LessonUiState())
    val uiState: StateFlow<LessonUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch { start() }
    }

    private suspend fun start() {
        plan = generateLesson.generate(nodeId)
        session = sessionFactory.create(plan)
        byId.clear()
        plan.exercises.forEach { byId[it.exerciseId] = it }

        // Restore (process death) or seed the durable progression queue.
        if (savedState.get<ArrayList<Long>>(KEY_QUEUE) == null) {
            savedState[KEY_QUEUE] = ArrayList(plan.exercises.map { it.exerciseId })
        }
        if (queue().isEmpty()) {
            // Either an empty node, or restored after completion → show the done state.
            finish(awardOnFinish = false)
            return
        }
        renderCurrent()
    }

    // ---- progression queue (durable, Bundle-backed) ----
    private fun queue(): ArrayList<Long> = savedState.get<ArrayList<Long>>(KEY_QUEUE) ?: ArrayList()
    private fun setQueue(q: ArrayList<Long>) { savedState[KEY_QUEUE] = q }
    private fun currentExercise(): Exercise? = queue().firstOrNull()?.let { byId[it] }

    // ---- intents from the UI ----
    fun onTypedInputChange(value: String) {
        savedState[KEY_TYPED] = value
        _uiState.value = _uiState.value.copy(typedInput = value)
    }

    /** Append a tile to the word-bank answer. */
    fun onTileSelected(tile: String) {
        val sel = ArrayList(_uiState.value.selectedTiles).apply { add(tile) }
        persistTiles(sel)
        _uiState.value = _uiState.value.copy(selectedTiles = sel)
    }

    /** Remove the tile at [index] from the in-progress word-bank answer. */
    fun onTileRemoved(index: Int) {
        val sel = ArrayList(_uiState.value.selectedTiles)
        if (index in sel.indices) sel.removeAt(index)
        persistTiles(sel)
        _uiState.value = _uiState.value.copy(selectedTiles = sel)
    }

    fun onChoiceSelected(index: Int) {
        savedState[KEY_CHOICE] = index
        _uiState.value = _uiState.value.copy(selectedChoice = index)
    }

    /** Append the on-screen accent character to the typed answer (SPEC §5.4). */
    fun onAccentChar(ch: String) = onTypedInputChange(_uiState.value.typedInput + ch)

    /** Grade and submit the CURRENT exercise. */
    fun submit() {
        val exercise = currentExercise() ?: return
        val state = _uiState.value
        if (state.feedback != Feedback.NONE) return // already graded; waiting for "continue"
        viewModelScope.launch {
            val accepted = content.acceptedAnswers(exercise.sentenceId, exercise.direction)
            val grade: GradeResult = when (kindOf(exercise.type)) {
                ExerciseKind.TYPED_TRANSLATION -> grader.gradeFreeText(state.typedInput, accepted)
                ExerciseKind.WORD_BANK -> grader.gradeTokens(
                    input = state.selectedTiles,
                    acceptedOrderings = accepted.map { tokenize(it) },
                )
                ExerciseKind.MULTIPLE_CHOICE -> grader.gradeChoice(
                    selectedIndex = state.selectedChoice,
                    correctIndex = state.correctChoiceIndex,
                )
            }

            // SRS + persistent mistake-queue side effects (authoritative domain sink).
            session.submit(grade, usedHint = false)

            if (grade.correct) {
                _uiState.value = _uiState.value.copy(feedback = Feedback.CORRECT)
            } else {
                val remaining = hearts.loseHeart()
                // Wrong answer re-queues to the back (dynamic length — §7 step 5).
                val q = queue().apply { add(removeAt(0)) }
                setQueue(q)
                _uiState.value = _uiState.value.copy(
                    feedback = Feedback.INCORRECT,
                    hearts = remaining,
                    correctAnswer = accepted.firstOrNull() ?: "",
                    mistakesMade = session.mistakesMade,
                    heartsGate = remaining <= 0,
                )
            }
        }
    }

    /** Advance after viewing feedback: dequeue a correct answer, then render next / complete. */
    fun onContinue() {
        val state = _uiState.value
        if (state.heartsGate) return // gated until hearts regen / refill (SPEC §9)
        viewModelScope.launch {
            if (state.feedback == Feedback.CORRECT) {
                val q = queue().apply { if (isNotEmpty()) removeAt(0) }
                setQueue(q)
            }
            clearInput()
            if (queue().isEmpty()) {
                finish(awardOnFinish = true)
            } else {
                renderCurrent()
            }
        }
    }

    private suspend fun finish(awardOnFinish: Boolean) {
        var xp = 0
        if (awardOnFinish) {
            // Mark this Path node complete so it stays done and unlocks the next node (§7 step 6, §4.4).
            completeNode.complete(nodeId)
            val rewards = awardRewards.award(Xp.STANDARD_LESSON)
            evaluateAchievements.evaluate()
            xp = rewards.xpEarned
        }
        // Read the live streak length for the completion summary (it was advanced just above
        // by AwardLessonRewardsUseCase if today's goal was newly met).
        val streakLen = progress.getUserStats()?.streakLength ?: 0
        _uiState.value = _uiState.value.copy(
            loading = false,
            finished = true,
            feedback = Feedback.NONE,
            xpEarned = xp,
            streak = streakLen,
            mistakesMade = session.mistakesMade,
        )
    }

    private suspend fun renderCurrent() {
        val exercise = currentExercise()
        if (exercise == null) {
            finish(awardOnFinish = true)
            return
        }
        val kind = kindOf(exercise.type)
        val accepted = content.acceptedAnswers(exercise.sentenceId, exercise.direction)
        val sentence = content.sentenceText(exercise.sentenceId)
        val prompt = promptFor(sentence, exercise.direction, exercise.promptHint)
        val target = accepted.firstOrNull() ?: ""
        val multipleChoiceSpec = if (kind == ExerciseKind.MULTIPLE_CHOICE) {
            parseMultipleChoiceSpec(exercise.promptHint)
        } else {
            null
        }

        val tiles = if (kind == ExerciseKind.WORD_BANK) tokenize(target).shuffled() else emptyList()
        val choices = if (kind == ExerciseKind.MULTIPLE_CHOICE) {
            multipleChoiceSpec?.choices ?: buildChoices(target, accepted)
        } else {
            emptyList()
        }
        val correctChoiceIndex = if (kind == ExerciseKind.MULTIPLE_CHOICE) {
            multipleChoiceSpec?.correctIndex ?: choices.indexOf(target)
        } else {
            -1
        }

        _uiState.value = LessonUiState(
            loading = false,
            finished = false,
            heartsGate = false,
            hearts = hearts.currentHearts(),
            prompt = prompt,
            instruction = instructionFor(kind, exercise.direction),
            kind = kind,
            typedInput = savedState.get<String>(KEY_TYPED) ?: "",
            wordBankTiles = tiles,
            selectedTiles = restoredTiles(),
            choices = choices,
            selectedChoice = savedState.get<Int>(KEY_CHOICE) ?: -1,
            correctChoiceIndex = correctChoiceIndex,
            feedback = Feedback.NONE,
            correctAnswer = "",
            mistakesMade = session.mistakesMade,
        )
    }

    private fun clearInput() {
        savedState[KEY_TYPED] = ""
        savedState[KEY_CHOICE] = -1
        savedState[KEY_TILES] = ArrayList<String>()
    }

    private fun persistTiles(tiles: List<String>) { savedState[KEY_TILES] = ArrayList(tiles) }
    private fun restoredTiles(): List<String> = savedState.get<ArrayList<String>>(KEY_TILES) ?: emptyList()

    private fun kindOf(type: String): ExerciseKind = when (type) {
        "WORD_BANK" -> ExerciseKind.WORD_BANK
        "MULTIPLE_CHOICE" -> ExerciseKind.MULTIPLE_CHOICE
        else -> ExerciseKind.TYPED_TRANSLATION // typed translation is the Tier-0 default
    }

    private fun promptFor(sentence: com.magicalhippie.aprende.domain.model.SentenceText?, direction: String, fallback: String?): String =
        when (direction) {
            "EN_TO_ES" -> sentence?.englishText
            else -> sentence?.spanishText
        } ?: fallback ?: ""

    private fun instructionFor(kind: ExerciseKind, direction: String): String {
        val dir = if (direction == "ES_TO_EN") "in English" else "in Spanish"
        return when (kind) {
            ExerciseKind.TYPED_TRANSLATION -> "Type this $dir"
            ExerciseKind.WORD_BANK -> "Tap the words to translate $dir"
            ExerciseKind.MULTIPLE_CHOICE -> "Choose the correct translation"
        }
    }

    /** Multiple-choice options: correct answer + simple distractors from other accepted texts. */
    private fun buildChoices(target: String, accepted: List<String>): List<String> {
        val options = LinkedHashSet<String>()
        if (target.isNotBlank()) options.add(target)
        accepted.forEach { if (it.isNotBlank()) options.add(it) }
        // Pad with deterministic placeholders so there are always ≥2 choices to discriminate.
        var i = 1
        while (options.size < 2) { options.add("Option ${i++}") }
        return options.toList()
    }

    private companion object {
        const val KEY_QUEUE = "lesson_queue_ids"
        const val KEY_TYPED = "lesson_typed_input"
        const val KEY_TILES = "lesson_selected_tiles"
        const val KEY_CHOICE = "lesson_selected_choice"

        /** Split an answer into word tokens for word-bank / arrange-the-words grading. */
        fun tokenize(s: String): List<String> = s.trim().split(Regex("\\s+")).filter { it.isNotEmpty() }
    }
}

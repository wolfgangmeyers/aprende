package com.magicalhippie.aprende.ui.review

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.magicalhippie.aprende.domain.grading.GradeAnswerUseCase
import com.magicalhippie.aprende.domain.grading.GradeResult
import com.magicalhippie.aprende.domain.model.Exercise
import com.magicalhippie.aprende.domain.repository.ContentRepository
import com.magicalhippie.aprende.domain.review.GenerateMistakesReviewUseCase
import com.magicalhippie.aprende.domain.review.MistakesReviewSession
import com.magicalhippie.aprende.domain.review.MistakesReviewSessionFactory
import com.magicalhippie.aprende.ui.lesson.ExerciseKind
import com.magicalhippie.aprende.ui.lesson.Feedback
import com.magicalhippie.aprende.ui.lesson.parseMultipleChoiceSpec
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * Immutable UI state for the Mistakes-review screen (SPEC §8 / AC7). Reuses the lesson
 * [ExerciseKind]/[Feedback] enums and the shared exercise composables (P1.7) for rendering.
 */
data class MistakesReviewUiState(
    val loading: Boolean = true,
    val empty: Boolean = false,
    val complete: Boolean = false,
    val prompt: String = "",
    val instruction: String = "",
    val kind: ExerciseKind = ExerciseKind.TYPED_TRANSLATION,
    val typedInput: String = "",
    val wordBankTiles: List<String> = emptyList(),
    val selectedTiles: List<String> = emptyList(),
    val choices: List<String> = emptyList(),
    val selectedChoice: Int = -1,
    val correctChoiceIndex: Int = -1,
    val feedback: Feedback = Feedback.NONE,
    val correctAnswer: String = "",
    /** How many mistakes have been cleared so far (drives the completion summary, AC7). */
    val clearedCount: Int = 0,
)

/**
 * Drives a Mistakes-review session (SPEC §8 / AC7). Loads up to N queued mistakes via
 * [GenerateMistakesReviewUseCase], then walks the [MistakesReviewSession]: each answer is graded
 * with [GradeAnswerUseCase] against vetted accepted answers (C5/§4.6), and the session itself is
 * the authoritative SRS + queue sink — a CORRECT answer clears the mistake from the persistent
 * queue (AC7), a WRONG one re-queues it so it must be answered correctly before completion.
 *
 * Unlike the lesson flow this is NOT hearts-gated (review can't fail you out) and is transient:
 * a process-death restore simply re-drains the queue (idempotent — cleared mistakes are gone).
 */
@HiltViewModel
class MistakesReviewViewModel @Inject constructor(
    private val generate: GenerateMistakesReviewUseCase,
    private val sessionFactory: MistakesReviewSessionFactory,
    private val content: ContentRepository,
    private val grader: GradeAnswerUseCase,
) : ViewModel() {

    private lateinit var session: MistakesReviewSession

    private val _uiState = MutableStateFlow(MistakesReviewUiState())
    val uiState: StateFlow<MistakesReviewUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch { start() }
    }

    private suspend fun start() {
        val plan = generate.generate()
        session = sessionFactory.create(plan)
        if (session.isComplete) {
            _uiState.value = MistakesReviewUiState(loading = false, empty = true, complete = true)
            return
        }
        renderCurrent()
    }

    fun onTypedInputChange(value: String) {
        _uiState.value = _uiState.value.copy(typedInput = value)
    }

    fun onAccentChar(ch: String) = onTypedInputChange(_uiState.value.typedInput + ch)

    fun onTileSelected(tile: String) {
        _uiState.value = _uiState.value.copy(selectedTiles = _uiState.value.selectedTiles + tile)
    }

    fun onTileRemoved(index: Int) {
        val sel = _uiState.value.selectedTiles.toMutableList()
        if (index in sel.indices) sel.removeAt(index)
        _uiState.value = _uiState.value.copy(selectedTiles = sel)
    }

    fun onChoiceSelected(index: Int) {
        _uiState.value = _uiState.value.copy(selectedChoice = index)
    }

    /** Grade and submit the CURRENT exercise to the [MistakesReviewSession]. */
    fun submit() {
        val exercise = session.currentExercise() ?: return
        val state = _uiState.value
        if (state.feedback != Feedback.NONE) return // already graded; awaiting "continue"
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
            // Authoritative sink: updates SRS + clears/re-queues the mistake (AC7).
            session.submit(grade, usedHint = false)
            _uiState.value = _uiState.value.copy(
                feedback = if (grade.correct) Feedback.CORRECT else Feedback.INCORRECT,
                correctAnswer = accepted.firstOrNull() ?: "",
                clearedCount = session.clearedCount,
            )
        }
    }

    /** Advance past the feedback to the next queued mistake, or the completion summary. */
    fun onContinue() {
        viewModelScope.launch {
            if (session.isComplete) {
                _uiState.value = MistakesReviewUiState(
                    loading = false,
                    empty = false,
                    complete = true,
                    clearedCount = session.clearedCount,
                )
            } else {
                renderCurrent()
            }
        }
    }

    private suspend fun renderCurrent() {
        val exercise = session.currentExercise()
        if (exercise == null) {
            _uiState.value = _uiState.value.copy(loading = false, complete = true)
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

        _uiState.value = MistakesReviewUiState(
            loading = false,
            empty = false,
            complete = false,
            prompt = prompt,
            instruction = instructionFor(kind, exercise.direction),
            kind = kind,
            choices = choices,
            correctChoiceIndex = correctChoiceIndex,
            wordBankTiles = tiles,
            feedback = Feedback.NONE,
            clearedCount = session.clearedCount,
        )
    }

    private fun kindOf(type: String): ExerciseKind = when (type) {
        "WORD_BANK" -> ExerciseKind.WORD_BANK
        "MULTIPLE_CHOICE" -> ExerciseKind.MULTIPLE_CHOICE
        else -> ExerciseKind.TYPED_TRANSLATION
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

    private fun buildChoices(target: String, accepted: List<String>): List<String> {
        val options = LinkedHashSet<String>()
        if (target.isNotBlank()) options.add(target)
        accepted.forEach { if (it.isNotBlank()) options.add(it) }
        var i = 1
        while (options.size < 2) { options.add("Option ${i++}") }
        return options.toList()
    }

    private companion object {
        fun tokenize(s: String): List<String> = s.trim().split(Regex("\\s+")).filter { it.isNotEmpty() }
    }
}

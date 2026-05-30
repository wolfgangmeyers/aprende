package com.magicalhippie.aprende.domain.review

import com.magicalhippie.aprende.domain.model.Exercise
import com.magicalhippie.aprende.domain.model.ItemType
import com.magicalhippie.aprende.domain.repository.ContentRepository
import com.magicalhippie.aprende.domain.repository.ProgressRepository
import com.magicalhippie.aprende.domain.grading.GradeResult
import com.magicalhippie.aprende.domain.session.SubmitResult
import com.magicalhippie.aprende.domain.srs.ExerciseOutcome
import com.magicalhippie.aprende.domain.srs.RecordAnswerUseCase
import javax.inject.Inject

/** One queued mistake plus the exercise that was missed. */
data class MistakeReviewItem(val mistakeId: Long, val exercise: Exercise)

/** The set of mistakes to re-practice in a review session (SPEC §8). */
data class MistakesReviewPlan(val items: List<MistakeReviewItem>) {
    val size: Int get() = items.size
}

/**
 * Builds a Mistakes-review session from the persistent mistake queue (SPEC §8): take up to
 * [limit] queued mistakes (FIFO) and load their exercises. Mistakes whose exercise no longer
 * exists (e.g. after a content update) are cleared so they can't wedge the queue.
 */
class GenerateMistakesReviewUseCase @Inject constructor(
    private val progress: ProgressRepository,
    private val content: ContentRepository,
) {
    suspend fun generate(limit: Int = DEFAULT_LIMIT): MistakesReviewPlan {
        val mistakes = progress.drainMistakes(limit) // peek; cleared on correct (or when orphaned)
        val items = mutableListOf<MistakeReviewItem>()
        val orphanIds = mutableListOf<Long>()
        for (m in mistakes) {
            val exercise = content.getExercise(m.exerciseId)
            if (exercise != null) items.add(MistakeReviewItem(m.id, exercise)) else orphanIds.add(m.id)
        }
        if (orphanIds.isNotEmpty()) progress.clearMistakes(orphanIds)
        return MistakesReviewPlan(items)
    }

    companion object {
        const val DEFAULT_LIMIT = 10
    }
}

/**
 * Drives a Mistakes-review session (SPEC §8 / AC7). On each [submit]: update the target item's
 * SRS state; a CORRECT answer **clears the mistake from the persistent queue** (it's fixed); a
 * WRONG answer re-queues it (must be answered correctly to clear). Single-use — create via
 * [MistakesReviewSessionFactory].
 */
class MistakesReviewSession(
    plan: MistakesReviewPlan,
    private val recordAnswer: RecordAnswerUseCase,
    private val progress: ProgressRepository,
) {
    private val queue: ArrayDeque<MistakeReviewItem> = ArrayDeque(plan.items)
    private var cleared = 0

    fun currentExercise(): Exercise? = queue.firstOrNull()?.exercise

    val isComplete: Boolean get() = queue.isEmpty()
    val clearedCount: Int get() = cleared

    suspend fun submit(grade: GradeResult, usedHint: Boolean = false): SubmitResult {
        val item = queue.removeFirst()
        val exercise = item.exercise
        recordAnswer.record(
            exercise.targetItemId,
            ItemType.valueOf(exercise.targetItemType),
            ExerciseOutcome(correct = grade.correct, usedHint = usedHint, forgivenTypo = grade.forgivenTypo),
        )
        return if (grade.correct) {
            progress.clearMistakes(listOf(item.mistakeId))
            cleared++
            SubmitResult(correct = true, requeued = false, complete = queue.isEmpty())
        } else {
            queue.addLast(item) // stays in the review until answered correctly
            SubmitResult(correct = false, requeued = true, complete = false)
        }
    }
}

/** Creates a single-use [MistakesReviewSession]. */
class MistakesReviewSessionFactory @Inject constructor(
    private val recordAnswer: RecordAnswerUseCase,
    private val progress: ProgressRepository,
) {
    fun create(plan: MistakesReviewPlan): MistakesReviewSession =
        MistakesReviewSession(plan, recordAnswer, progress)
}

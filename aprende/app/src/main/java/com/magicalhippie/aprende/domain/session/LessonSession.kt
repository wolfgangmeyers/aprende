package com.magicalhippie.aprende.domain.session

import com.magicalhippie.aprende.domain.model.Exercise
import com.magicalhippie.aprende.domain.model.ItemType
import com.magicalhippie.aprende.domain.repository.ProgressRepository
import com.magicalhippie.aprende.domain.srs.ExerciseOutcome
import com.magicalhippie.aprende.domain.srs.RecordAnswerUseCase
import com.magicalhippie.aprende.domain.grading.GradeResult
import java.time.Clock
import javax.inject.Inject

/**
 * Drives one lesson session (SPEC §7 steps 4–6). Stateful and single-use — create one per
 * session via [LessonSessionFactory].
 *
 * On each [submit]:
 *  - updates the SRS state of the exercise's **target item** (fan-out rule §6.4a) via [RecordAnswerUseCase];
 *  - on a wrong answer, **re-queues** the exercise to the end (so it must be answered correctly
 *    before the session ends — this is what makes lesson length dynamic, §7 step 5) and appends
 *    it to the persistent mistake queue (§8 / AC7).
 * The session is complete when the queue drains.
 *
 * NOTE: awarding XP / advancing the streak on completion (SPEC §7 step 6) is wired in P1.5
 * (gamification). This session exposes the data for it via [summary]; it deliberately does not
 * depend on the (not-yet-built) gamification layer.
 */
class LessonSession(
    val plan: LessonPlan,
    private val recordAnswer: RecordAnswerUseCase,
    private val progress: ProgressRepository,
    private val clock: Clock,
) {
    private val queue: ArrayDeque<Exercise> = ArrayDeque(plan.exercises)
    private var presented = 0
    private var mistakeCount = 0

    fun currentExercise(): Exercise? = queue.firstOrNull()

    val isComplete: Boolean get() = queue.isEmpty()
    val presentedCount: Int get() = presented
    val mistakesMade: Int get() = mistakeCount

    /** Submit the graded result (+ whether a hint was used) for the CURRENT exercise. */
    suspend fun submit(grade: GradeResult, usedHint: Boolean = false): SubmitResult {
        val exercise = queue.removeFirst()
        presented++
        val itemType = ItemType.valueOf(exercise.targetItemType)
        val outcome = ExerciseOutcome(correct = grade.correct, usedHint = usedHint, forgivenTypo = grade.forgivenTypo)
        recordAnswer.record(exercise.targetItemId, itemType, outcome)

        return if (!outcome.correct) {
            mistakeCount++
            progress.enqueueMistake(exercise.exerciseId, exercise.targetItemId, itemType, clock.millis())
            queue.addLast(exercise) // dynamic length: must be answered correctly before completion
            SubmitResult(correct = false, requeued = true, complete = false)
        } else {
            SubmitResult(correct = true, requeued = false, complete = queue.isEmpty())
        }
    }

    fun summary(): LessonSummary = LessonSummary(
        plannedCount = plan.size,
        presentedCount = presented,
        mistakesMade = mistakeCount,
        completed = isComplete,
    )
}

/** Creates a single-use [LessonSession] from a [LessonPlan], injecting its collaborators. */
class LessonSessionFactory @Inject constructor(
    private val recordAnswer: RecordAnswerUseCase,
    private val progress: ProgressRepository,
    private val clock: Clock,
) {
    fun create(plan: LessonPlan): LessonSession = LessonSession(plan, recordAnswer, progress, clock)
}

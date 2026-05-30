package com.magicalhippie.aprende.domain.session

import com.magicalhippie.aprende.domain.model.Exercise

/**
 * An ordered set of exercises for one lesson session (SPEC §7). [newExerciseIds] marks the
 * exercises introducing a not-yet-seen target item (so the UI can show hints/word-bank on
 * first appearance). The session's *actual* length is dynamic and may exceed this (wrong
 * answers re-queue — see [LessonSession]).
 */
data class LessonPlan(
    val exercises: List<Exercise>,
    val newExerciseIds: Set<Long>,
) {
    val size: Int get() = exercises.size
}

/** Result of submitting one answer to a [LessonSession]. */
data class SubmitResult(
    val correct: Boolean,
    /** True when a wrong answer was re-queued and must be answered correctly before the session ends. */
    val requeued: Boolean,
    /** True when this submission emptied the queue and completed the session. */
    val complete: Boolean,
)

/** End-of-session tallies (input to XP/streak in P1.5; SPEC §7 step 6). */
data class LessonSummary(
    val plannedCount: Int,
    val presentedCount: Int,
    val mistakesMade: Int,
    val completed: Boolean,
)

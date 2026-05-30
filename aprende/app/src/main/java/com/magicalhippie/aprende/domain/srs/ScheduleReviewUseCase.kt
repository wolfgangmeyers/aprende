package com.magicalhippie.aprende.domain.srs

import java.time.Clock
import javax.inject.Inject

/**
 * The graded result of a single exercise attempt, produced by the deterministic
 * answer checker (SPEC §5.5). This is the SRS engine's only input about how the
 * learner did — the learner never self-rates (contrast Anki).
 */
data class ExerciseOutcome(
    val correct: Boolean,
    val usedHint: Boolean = false,
    val forgivenTypo: Boolean = false,
)

/**
 * Derives the FSRS grade from an [ExerciseOutcome] (SPEC §6.4) and advances the item's
 * SRS state via [Fsrs]. This use-case is the seam that isolates SRS scheduling from the
 * rest of the app (SPEC D1 — there is intentionally no `SrsScheduler` interface).
 *
 * Time comes from an injected [Clock] so streak/decay/scheduling are deterministic and
 * unit-testable across day boundaries (SPEC §12.3).
 */
class ScheduleReviewUseCase @Inject constructor(
    private val clock: Clock,
    private val fsrs: Fsrs,
) {
    /**
     * Maps an exercise outcome to an FSRS grade (SPEC §6.4):
     * wrong → Again; correct-with-hint-or-forgiven-typo → Hard; clean correct → Good.
     * There is no Easy path from a normal exercise.
     */
    fun gradeFor(outcome: ExerciseOutcome): FsrsRating = when {
        !outcome.correct -> FsrsRating.AGAIN
        outcome.usedHint || outcome.forgivenTypo -> FsrsRating.HARD
        else -> FsrsRating.GOOD
    }

    /**
     * Apply an exercise outcome to an item and return its updated SRS state.
     * A null [previous] means this is the item's first-ever review.
     */
    fun review(previous: SrsItemState?, outcome: ExerciseOutcome): SrsItemState {
        val rating = gradeFor(outcome)
        val now = clock.millis()
        return if (previous == null) {
            fsrs.firstReview(rating, now)
        } else {
            fsrs.review(previous, rating, now)
        }
    }
}

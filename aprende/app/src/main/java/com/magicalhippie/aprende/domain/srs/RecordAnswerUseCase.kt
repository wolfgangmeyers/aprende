package com.magicalhippie.aprende.domain.srs

import com.magicalhippie.aprende.domain.model.ItemType
import com.magicalhippie.aprende.domain.model.SrsItem
import com.magicalhippie.aprende.domain.model.SrsState
import com.magicalhippie.aprende.domain.repository.ProgressRepository
import javax.inject.Inject

/**
 * Applies an exercise outcome to the SRS state of the exercise's **target item only**
 * (the fan-out rule, SPEC §6.4a — incidental lexemes in the sentence are NOT all updated,
 * which would thrash unrelated schedules) and persists it. Increments the lifetime counters.
 *
 * Composes [ScheduleReviewUseCase] (FSRS + Clock) with [ProgressRepository] (persistence).
 */
class RecordAnswerUseCase @Inject constructor(
    private val progress: ProgressRepository,
    private val schedule: ScheduleReviewUseCase,
) {
    suspend fun record(
        targetItemId: Long,
        targetItemType: ItemType,
        outcome: ExerciseOutcome,
    ): SrsItem {
        val previous = progress.getSrsItem(targetItemId, targetItemType)
        val newState = schedule.review(previous?.state, outcome)
        val lifecycle = when {
            !outcome.correct -> SrsState.RELEARNING
            previous == null -> SrsState.LEARNING
            else -> SrsState.REVIEW
        }
        val updated = SrsItem(
            itemId = targetItemId,
            itemType = targetItemType,
            state = newState,
            lifecycle = lifecycle,
            timesSeen = (previous?.timesSeen ?: 0) + 1,
            timesCorrect = (previous?.timesCorrect ?: 0) + if (outcome.correct) 1 else 0,
            timesWrong = (previous?.timesWrong ?: 0) + if (outcome.correct) 0 else 1,
        )
        progress.upsertSrsItem(updated)
        return updated
    }
}

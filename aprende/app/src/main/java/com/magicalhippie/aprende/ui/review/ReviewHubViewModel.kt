package com.magicalhippie.aprende.ui.review

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.magicalhippie.aprende.domain.repository.ProgressRepository
import com.magicalhippie.aprende.domain.review.SeenItemsByStrengthUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * Immutable UI state for the Review hub (SPEC §8). Surfaces the live counts that motivate each
 * review entry point: how many mistakes are queued and how many words the learner has seen.
 */
data class ReviewHubUiState(
    val mistakesQueued: Int = 0,
    val wordsLearned: Int = 0,
    val loading: Boolean = true,
)

/**
 * Review-hub ViewModel (SPEC §8). The hub is the entry point to the three reinforcement
 * surfaces — Mistakes review, Words, Vocab practice — distinct from *learning new* (§7). It
 * observes live counts: the seen-item count (words learned) from [SeenItemsByStrengthUseCase]
 * and the queued-mistake count peeked from the persistent mistake queue.
 *
 * The mistake count is recomputed each time the seen list changes (the cheapest live trigger we
 * have without adding a dedicated count Flow); it peeks the queue (a bounded read) and never
 * drains it — draining only happens inside a Mistakes-review session.
 */
@HiltViewModel
class ReviewHubViewModel @Inject constructor(
    private val progress: ProgressRepository,
    private val seenByStrength: SeenItemsByStrengthUseCase,
) : ViewModel() {

    private val mistakesQueued = MutableStateFlow(0)

    init {
        refreshMistakeCount()
    }

    /** Re-peek the mistake queue (call on return to the hub from a Mistakes-review session). */
    fun refreshMistakeCount() {
        viewModelScope.launch {
            mistakesQueued.value = progress.drainMistakes(MISTAKE_PEEK_LIMIT).size
        }
    }

    val uiState: StateFlow<ReviewHubUiState> =
        combine(seenByStrength(), mistakesQueued) { seen, mistakes ->
            ReviewHubUiState(
                mistakesQueued = mistakes,
                wordsLearned = seen.size,
                loading = false,
            )
        }.stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(STOP_TIMEOUT_MILLIS),
            initialValue = ReviewHubUiState(),
        )

    private companion object {
        /** Peek window for the queued-mistake count (the queue is small by construction, §8). */
        const val MISTAKE_PEEK_LIMIT = 100
        const val STOP_TIMEOUT_MILLIS = 5_000L
    }
}

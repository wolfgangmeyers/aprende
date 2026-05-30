package com.magicalhippie.aprende.ui.words

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.magicalhippie.aprende.domain.model.ItemType
import com.magicalhippie.aprende.domain.repository.ContentRepository
import com.magicalhippie.aprende.domain.review.SeenItemsByStrengthUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import javax.inject.Inject

/**
 * One learned word as the Words list renders it (SPEC §8 Words screen / §6.6). [strengthBars]
 * buckets the FSRS recall strength R∈[0,1] into [STRENGTH_BARS] discrete bars (a "crystal" meter
 * — §12.1), and [isStrong] marks a high-R word to render gold.
 */
data class WordUiModel(
    val itemId: Long,
    val lemma: String,
    val gloss: String,
    val strengthBars: Int,
    val isStrong: Boolean,
)

data class WordsUiState(
    val words: List<WordUiModel> = emptyList(),
    val loading: Boolean = true,
)

/**
 * Words-list ViewModel (SPEC §8 / §6.6). Observes [SeenItemsByStrengthUseCase] (weakest-first)
 * and joins each `LEXEME` SRS row to its content [com.magicalhippie.aprende.domain.model.Lexeme]
 * (the cross-DB join lives in the repository layer — D2) to show lemma + gloss + a strength
 * meter. Non-lexeme items (e.g. grammar rules) are not shown on the Words list. Strength is the
 * lazily-decayed R (§6.5), so the ordering reflects what to practice next.
 */
@HiltViewModel
class WordsViewModel @Inject constructor(
    private val content: ContentRepository,
    seenByStrength: SeenItemsByStrengthUseCase,
) : ViewModel() {

    val uiState: StateFlow<WordsUiState> =
        seenByStrength()
            .map { items ->
                val words = items
                    .filter { it.item.itemType == ItemType.LEXEME }
                    .mapNotNull { itemStrength ->
                        val lexeme = content.getLexeme(itemStrength.item.itemId) ?: return@mapNotNull null
                        WordUiModel(
                            itemId = lexeme.lexemeId,
                            lemma = lexeme.lemma,
                            gloss = lexeme.englishGloss,
                            strengthBars = strengthBars(itemStrength.strength),
                            isStrong = itemStrength.strength >= STRONG_THRESHOLD,
                        )
                    }
                WordsUiState(words = words, loading = false)
            }
            .stateIn(
                scope = viewModelScope,
                started = SharingStarted.WhileSubscribed(STOP_TIMEOUT_MILLIS),
                initialValue = WordsUiState(),
            )

    companion object {
        /** Number of discrete bars in the strength crystal meter. */
        const val STRENGTH_BARS = 4

        /** R at or above this renders the word as "strong" (gold). */
        const val STRONG_THRESHOLD = 0.9

        private const val STOP_TIMEOUT_MILLIS = 5_000L

        /** Bucket R∈[0,1] into 0..[STRENGTH_BARS] filled bars (always ≥1 for a seen word). */
        fun strengthBars(r: Double): Int {
            val clamped = r.coerceIn(0.0, 1.0)
            val bars = Math.round(clamped * STRENGTH_BARS).toInt()
            return bars.coerceIn(1, STRENGTH_BARS)
        }
    }
}

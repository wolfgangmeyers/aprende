package com.magicalhippie.aprende.ui.vocab

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.magicalhippie.aprende.domain.model.ItemType
import com.magicalhippie.aprende.domain.repository.ContentRepository
import com.magicalhippie.aprende.domain.review.MatchPair
import com.magicalhippie.aprende.domain.review.MatchSession
import com.magicalhippie.aprende.domain.review.MatchSide
import com.magicalhippie.aprende.domain.review.MatchTap
import com.magicalhippie.aprende.domain.review.MatchTile
import com.magicalhippie.aprende.domain.review.SeenItemsByStrengthUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

/** A tappable matching tile as the vocab board renders it. */
data class VocabTileUiModel(
    val pairId: Long,
    val side: MatchSide,
    val text: String,
    val selected: Boolean,
    val cleared: Boolean,
)

data class VocabPracticeUiState(
    val loading: Boolean = true,
    val empty: Boolean = false,
    val complete: Boolean = false,
    val tiles: List<VocabTileUiModel> = emptyList(),
    val matchedCount: Int = 0,
    val totalPairs: Int = 0,
)

/**
 * Vocabulary-practice ViewModel (SPEC §8) — untimed matching over a handful of learned lexemes.
 * Picks the weakest-first encountered `LEXEME` items (so practice targets what's decaying) via
 * [SeenItemsByStrengthUseCase], resolves lemma↔gloss from content, and drives the pure
 * [MatchSession] (all matching rules + completion live there; this VM only projects its state).
 */
@HiltViewModel
class VocabPracticeViewModel @Inject constructor(
    private val content: ContentRepository,
    private val seenByStrength: SeenItemsByStrengthUseCase,
) : ViewModel() {

    private var session: MatchSession? = null

    private val _uiState = MutableStateFlow(VocabPracticeUiState())
    val uiState: StateFlow<VocabPracticeUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch { start() }
    }

    private suspend fun start() {
        // Take a one-shot snapshot of the weakest learned lexemes (matching is a fixed board).
        val seen = seenByStrength().first()
        val pairs = seen
            .filter { it.item.itemType == ItemType.LEXEME }
            .take(MAX_PAIRS)
            .mapNotNull { itemStrength ->
                val lexeme = content.getLexeme(itemStrength.item.itemId) ?: return@mapNotNull null
                MatchPair(itemId = lexeme.lexemeId, lemma = lexeme.lemma, gloss = lexeme.englishGloss)
            }
        if (pairs.size < MIN_PAIRS) {
            _uiState.value = VocabPracticeUiState(loading = false, empty = true)
            return
        }
        val s = MatchSession(pairs, shuffle = { it.shuffled() })
        session = s
        publish(s)
    }

    /** Tap a board tile; delegates the rule to [MatchSession] and re-projects the new board. */
    fun onTileTapped(pairId: Long, side: MatchSide) {
        val s = session ?: return
        val tile = s.tiles.firstOrNull { it.pairId == pairId && it.side == side } ?: return
        when (s.tap(tile)) {
            MatchTap.SELECTED, MatchTap.MATCHED, MatchTap.MISMATCH, MatchTap.IGNORED -> publish(s)
        }
    }

    private fun publish(s: MatchSession) {
        val selected = s.selectedTile()
        _uiState.value = VocabPracticeUiState(
            loading = false,
            empty = false,
            complete = s.isComplete,
            tiles = s.tiles.map { it.toUi(selected, s) },
            matchedCount = s.clearedCount,
            totalPairs = s.tiles.size / 2,
        )
    }

    private fun MatchTile.toUi(selected: MatchTile?, s: MatchSession): VocabTileUiModel =
        VocabTileUiModel(
            pairId = pairId,
            side = side,
            text = text,
            selected = this == selected,
            cleared = s.isCleared(pairId),
        )

    private companion object {
        const val MAX_PAIRS = 6
        const val MIN_PAIRS = 2
    }
}

package com.magicalhippie.aprende.ui.about

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.magicalhippie.aprende.domain.model.Attribution
import com.magicalhippie.aprende.domain.repository.ContentRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

/** One rendered content credit (SPEC §4.5 / AC14): a human label + the raw source/license. */
data class AttributionUiModel(
    val displayName: String,
    val source: String,
    val license: String,
)

data class AttributionUiState(
    val credits: List<AttributionUiModel> = emptyList(),
    val loading: Boolean = true,
)

/**
 * Attribution/credits ViewModel (SPEC §4.5/§4.6, C4/C5, AC14). Reads the distinct vetted
 * `(source, license)` provenance from [ContentRepository.attributions] — the SAME columns the
 * build-time vetting gate populates (§4.6) — and renders them. It does NOT bypass or re-derive
 * the pipeline; it surfaces what shipped. The display name is a presentation nicety mapped from
 * the source key; the raw source/license are always shown so the credit stays accurate to data.
 */
@HiltViewModel
class AttributionViewModel @Inject constructor(
    private val content: ContentRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(AttributionUiState())
    val uiState: StateFlow<AttributionUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            val credits = content.attributions().map { it.toUi() }
            _uiState.value = AttributionUiState(credits = credits, loading = false)
        }
    }

    private fun Attribution.toUi(): AttributionUiModel =
        AttributionUiModel(displayName = displayNameFor(source), source = source, license = license)

    private companion object {
        /** Friendly label for a known source key; falls back to the raw key for anything new. */
        fun displayNameFor(source: String): String = when (source.lowercase()) {
            "tatoeba" -> "Tatoeba"
            "wiktionary" -> "Wiktionary"
            "wikidata" -> "Wikidata"
            "frequencywords", "hermitdave" -> "FrequencyWords (OpenSubtitles)"
            "authored" -> "Aprende (authored)"
            else -> source
        }
    }
}

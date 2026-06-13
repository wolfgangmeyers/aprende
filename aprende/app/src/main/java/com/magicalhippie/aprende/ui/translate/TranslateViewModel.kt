package com.magicalhippie.aprende.ui.translate

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.magicalhippie.aprende.domain.repository.TranslationRepository
import com.magicalhippie.aprende.domain.translation.TranslationLookupResult
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class TranslateUiState(
    val query: String = "",
    val loading: Boolean = false,
    val result: TranslationLookupResult? = null,
    val message: String? = null,
)

@HiltViewModel
class TranslateViewModel @Inject constructor(
    private val translations: TranslationRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(TranslateUiState())
    val uiState: StateFlow<TranslateUiState> = _uiState
    private var lookupJob: Job? = null
    private var lookupGeneration: Int = 0

    fun onQueryChange(query: String) {
        lookupGeneration++
        lookupJob?.cancel()
        _uiState.update {
            it.copy(
                query = query,
                loading = false,
                message = null,
                result = null,
            )
        }
    }

    fun lookup() {
        val query = _uiState.value.query.trim()
        if (query.isBlank()) {
            _uiState.update { it.copy(message = "Enter a Spanish word or phrase.", result = null) }
            return
        }

        lookupJob?.cancel()
        val generation = ++lookupGeneration
        lookupJob = viewModelScope.launch {
            _uiState.update { it.copy(loading = true, message = null) }
            try {
                val lookup = translations.lookupSpanishToEnglish(query)
                _uiState.update { state ->
                    if (generation != lookupGeneration || state.query.trim() != query) {
                        state
                    } else {
                        state.copy(
                            loading = false,
                            result = lookup,
                            message = if (lookup.hasMatches) null else "No local match found.",
                        )
                    }
                }
            } catch (e: CancellationException) {
                throw e
            } catch (_: Throwable) {
                _uiState.update { state ->
                    if (generation != lookupGeneration || state.query.trim() != query) {
                        state
                    } else {
                        state.copy(
                            loading = false,
                            result = null,
                            message = "Lookup is unavailable right now.",
                        )
                    }
                }
            }
        }
    }

    fun clear() {
        lookupGeneration++
        lookupJob?.cancel()
        _uiState.value = TranslateUiState()
    }
}

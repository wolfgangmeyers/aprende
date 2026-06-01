package com.magicalhippie.aprende.ui.vocab

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.magicalhippie.aprende.domain.review.MatchSide
import com.magicalhippie.aprende.ui.theme.AprendeTheme

/**
 * Stateful entry point for vocabulary practice (SPEC §8). Collects [VocabPracticeUiState]
 * lifecycle-aware and defers to the stateless [VocabPracticeContent]. The matching rules live in
 * the pure domain [com.magicalhippie.aprende.domain.review.MatchSession]; this screen only
 * renders the board and forwards taps.
 */
@Composable
fun VocabPracticeScreen(
    onFinished: () -> Unit,
    viewModel: VocabPracticeViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    VocabPracticeContent(
        state = state,
        onTileTapped = viewModel::onTileTapped,
        onFinished = onFinished,
    )
}

/** Stateless, preview- and test-friendly board. Renders only from [VocabPracticeUiState]. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun VocabPracticeContent(
    state: VocabPracticeUiState,
    onTileTapped: (Long, MatchSide) -> Unit = { _, _ -> },
    onFinished: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    when {
        state.loading -> Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator() }
        state.empty -> EmptyOrDone("✨ Not enough words yet — learn a few more!", onFinished, modifier)
        state.complete -> EmptyOrDone("✨ All matched! ${state.matchedCount}/${state.totalPairs}", onFinished, modifier)
        else -> Column(
            modifier = modifier
                .fillMaxSize()
                .padding(24.dp),
        ) {
            Text("✨ Vocab practice", style = MaterialTheme.typography.titleLarge)
            Text(
                "Matched ${state.matchedCount}/${state.totalPairs}",
                style = MaterialTheme.typography.bodyMedium,
            )
            Spacer(Modifier.height(24.dp))
            FlowRow(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                state.tiles.forEach { tile ->
                    if (!tile.cleared) {
                        if (tile.selected) {
                            Button(onClick = { onTileTapped(tile.pairId, tile.side) }) { Text(tile.text) }
                        } else {
                            OutlinedButton(onClick = { onTileTapped(tile.pairId, tile.side) }) { Text(tile.text) }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun EmptyOrDone(message: String, onFinished: () -> Unit, modifier: Modifier) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(message, style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(24.dp))
        Button(onClick = onFinished, modifier = Modifier.fillMaxWidth()) { Text("Done") }
    }
}

@Preview(showBackground = true)
@Composable
private fun VocabPracticePreview() {
    AprendeTheme {
        VocabPracticeContent(
            state = VocabPracticeUiState(
                loading = false,
                totalPairs = 2,
                matchedCount = 0,
                tiles = listOf(
                    VocabTileUiModel(1, MatchSide.LEMMA, "perro", selected = false, cleared = false),
                    VocabTileUiModel(1, MatchSide.GLOSS, "dog", selected = false, cleared = false),
                    VocabTileUiModel(2, MatchSide.LEMMA, "agua", selected = true, cleared = false),
                    VocabTileUiModel(2, MatchSide.GLOSS, "water", selected = false, cleared = false),
                ),
            ),
        )
    }
}

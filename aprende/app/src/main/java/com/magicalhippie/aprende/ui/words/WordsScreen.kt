package com.magicalhippie.aprende.ui.words

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.magicalhippie.aprende.ui.theme.AprendeTheme

/**
 * Stateful entry point for the Words list (SPEC §8 / §6.6). Collects [WordsUiState] lifecycle-
 * aware and defers to the stateless [WordsContent]. Lists learned lemmas weakest-first with a
 * strength crystal meter (gold for strong words — §12.1 whimsy).
 */
@Composable
fun WordsScreen(viewModel: WordsViewModel = hiltViewModel()) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    WordsContent(state = state)
}

/** Stateless, preview- and test-friendly content. Renders only from [WordsUiState]. */
@Composable
fun WordsContent(state: WordsUiState, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
    ) {
        Text(
            text = "✨ Words",
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.primary,
        )
        Spacer(Modifier.height(16.dp))
        LazyColumn(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            items(state.words, key = { it.itemId }) { word -> WordCard(word) }
        }
    }
}

@Composable
private fun WordCard(word: WordUiModel) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .semantics { contentDescription = "${word.lemma}, ${word.gloss}, strength ${word.strengthBars}" },
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(20.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column {
                Text(word.lemma, style = MaterialTheme.typography.titleMedium)
                Text(word.gloss, style = MaterialTheme.typography.bodyMedium)
            }
            StrengthMeter(bars = word.strengthBars, isStrong = word.isStrong)
        }
    }
}

/** A simple discrete strength crystal meter; strong words glow gold (§6.6 / §12.1). */
@Composable
private fun StrengthMeter(bars: Int, isStrong: Boolean) {
    val filled = if (isStrong) "🟡" else "🔷"
    val empty = "▫️"
    Text(
        text = filled.repeat(bars) + empty.repeat((WordsViewModel.STRENGTH_BARS - bars).coerceAtLeast(0)),
        style = MaterialTheme.typography.titleMedium,
    )
}

@Preview(showBackground = true)
@Composable
private fun WordsPreview() {
    AprendeTheme {
        WordsContent(
            state = WordsUiState(
                words = listOf(
                    WordUiModel(1, "perro", "dog", strengthBars = 1, isStrong = false),
                    WordUiModel(2, "agua", "water", strengthBars = 4, isStrong = true),
                ),
                loading = false,
            ),
        )
    }
}

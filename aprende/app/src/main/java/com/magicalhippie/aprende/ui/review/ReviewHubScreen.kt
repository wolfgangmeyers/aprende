package com.magicalhippie.aprende.ui.review

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
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
 * Stateful entry point for the Review hub (SPEC §8). Collects [ReviewHubUiState] lifecycle-aware
 * and defers rendering to the stateless [ReviewHubContent]. The three callbacks navigate to the
 * Mistakes review, the Words list, and Vocab practice.
 */
@Composable
fun ReviewHubScreen(
    onMistakes: () -> Unit,
    onWords: () -> Unit,
    onVocab: () -> Unit,
    viewModel: ReviewHubViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    ReviewHubContent(
        state = state,
        onMistakes = onMistakes,
        onWords = onWords,
        onVocab = onVocab,
    )
}

/** Stateless, preview- and test-friendly hub content. Renders only from [ReviewHubUiState]. */
@Composable
fun ReviewHubContent(
    state: ReviewHubUiState,
    onMistakes: () -> Unit = {},
    onWords: () -> Unit = {},
    onVocab: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = "✨ Review",
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.primary,
        )
        Spacer(Modifier.height(24.dp))

        ReviewEntryCard(
            title = "Mistakes",
            subtitle = "${state.mistakesQueued} queued",
            onClick = onMistakes,
        )
        Spacer(Modifier.height(12.dp))
        ReviewEntryCard(
            title = "Words",
            subtitle = "${state.wordsLearned} learned",
            onClick = onWords,
        )
        Spacer(Modifier.height(12.dp))
        ReviewEntryCard(
            title = "Vocab practice",
            subtitle = "Match it up",
            onClick = onVocab,
        )
    }
}

@Composable
private fun ReviewEntryCard(title: String, subtitle: String, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .semantics { contentDescription = "$title, $subtitle" },
    ) {
        Column(Modifier.padding(20.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(subtitle, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun ReviewHubPreview() {
    AprendeTheme {
        ReviewHubContent(
            state = ReviewHubUiState(mistakesQueued = 3, wordsLearned = 42, loading = false),
        )
    }
}

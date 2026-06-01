package com.magicalhippie.aprende.ui.about

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
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
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.magicalhippie.aprende.ui.theme.AprendeTheme

/**
 * Credits / attribution screen (SPEC §4.5/§4.6, C4/C5, AC14). Renders the vetted content
 * provenance shipped in `content.db` — proving every bundled row carries its required
 * attribution. Stateful entry collects [AttributionUiState]; rendering is the stateless
 * [AttributionContent].
 */
@Composable
fun AttributionScreen(viewModel: AttributionViewModel = hiltViewModel()) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    AttributionContent(state = state)
}

/** Stateless, preview- and test-friendly content. Renders only from [AttributionUiState]. */
@Composable
fun AttributionContent(state: AttributionUiState, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
    ) {
        Text(
            text = "✨ Credits",
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.primary,
        )
        Spacer(Modifier.height(8.dp))
        Text(
            "Aprende's content is built from these openly-licensed sources:",
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(Modifier.height(16.dp))
        LazyColumn(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            items(state.credits, key = { it.source + "|" + it.license }) { credit ->
                CreditCard(credit)
            }
        }
    }
}

@Composable
private fun CreditCard(credit: AttributionUiModel) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .semantics { contentDescription = "${credit.displayName} — ${credit.license}" },
    ) {
        Column(Modifier.padding(20.dp)) {
            Text(credit.displayName, style = MaterialTheme.typography.titleMedium)
            Text("License: ${credit.license}", style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun AttributionPreview() {
    AprendeTheme {
        AttributionContent(
            state = AttributionUiState(
                credits = listOf(
                    AttributionUiModel("Tatoeba", "tatoeba", "CC-BY-2.0-FR"),
                    AttributionUiModel("Wiktionary", "wiktionary", "CC-BY-SA-3.0"),
                ),
                loading = false,
            ),
        )
    }
}

package com.magicalhippie.aprende.ui.translate

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.magicalhippie.aprende.domain.translation.TranslationLookupResult
import com.magicalhippie.aprende.domain.translation.TranslationMatch
import com.magicalhippie.aprende.domain.translation.TranslationMatchKind
import com.magicalhippie.aprende.ui.theme.AprendeTheme

@Composable
fun TranslatePopupHost(
    modifier: Modifier = Modifier,
    viewModel: TranslateViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    var sheetOpen by rememberSaveable { mutableStateOf(false) }

    TranslatePopupContent(
        state = state,
        sheetOpen = sheetOpen,
        onOpen = { sheetOpen = true },
        onDismiss = { sheetOpen = false },
        onQueryChange = viewModel::onQueryChange,
        onLookup = viewModel::lookup,
        onClear = viewModel::clear,
        modifier = modifier,
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TranslatePopupContent(
    state: TranslateUiState,
    sheetOpen: Boolean,
    onOpen: () -> Unit,
    onDismiss: () -> Unit,
    onQueryChange: (String) -> Unit,
    onLookup: () -> Unit,
    onClear: () -> Unit,
    modifier: Modifier = Modifier,
) {
    FloatingActionButton(
        modifier = modifier
            .testTag("translate_fab")
            .semantics { contentDescription = "Open Spanish to English lookup" },
        onClick = onOpen,
    ) {
        Text("EN")
    }

    if (sheetOpen) {
        ModalBottomSheet(onDismissRequest = onDismiss) {
            TranslateSheetContent(
                state = state,
                onQueryChange = onQueryChange,
                onLookup = onLookup,
                onClear = onClear,
            )
        }
    }
}

@Composable
internal fun TranslateSheetContent(
    state: TranslateUiState,
    onQueryChange: (String) -> Unit,
    onLookup: () -> Unit,
    onClear: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .navigationBarsPadding()
            .padding(horizontal = 24.dp, vertical = 16.dp),
    ) {
        Text(
            text = "Spanish to English",
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.primary,
        )
        Text(
            text = "Offline lookup from Aprende content",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(16.dp))
        OutlinedTextField(
            value = state.query,
            onValueChange = onQueryChange,
            modifier = Modifier
                .fillMaxWidth()
                .testTag("translate_query"),
            label = { Text("Spanish word or phrase") },
            singleLine = false,
            minLines = 1,
            maxLines = 3,
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            keyboardActions = KeyboardActions(onSearch = { onLookup() }),
        )
        Spacer(Modifier.height(12.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Button(
                onClick = onLookup,
                enabled = !state.loading,
                modifier = Modifier
                    .weight(1f)
                    .testTag("translate_lookup_button"),
            ) {
                Text("Look up")
            }
            OutlinedButton(onClick = onClear, enabled = !state.loading) {
                Text("Clear")
            }
        }
        Spacer(Modifier.height(18.dp))
        TranslateResultContent(state = state)
    }
}

@Composable
private fun TranslateResultContent(state: TranslateUiState) {
    when {
        state.loading -> {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Center,
            ) {
                CircularProgressIndicator(
                    modifier = Modifier.semantics {
                        contentDescription = "Translation lookup loading"
                    },
                )
            }
        }

        state.message != null -> {
            Text(
                text = state.message,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        state.result?.hasMatches == true -> {
            TranslationMatches(result = state.result)
        }
    }
}

@Composable
private fun TranslationMatches(result: TranslationLookupResult) {
    val exactMatches = result.matches.filterNot { it.kind == TranslationMatchKind.EXAMPLE }
    val examples = result.matches.filter { it.kind == TranslationMatchKind.EXAMPLE }

    result.bestEnglish?.let { best ->
        Text(
            text = "Best match",
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.primary,
        )
        Text(
            text = best,
            style = MaterialTheme.typography.headlineSmall,
            color = MaterialTheme.colorScheme.onSurface,
        )
        Spacer(Modifier.height(12.dp))
    }

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        exactMatches.forEach { match ->
            MatchCard(match = match, modifier = Modifier.fillMaxWidth())
        }
    }

    if (examples.isNotEmpty()) {
        Spacer(Modifier.height(12.dp))
        Text(
            text = "Examples",
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.primary,
        )
        Spacer(Modifier.height(8.dp))
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            examples.forEach { MatchCard(match = it) }
        }
    }
}

@Composable
private fun MatchCard(match: TranslationMatch, modifier: Modifier = Modifier) {
    Card(modifier = modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
        ) {
            Text(
                text = match.spanish,
                style = MaterialTheme.typography.titleSmall,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = match.english,
                style = MaterialTheme.typography.bodyMedium,
            )
            if (match.note != null) {
                Text(
                    text = match.note,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun TranslatePopupPreview() {
    AprendeTheme {
        TranslatePopupContent(
            state = TranslateUiState(
                query = "perro",
                result = TranslationLookupResult(
                    query = "perro",
                    matches = listOf(
                        TranslationMatch("perro", "dog", TranslationMatchKind.WORD, "noun"),
                    ),
                ),
            ),
            sheetOpen = true,
            onOpen = {},
            onDismiss = {},
            onQueryChange = {},
            onLookup = {},
            onClear = {},
        )
    }
}

package com.magicalhippie.aprende.ui.review

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.magicalhippie.aprende.ui.lesson.ExerciseAnswer
import com.magicalhippie.aprende.ui.lesson.ExerciseFeedbackBanner
import com.magicalhippie.aprende.ui.lesson.ExerciseKind
import com.magicalhippie.aprende.ui.lesson.ExercisePrompt
import com.magicalhippie.aprende.ui.lesson.Feedback
import com.magicalhippie.aprende.ui.theme.AprendeTheme

/**
 * Stateful entry point for the Mistakes-review screen (SPEC §8 / AC7). Reuses the SAME shared
 * exercise composables as the lesson screen (P1.7) so the prompt/answer/feedback surfaces are
 * identical. On completion shows "N mistakes cleared" (the clear-on-correct behavior is in the
 * domain [com.magicalhippie.aprende.domain.review.MistakesReviewSession] — AC7).
 */
@Composable
fun MistakesReviewScreen(
    onFinished: () -> Unit,
    viewModel: MistakesReviewViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    MistakesReviewContent(
        state = state,
        onTypedInputChange = viewModel::onTypedInputChange,
        onAccentChar = viewModel::onAccentChar,
        onTileSelected = viewModel::onTileSelected,
        onTileRemoved = viewModel::onTileRemoved,
        onChoiceSelected = viewModel::onChoiceSelected,
        onSubmit = viewModel::submit,
        onContinue = viewModel::onContinue,
        onFinished = onFinished,
    )
}

/** Stateless, preview- and test-friendly content. Renders only from [MistakesReviewUiState]. */
@Composable
fun MistakesReviewContent(
    state: MistakesReviewUiState,
    onTypedInputChange: (String) -> Unit = {},
    onAccentChar: (String) -> Unit = {},
    onTileSelected: (String) -> Unit = {},
    onTileRemoved: (Int) -> Unit = {},
    onChoiceSelected: (Int) -> Unit = {},
    onSubmit: () -> Unit = {},
    onContinue: () -> Unit = {},
    onFinished: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    when {
        state.loading -> Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator() }
        state.complete -> CompletionContent(state = state, onFinished = onFinished, modifier = modifier)
        else -> ExerciseContent(
            state = state,
            onTypedInputChange = onTypedInputChange,
            onAccentChar = onAccentChar,
            onTileSelected = onTileSelected,
            onTileRemoved = onTileRemoved,
            onChoiceSelected = onChoiceSelected,
            onSubmit = onSubmit,
            onContinue = onContinue,
            modifier = modifier,
        )
    }
}

@Composable
private fun ExerciseContent(
    state: MistakesReviewUiState,
    onTypedInputChange: (String) -> Unit,
    onAccentChar: (String) -> Unit,
    onTileSelected: (String) -> Unit,
    onTileRemoved: (Int) -> Unit,
    onChoiceSelected: (Int) -> Unit,
    onSubmit: () -> Unit,
    onContinue: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
    ) {
        Text("✨ Mistakes review", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(8.dp))
        Text(state.instruction, style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(16.dp))

        ExercisePrompt(prompt = state.prompt)
        Spacer(Modifier.height(24.dp))

        ExerciseAnswer(
            kind = state.kind,
            typedInput = state.typedInput,
            wordBankTiles = state.wordBankTiles,
            selectedTiles = state.selectedTiles,
            choices = state.choices,
            selectedChoice = state.selectedChoice,
            onTypedInputChange = onTypedInputChange,
            onAccentChar = onAccentChar,
            onTileSelected = onTileSelected,
            onTileRemoved = onTileRemoved,
            onChoiceSelected = onChoiceSelected,
        )

        Spacer(Modifier.height(24.dp))
        ExerciseFeedbackBanner(feedback = state.feedback, correctAnswer = state.correctAnswer)
        Spacer(Modifier.weight(1f))

        if (state.feedback == Feedback.NONE) {
            Button(onClick = onSubmit, modifier = Modifier.fillMaxWidth()) { Text("Check") }
        } else {
            Button(onClick = onContinue, modifier = Modifier.fillMaxWidth()) { Text("Continue") }
        }
    }
}

@Composable
private fun CompletionContent(
    state: MistakesReviewUiState,
    onFinished: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        if (state.empty) {
            Text("✨ No mistakes to review!", style = MaterialTheme.typography.headlineSmall)
        } else {
            Text("✨ ${state.clearedCount} mistakes cleared", style = MaterialTheme.typography.headlineSmall)
        }
        Spacer(Modifier.height(24.dp))
        Button(onClick = onFinished, modifier = Modifier.fillMaxWidth()) { Text("Done") }
    }
}

@Preview(showBackground = true)
@Composable
private fun MistakesReviewPreview() {
    AprendeTheme {
        MistakesReviewContent(
            state = MistakesReviewUiState(
                loading = false,
                prompt = "Tengo un perro.",
                instruction = "Type this in English",
                kind = ExerciseKind.TYPED_TRANSLATION,
            ),
        )
    }
}

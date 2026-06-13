package com.magicalhippie.aprende.ui.lesson

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
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
import com.magicalhippie.aprende.ui.theme.AprendeTheme

/**
 * Stateful entry point. Obtains the Hilt-provided [LessonViewModel] (its `nodeId` comes from
 * the nav arg via `SavedStateHandle`), collects state lifecycle-aware, and defers rendering to
 * the stateless [LessonContent]. Calls [onFinished] when the learner leaves a completed lesson.
 */
@Composable
fun LessonScreen(
    onFinished: () -> Unit,
    viewModel: LessonViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    LessonContent(
        state = state,
        onTypedInputChange = viewModel::onTypedInputChange,
        onTileSelected = viewModel::onTileSelected,
        onTileRemoved = viewModel::onTileRemoved,
        onChoiceSelected = viewModel::onChoiceSelected,
        onSubmit = viewModel::submit,
        onContinue = viewModel::onContinue,
        onRestart = viewModel::restart,
        onFinished = onFinished,
    )
}

/** Stateless, preview- and test-friendly lesson content. Renders only from [LessonUiState]. */
@Composable
fun LessonContent(
    state: LessonUiState,
    onTypedInputChange: (String) -> Unit = {},
    onTileSelected: (String) -> Unit = {},
    onTileRemoved: (Int) -> Unit = {},
    onChoiceSelected: (Int) -> Unit = {},
    onSubmit: () -> Unit = {},
    onContinue: () -> Unit = {},
    onRestart: () -> Unit = {},
    onFinished: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    when {
        state.loading -> Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator() }
        state.finished -> CompletionContent(
            state = state,
            onRestart = onRestart,
            onFinished = onFinished,
            modifier = modifier,
        )
        else -> ExerciseContent(
            state = state,
            onTypedInputChange = onTypedInputChange,
            onTileSelected = onTileSelected,
            onTileRemoved = onTileRemoved,
            onChoiceSelected = onChoiceSelected,
            onSubmit = onSubmit,
            onContinue = onContinue,
            onRestart = onRestart,
            modifier = modifier,
        )
    }
}

@Composable
private fun ExerciseContent(
    state: LessonUiState,
    onTypedInputChange: (String) -> Unit,
    onTileSelected: (String) -> Unit,
    onTileRemoved: (Int) -> Unit,
    onChoiceSelected: (Int) -> Unit,
    onSubmit: () -> Unit,
    onContinue: () -> Unit,
    onRestart: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("❤️ ${state.hearts}", style = MaterialTheme.typography.titleMedium)
            OutlinedButton(onClick = onRestart) { Text("Restart") }
        }
        Spacer(Modifier.height(8.dp))
        Text(state.instruction, style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(16.dp))

        // Shared exercise rendering (reused by the Mistakes-review screen — P1.7).
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
            onTileSelected = onTileSelected,
            onTileRemoved = onTileRemoved,
            onChoiceSelected = onChoiceSelected,
        )

        Spacer(Modifier.height(24.dp))
        ExerciseFeedbackBanner(
            feedback = state.feedback,
            correctAnswer = state.correctAnswer,
            heartsGate = state.heartsGate,
        )
        Spacer(Modifier.weight(1f))

        if (state.feedback == Feedback.NONE) {
            Button(onClick = onSubmit, modifier = Modifier.fillMaxWidth()) { Text("Check") }
        } else if (!state.heartsGate) {
            Button(onClick = onContinue, modifier = Modifier.fillMaxWidth()) { Text("Continue") }
        }
    }
}

@Composable
private fun CompletionContent(
    state: LessonUiState,
    onRestart: () -> Unit,
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
        Text("✨ ¡Lección completa! ✨", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(16.dp))
        Text("+${state.xpEarned} XP", style = MaterialTheme.typography.titleLarge)
        Text("🔥 Streak: ${state.streak}", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(24.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            OutlinedButton(onClick = onRestart) { Text("Practice again") }
            Button(onClick = onFinished) { Text("Continue") }
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun TypedExercisePreview() {
    AprendeTheme {
        LessonContent(
            state = LessonUiState(
                loading = false,
                hearts = 5,
                prompt = "Tengo un perro.",
                instruction = "Type this in English",
                kind = ExerciseKind.TYPED_TRANSLATION,
            ),
        )
    }
}

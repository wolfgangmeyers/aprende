package com.magicalhippie.aprende.ui.lesson

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp

/**
 * Shared, stateless exercise-rendering composables (SPEC §7, §11.0 Tier-0 types). Extracted
 * from the lesson UI so the Mistakes-review screen (P1.7) renders the SAME exercise prompt +
 * answer surfaces without duplicating them — both call these from their own `*Content`. They
 * render only from inputs + emit callbacks (unidirectional data flow, §12.1), so they preview
 * and Robolectric-test without Hilt/ViewModels.
 *
 * The Spanish accent bar (§5.4) and the bouncy correct-answer pop (§12.1 whimsy) live here so
 * every exercise surface — lesson or review — gets them for free.
 */

/** The Spanish accent bar shown on every typed-answer surface (SPEC §5.4). */
internal val ACCENT_CHARS = listOf("ñ", "á", "é", "í", "ó", "ú", "ü", "¿", "¡")

/** The animated prompt card (the sentence to translate). Swaps with a tasteful fade (§12.1). */
@Composable
fun ExercisePrompt(prompt: String, modifier: Modifier = Modifier) {
    AnimatedContent(
        targetState = prompt,
        transitionSpec = { fadeThroughSpec() },
        label = "questionCard",
        modifier = modifier,
    ) { p ->
        Text(
            text = p,
            style = MaterialTheme.typography.headlineSmall,
            color = MaterialTheme.colorScheme.primary,
        )
    }
}

/** Renders the answer surface for the given [kind] (typed / word-bank / multiple-choice). */
@Composable
fun ExerciseAnswer(
    kind: ExerciseKind,
    typedInput: String,
    wordBankTiles: List<String>,
    selectedTiles: List<String>,
    choices: List<String>,
    selectedChoice: Int,
    onTypedInputChange: (String) -> Unit,
    onTileSelected: (String) -> Unit,
    onTileRemoved: (Int) -> Unit,
    onChoiceSelected: (Int) -> Unit,
) {
    when (kind) {
        ExerciseKind.TYPED_TRANSLATION -> TypedTranslation(
            input = typedInput,
            onInputChange = onTypedInputChange,
        )
        ExerciseKind.WORD_BANK -> WordBank(
            tiles = wordBankTiles,
            selected = selectedTiles,
            onTileSelected = onTileSelected,
            onTileRemoved = onTileRemoved,
        )
        ExerciseKind.MULTIPLE_CHOICE -> MultipleChoice(
            choices = choices,
            selected = selectedChoice,
            onChoiceSelected = onChoiceSelected,
        )
    }
}

@Composable
private fun TypedTranslation(
    input: String,
    onInputChange: (String) -> Unit,
) {
    var textFieldValue by remember {
        mutableStateOf(TextFieldValue(text = input, selection = TextRange(input.length)))
    }

    LaunchedEffect(input) {
        if (input != textFieldValue.text) {
            textFieldValue = TextFieldValue(text = input, selection = TextRange(input.length))
        }
    }

    OutlinedTextField(
        value = textFieldValue,
        onValueChange = { value ->
            textFieldValue = value
            if (value.text != input) {
                onInputChange(value.text)
            }
        },
        modifier = Modifier
            .fillMaxWidth()
            .semantics { contentDescription = "Answer input" },
        label = { Text("Your answer") },
        singleLine = true,
        keyboardOptions = KeyboardOptions(
            capitalization = KeyboardCapitalization.None,
            keyboardType = KeyboardType.Text,
            imeAction = ImeAction.Done,
        ),
    )
    Spacer(Modifier.height(8.dp))
    // Accent bar (§5.4) — a Spanish OS keyboard is never required.
    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        items(ACCENT_CHARS) { ch ->
            OutlinedButton(
                onClick = {
                    textFieldValue = textFieldValue.insertAtSelection(ch)
                    onInputChange(textFieldValue.text)
                },
            ) {
                Text(ch)
            }
        }
    }
}

private fun TextFieldValue.insertAtSelection(inserted: String): TextFieldValue {
    val start = selection.min.coerceIn(0, text.length)
    val end = selection.max.coerceIn(0, text.length)
    val newText = text.replaceRange(start, end, inserted)
    val cursor = start + inserted.length
    return TextFieldValue(text = newText, selection = TextRange(cursor))
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun WordBank(
    tiles: List<String>,
    selected: List<String>,
    onTileSelected: (String) -> Unit,
    onTileRemoved: (Int) -> Unit,
) {
    Text("Your answer:", style = MaterialTheme.typography.labelLarge)
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        selected.forEachIndexed { index, tile ->
            AssistChip(onClick = { onTileRemoved(index) }, label = { Text(tile) })
        }
    }
    Spacer(Modifier.height(16.dp))
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        tiles.forEach { tile ->
            OutlinedButton(onClick = { onTileSelected(tile) }) { Text(tile) }
        }
    }
}

@Composable
private fun MultipleChoice(
    choices: List<String>,
    selected: Int,
    onChoiceSelected: (Int) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        choices.forEachIndexed { index, choice ->
            if (index == selected) {
                Button(onClick = { onChoiceSelected(index) }, modifier = Modifier.fillMaxWidth()) {
                    Text(choice)
                }
            } else {
                OutlinedButton(onClick = { onChoiceSelected(index) }, modifier = Modifier.fillMaxWidth()) {
                    Text(choice)
                }
            }
        }
    }
}

/** Correct/incorrect banner with a bouncy "pop" on correct (§12.1 whimsy/delight). */
@Composable
fun ExerciseFeedbackBanner(feedback: Feedback, correctAnswer: String, heartsGate: Boolean = false) {
    val pop by animateFloatAsState(
        targetValue = if (feedback == Feedback.CORRECT) 1f else 0.9f,
        animationSpec = spring(dampingRatio = Spring.DampingRatioMediumBouncy, stiffness = Spring.StiffnessLow),
        label = "correctPop",
    )
    when (feedback) {
        Feedback.CORRECT -> Text(
            "✨ ¡Correcto!",
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.tertiary,
            modifier = Modifier.scale(pop),
        )
        Feedback.INCORRECT -> Column {
            Text(
                "Not quite",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.error,
            )
            if (correctAnswer.isNotBlank()) {
                Text("Answer: $correctAnswer", style = MaterialTheme.typography.bodyMedium)
            }
            if (heartsGate) {
                Text(
                    "Out of hearts — come back when they refill.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.error,
                )
            }
        }
        Feedback.NONE -> Unit
    }
}

internal fun fadeThroughSpec() =
    fadeIn(spring(stiffness = Spring.StiffnessLow)) togetherWith
        fadeOut(spring(stiffness = Spring.StiffnessLow))

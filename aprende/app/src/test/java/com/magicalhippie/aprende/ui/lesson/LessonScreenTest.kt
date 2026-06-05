package com.magicalhippie.aprende.ui.lesson

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import com.magicalhippie.aprende.ui.theme.AprendeTheme
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * Robolectric Compose tests (P1.6) for the stateless [LessonContent]: a typed-translation
 * exercise renders the prompt + accent bar (§5.4), typing + Check drive the callbacks, and a
 * CORRECT-feedback state shows the celebratory banner. No Hilt / no audio (Tier-0, AC1).
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class LessonScreenTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun typedTranslation_rendersPromptAndAccentBar_andAcceptsInput() {
        var typed = ""
        var submitted = false
        composeRule.setContent {
            AprendeTheme {
                LessonContent(
                    state = LessonUiState(
                        loading = false,
                        hearts = 5,
                        prompt = "Tengo un perro.",
                        instruction = "Type this in English",
                        kind = ExerciseKind.TYPED_TRANSLATION,
                    ),
                    onTypedInputChange = { typed = it },
                    onSubmit = { submitted = true },
                )
            }
        }

        composeRule.onNodeWithText("Tengo un perro.").assertIsDisplayed()
        // Accent bar present (§5.4).
        composeRule.onNodeWithText("ñ").assertIsDisplayed()

        composeRule.onNodeWithContentDescription("Answer input").performTextInput("I have a dog")
        assertTrue(typed.isNotEmpty())

        composeRule.onNodeWithText("Check").performClick()
        assertTrue(submitted)
    }

    @Test
    fun correctFeedback_showsCelebration_andContinueAdvances() {
        var continued = false
        composeRule.setContent {
            AprendeTheme {
                LessonContent(
                    state = LessonUiState(
                        loading = false,
                        hearts = 5,
                        prompt = "Tengo un perro.",
                        kind = ExerciseKind.TYPED_TRANSLATION,
                        feedback = Feedback.CORRECT,
                    ),
                    onContinue = { continued = true },
                )
            }
        }

        composeRule.onNodeWithText("✨ ¡Correcto!").assertIsDisplayed()
        composeRule.onNodeWithText("Continue").performClick()
        assertTrue(continued)
    }

    @Test
    fun lessonContent_restartButton_firesCallback() {
        var restarted = false
        composeRule.setContent {
            AprendeTheme {
                LessonContent(
                    state = LessonUiState(
                        loading = false,
                        hearts = 5,
                        prompt = "I have a dog.",
                        instruction = "Choose the correct translation",
                        kind = ExerciseKind.MULTIPLE_CHOICE,
                        choices = listOf("Tengo un perro.", "Quiero agua."),
                    ),
                    onRestart = { restarted = true },
                )
            }
        }

        composeRule.onNodeWithText("Restart").performClick()
        assertTrue(restarted)
    }

    @Test
    fun multipleChoice_rendersOptions_andSelectionCallback() {
        var selected = -1
        composeRule.setContent {
            AprendeTheme {
                LessonContent(
                    state = LessonUiState(
                        loading = false,
                        hearts = 5,
                        prompt = "Tengo un perro.",
                        instruction = "Choose the correct translation",
                        kind = ExerciseKind.MULTIPLE_CHOICE,
                        choices = listOf("we're going home", "i have a dog", "i want water", "i have the water"),
                    ),
                    onChoiceSelected = { selected = it },
                )
            }
        }

        composeRule.onNodeWithText("Tengo un perro.").assertIsDisplayed()
        composeRule.onNodeWithText("we're going home").assertIsDisplayed()
        composeRule.onNodeWithText("i have a dog").assertIsDisplayed()

        composeRule.onNodeWithText("i have a dog").performClick()
        assertEquals(1, selected)
    }

    @Test
    fun completionState_showsXpAndStreak() {
        var finished = false
        var restarted = false
        composeRule.setContent {
            AprendeTheme {
                LessonContent(
                    state = LessonUiState(loading = false, finished = true, xpEarned = 10, streak = 1),
                    onRestart = { restarted = true },
                    onFinished = { finished = true },
                )
            }
        }

        composeRule.onNodeWithText("+10 XP").assertIsDisplayed()
        composeRule.onNodeWithText("🔥 Streak: 1").assertIsDisplayed()
        composeRule.onNodeWithText("Practice again").performClick()
        assertEquals(true, restarted)
        composeRule.onNodeWithText("Continue").performClick()
        assertEquals(true, finished)
    }
}

package com.magicalhippie.aprende.ui.words

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import com.magicalhippie.aprende.ui.theme.AprendeTheme
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * Robolectric Compose test for the Words list (P1.7, SPEC §8/§6.6): renders [WordsContent] from a
 * seeded weakest-first state and asserts lemmas/glosses and the strength meter show. Also covers
 * the pure strength-bucketing helper.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class WordsScreenTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun wordsContent_displaysWordsAndStrength() {
        val state = WordsUiState(
            words = listOf(
                WordUiModel(1, "perro", "dog", strengthBars = 1, isStrong = false),
                WordUiModel(2, "agua", "water", strengthBars = 4, isStrong = true),
            ),
            loading = false,
        )
        composeRule.setContent { AprendeTheme { WordsContent(state = state) } }

        composeRule.onNodeWithText("perro").assertIsDisplayed()
        composeRule.onNodeWithText("dog").assertIsDisplayed()
        composeRule.onNodeWithText("agua").assertIsDisplayed()
        composeRule.onNodeWithContentDescription("perro, dog, strength 1").assertIsDisplayed()
        composeRule.onNodeWithContentDescription("agua, water, strength 4").assertIsDisplayed()
    }

    @Test
    fun strengthBars_bucketsRecall() {
        assertEquals(1, WordsViewModel.strengthBars(0.0))   // a seen word is always >= 1 bar
        assertEquals(1, WordsViewModel.strengthBars(0.1))
        assertEquals(2, WordsViewModel.strengthBars(0.5))
        assertEquals(4, WordsViewModel.strengthBars(1.0))
    }
}

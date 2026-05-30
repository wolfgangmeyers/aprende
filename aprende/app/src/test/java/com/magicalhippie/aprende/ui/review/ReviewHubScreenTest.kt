package com.magicalhippie.aprende.ui.review

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import com.magicalhippie.aprende.ui.theme.AprendeTheme
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * Robolectric Compose test for the Review hub (P1.7, SPEC §8): renders [ReviewHubContent] from a
 * seeded state and asserts the counts show and a tap fires the right navigation callback.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ReviewHubScreenTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun reviewHub_displaysCounts() {
        composeRule.setContent {
            AprendeTheme {
                ReviewHubContent(state = ReviewHubUiState(mistakesQueued = 3, wordsLearned = 42, loading = false))
            }
        }
        composeRule.onNodeWithText("3 queued").assertIsDisplayed()
        composeRule.onNodeWithText("42 learned").assertIsDisplayed()
    }

    @Test
    fun reviewHub_mistakesTap_firesCallback() {
        var tappedMistakes = false
        composeRule.setContent {
            AprendeTheme {
                ReviewHubContent(
                    state = ReviewHubUiState(mistakesQueued = 1, wordsLearned = 1, loading = false),
                    onMistakes = { tappedMistakes = true },
                )
            }
        }
        composeRule.onNodeWithText("Mistakes").performClick()
        assertTrue(tappedMistakes)
    }
}

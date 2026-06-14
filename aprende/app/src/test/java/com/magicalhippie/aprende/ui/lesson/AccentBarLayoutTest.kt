package com.magicalhippie.aprende.ui.lesson

import androidx.compose.foundation.layout.width
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.hasNoScrollAction
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.unit.dp
import com.magicalhippie.aprende.ui.review.MistakesReviewContent
import com.magicalhippie.aprende.ui.review.MistakesReviewUiState
import com.magicalhippie.aprende.ui.theme.AprendeTheme
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class AccentBarLayoutTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun lessonAccentButtons_wrapWithinNarrowWidth() {
        composeRule.setContent {
            AprendeTheme {
                LessonContent(
                    state = LessonUiState(
                        loading = false,
                        hearts = 5,
                        prompt = "Tengo un perro.",
                        instruction = "Type this in Spanish",
                        kind = ExerciseKind.TYPED_TRANSLATION,
                    ),
                    modifier = Modifier.width(160.dp),
                )
            }
        }

        assertAccentButtonsWrapWithinBar()
    }

    @Test
    fun mistakesReviewAccentButtons_wrapWithinNarrowWidth() {
        composeRule.setContent {
            AprendeTheme {
                MistakesReviewContent(
                    state = MistakesReviewUiState(
                        loading = false,
                        prompt = "I have a dog.",
                        instruction = "Type this in Spanish",
                        kind = ExerciseKind.TYPED_TRANSLATION,
                    ),
                    modifier = Modifier.width(160.dp),
                )
            }
        }

        assertAccentButtonsWrapWithinBar()
    }

    private fun assertAccentButtonsWrapWithinBar() {
        composeRule.onNodeWithTag(ACCENT_BAR_TEST_TAG).assert(hasNoScrollAction())
        val firstBounds = composeRule.onNodeWithTag(accentCharTestTag("ñ")).getUnclippedBoundsInRoot()
        val lastBounds = composeRule.onNodeWithTag(accentCharTestTag("¡")).getUnclippedBoundsInRoot()

        assertTrue(
            "accent buttons should wrap to later rows instead of forming a single horizontal strip",
            lastBounds.top > firstBounds.top,
        )
    }
}

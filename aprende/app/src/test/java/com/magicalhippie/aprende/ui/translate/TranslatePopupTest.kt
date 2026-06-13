package com.magicalhippie.aprende.ui.translate

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import com.magicalhippie.aprende.domain.translation.TranslationLookupResult
import com.magicalhippie.aprende.domain.translation.TranslationMatch
import com.magicalhippie.aprende.domain.translation.TranslationMatchKind
import com.magicalhippie.aprende.ui.theme.AprendeTheme
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class TranslatePopupTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun floatingButtonOpensPopup() {
        var opened = false
        composeRule.setContent {
            AprendeTheme {
                TranslatePopupContent(
                    state = TranslateUiState(),
                    sheetOpen = false,
                    onOpen = { opened = true },
                    onDismiss = {},
                    onQueryChange = {},
                    onLookup = {},
                    onClear = {},
                )
            }
        }

        composeRule.onNodeWithContentDescription("Open Spanish to English lookup").performClick()

        assertTrue(opened)
    }

    @Test
    fun popupAcceptsQueryAndRunsLookup() {
        var query by mutableStateOf("")
        var lookedUp = false
        composeRule.setContent {
            AprendeTheme {
                TranslateSheetContent(
                    state = TranslateUiState(query = query),
                    onQueryChange = { query = it },
                    onLookup = { lookedUp = true },
                    onClear = { query = "" },
                )
            }
        }

        composeRule.onNodeWithTag("translate_query").performTextInput("perro")
        composeRule.onNodeWithTag("translate_lookup_button").performClick()

        assertEquals("perro", query)
        assertTrue(lookedUp)
    }

    @Test
    fun popupDisplaysBestMatchAndExamples() {
        composeRule.setContent {
            AprendeTheme {
                TranslateSheetContent(
                    state = TranslateUiState(
                        query = "perro",
                        result = TranslationLookupResult(
                            query = "perro",
                            matches = listOf(
                                TranslationMatch("perro", "dog", TranslationMatchKind.WORD, "noun"),
                                TranslationMatch(
                                    "Tengo un perro.",
                                    "I have a dog.",
                                    TranslationMatchKind.EXAMPLE,
                                ),
                            ),
                        ),
                    ),
                    onQueryChange = {},
                    onLookup = {},
                    onClear = {},
                )
            }
        }

        composeRule.onNodeWithText("Best match").assertIsDisplayed()
        composeRule.onNodeWithText("noun").assertIsDisplayed()
        composeRule.onNodeWithText("Tengo un perro.").performScrollTo()
        composeRule.onNodeWithText("Tengo un perro.").assertIsDisplayed()
        composeRule.onNodeWithText("I have a dog.").performScrollTo()
        composeRule.onNodeWithText("I have a dog.").assertIsDisplayed()
    }

    @Test
    fun popupDoesNotPromoteExampleOnlyResultToBestMatch() {
        composeRule.setContent {
            AprendeTheme {
                TranslateSheetContent(
                    state = TranslateUiState(
                        query = "tengo",
                        result = TranslationLookupResult(
                            query = "tengo",
                            matches = listOf(
                                TranslationMatch(
                                    "Tengo un perro.",
                                    "I have a dog.",
                                    TranslationMatchKind.EXAMPLE,
                                ),
                            ),
                        ),
                    ),
                    onQueryChange = {},
                    onLookup = {},
                    onClear = {},
                )
            }
        }

        composeRule.onNodeWithText("Best match").assertDoesNotExist()
        composeRule.onNodeWithText("Examples").assertIsDisplayed()
        composeRule.onNodeWithText("I have a dog.").performScrollTo()
        composeRule.onNodeWithText("I have a dog.").assertIsDisplayed()
    }
}

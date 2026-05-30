package com.magicalhippie.aprende.ui.about

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import com.magicalhippie.aprende.ui.theme.AprendeTheme
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * **AC14 (UI half)** — the attribution screen renders the seeded credits (SPEC §4.5). Renders
 * the stateless [AttributionContent] from a seeded state (no Hilt) and asserts the source labels
 * and licenses are displayed. The data half is [com.magicalhippie.aprende.data.content.AttributionAc14Test].
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class AttributionScreenTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun attributionContent_displaysCredits() {
        val state = AttributionUiState(
            credits = listOf(
                AttributionUiModel("Tatoeba", "tatoeba", "CC-BY-2.0-FR"),
                AttributionUiModel("Wiktionary", "wiktionary", "CC-BY-SA-3.0"),
            ),
            loading = false,
        )

        composeRule.setContent { AprendeTheme { AttributionContent(state = state) } }

        composeRule.onNodeWithText("Tatoeba").assertIsDisplayed()
        composeRule.onNodeWithText("Wiktionary").assertIsDisplayed()
        composeRule.onNodeWithText("License: CC-BY-2.0-FR").assertIsDisplayed()
        composeRule.onNodeWithText("License: CC-BY-SA-3.0").assertIsDisplayed()
    }
}

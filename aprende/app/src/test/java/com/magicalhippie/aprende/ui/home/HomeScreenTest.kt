package com.magicalhippie.aprende.ui.home

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import com.magicalhippie.aprende.ui.theme.AprendeTheme
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * Robolectric Compose render test (P1.6): renders the stateless [HomeContent] from a seeded
 * [HomeUiState] (no Hilt) and asserts the node list + streak/XP/hearts stats are shown and a
 * node tap fires the navigation callback.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class HomeScreenTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun homeContent_displaysNodesAndStats() {
        val state = HomeUiState(
            nodes = listOf(NodeUiModel(1, "Basics 1"), NodeUiModel(2, "Basics 2")),
            streak = 4,
            totalXp = 120,
            hearts = 5,
            loading = false,
        )

        composeRule.setContent {
            AprendeTheme { HomeContent(state = state) }
        }

        composeRule.onNodeWithText("Basics 1").assertIsDisplayed()
        composeRule.onNodeWithText("Basics 2").assertIsDisplayed()
        composeRule.onNodeWithContentDescription("Streak: 4 days").assertIsDisplayed()
        composeRule.onNodeWithContentDescription("Total XP: 120").assertIsDisplayed()
        composeRule.onNodeWithContentDescription("Hearts: 5").assertIsDisplayed()
    }

    @Test
    fun homeContent_nodeTap_firesCallback() {
        var tapped = -1L
        val state = HomeUiState(
            nodes = listOf(NodeUiModel(7, "Basics 1")),
            loading = false,
        )

        composeRule.setContent {
            AprendeTheme { HomeContent(state = state, onNodeClick = { tapped = it }) }
        }

        composeRule.onNodeWithText("Basics 1").performClick()
        assertEquals(7L, tapped)
    }

    @Test
    fun homeContent_lockedNode_doesNotNavigate() {
        var tapped = -1L
        val state = HomeUiState(
            nodes = listOf(NodeUiModel(2, "Basics 2", unlocked = false)),
            loading = false,
        )

        composeRule.setContent {
            AprendeTheme { HomeContent(state = state, onNodeClick = { tapped = it }) }
        }

        composeRule.onNodeWithText("Basics 2").performClick()
        assertEquals("a locked node must not fire the navigation callback", -1L, tapped)
    }
}

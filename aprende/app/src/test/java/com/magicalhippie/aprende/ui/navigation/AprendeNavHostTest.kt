package com.magicalhippie.aprende.ui.navigation

import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import androidx.navigation.testing.TestNavHostController
import androidx.navigation.compose.ComposeNavigator
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class AprendeNavHostTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun freshLessonNavOptions_popToHomeAndUseSingleTop() {
        val options = freshLessonNavOptions()

        assertEquals(Routes.HOME, options.popUpToRoute)
        assertFalse("home remains on the back stack", options.isPopUpToInclusive())
        assertFalse("fresh lesson tap should not restore a stale saved queue", options.shouldRestoreState())
        assertTrue("repeat taps should reuse the top lesson destination", options.shouldLaunchSingleTop())
    }

    @Test
    fun retappingLessonFromHomeCreatesFreshLessonBackStackEntry() {
        lateinit var navController: NavHostController
        composeRule.setContent {
            navController = TestNavHostController(LocalContext.current).apply {
                navigatorProvider.addNavigator(ComposeNavigator())
            }
            NavHost(navController = navController, startDestination = Routes.HOME) {
                composable(Routes.HOME) {
                    Button(onClick = { navController.navigate(Routes.lesson(1), freshLessonNavOptions()) }) {
                        Text("A1 Unit 1.1")
                    }
                }
                composable(
                    route = Routes.LESSON_PATTERN,
                    arguments = listOf(navArgument(Routes.ARG_NODE_ID) { type = NavType.LongType }),
                ) {
                    Text("Lesson")
                }
            }
        }

        composeRule.onNodeWithText("A1 Unit 1.1").performClick()
        composeRule.runOnIdle {
            navController.currentBackStackEntry!!.savedStateHandle[LESSON_QUEUE_KEY] = arrayListOf(999L)
            assertEquals(arrayListOf(999L), navController.currentBackStackEntry!!.savedStateHandle[LESSON_QUEUE_KEY])
            navController.popBackStack(Routes.HOME, inclusive = false)
        }

        composeRule.onNodeWithText("A1 Unit 1.1").performClick()

        composeRule.runOnIdle {
            assertEquals(Routes.LESSON_PATTERN, navController.currentDestination?.route)
            assertNull(
                "retapping from Home must not reuse a saved lesson queue",
                navController.currentBackStackEntry!!.savedStateHandle.get<ArrayList<Long>>(LESSON_QUEUE_KEY),
            )
        }
    }

    @Test
    fun globalChrome_keepsTranslateAvailableAcrossRoutes() {
        lateinit var navController: NavHostController
        composeRule.setContent {
            navController = TestNavHostController(LocalContext.current).apply {
                navigatorProvider.addNavigator(ComposeNavigator())
            }
            AprendeGlobalChrome(
                translatePopup = { modifier -> Button(onClick = {}, modifier = modifier.testTag("translate_fab")) { Text("EN") } },
            ) { contentModifier ->
                NavHost(
                    navController = navController,
                    startDestination = "first",
                    modifier = contentModifier,
                ) {
                    composable("first") {
                        Button(onClick = { navController.navigate("second") }) { Text("Next") }
                    }
                    composable("second") {
                        Text("Second route")
                    }
                }
            }
        }

        composeRule.onNodeWithTag("translate_fab").assertExists()
        composeRule.onNodeWithText("Next").performClick()
        composeRule.onNodeWithText("Second route").assertExists()
        composeRule.onNodeWithTag("translate_fab").assertExists()
    }

    @Test
    fun globalChrome_raisesTranslateButtonAboveBottomAction() {
        composeRule.setContent {
            AprendeGlobalChrome(
                translatePopup = { modifier -> Button(onClick = {}, modifier = modifier.testTag("translate_fab")) { Text("EN") } },
            ) { contentModifier ->
                Box(contentModifier) {
                    Button(
                        onClick = {},
                        modifier = Modifier
                            .align(Alignment.BottomCenter)
                            .fillMaxWidth()
                            .testTag("bottom_action"),
                    ) {
                        Text("Check")
                    }
                }
            }
        }

        val translateBounds = composeRule.onNodeWithTag("translate_fab").getUnclippedBoundsInRoot()
        val actionBounds = composeRule.onNodeWithTag("bottom_action").getUnclippedBoundsInRoot()

        assertTrue(
            "translate button should sit above bottom primary actions",
            translateBounds.bottom <= actionBounds.top,
        )
    }

    private companion object {
        const val LESSON_QUEUE_KEY = "lesson_queue_ids"
    }
}

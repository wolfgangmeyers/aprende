package com.magicalhippie.aprende.ui.navigation

import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.test.junit4.createComposeRule
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

    private companion object {
        const val LESSON_QUEUE_KEY = "lesson_queue_ids"
    }
}

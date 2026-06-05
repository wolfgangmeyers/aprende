package com.magicalhippie.aprende.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.NavOptions
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import androidx.navigation.navOptions
import com.magicalhippie.aprende.ui.about.AttributionScreen
import com.magicalhippie.aprende.ui.home.HomeScreen
import com.magicalhippie.aprende.ui.lesson.LessonScreen
import com.magicalhippie.aprende.ui.review.MistakesReviewScreen
import com.magicalhippie.aprende.ui.review.ReviewHubScreen
import com.magicalhippie.aprende.ui.settings.BackupScreen
import com.magicalhippie.aprende.ui.settings.SettingsScreen
import com.magicalhippie.aprende.ui.vocab.VocabPracticeScreen
import com.magicalhippie.aprende.ui.words.WordsScreen

/**
 * The app's navigation graph (SPEC §12.2, Navigation Compose). Destinations:
 *  - Home/Path + a lesson session for a tapped node (P1.6).
 *  - Review hub → {Mistakes review, Words, Vocab practice} (P1.7, §8).
 *  - Settings → {Backup/restore, Credits/attribution} (P1.8, §11/§4.5).
 *
 * Routes are plain string constants; the `nodeId` lesson argument is passed in the path and
 * read back via `SavedStateHandle` (also what AC12's process-death restore relies on). Each
 * leaf returns to its parent via `popBackStack` (back/Done buttons), so the offline loop holds.
 */
object Routes {
    const val HOME = "home"
    const val LESSON = "lesson"
    const val ARG_NODE_ID = "nodeId"
    const val LESSON_PATTERN = "$LESSON/{$ARG_NODE_ID}"

    const val REVIEW_HUB = "review"
    const val MISTAKES = "review/mistakes"
    const val WORDS = "review/words"
    const val VOCAB = "review/vocab"

    const val SETTINGS = "settings"
    const val BACKUP = "settings/backup"
    const val ATTRIBUTION = "settings/about"

    fun lesson(nodeId: Long): String = "$LESSON/$nodeId"
}

@Composable
fun AprendeNavHost(
    navController: NavHostController = rememberNavController(),
) {
    NavHost(navController = navController, startDestination = Routes.HOME) {
        composable(Routes.HOME) {
            HomeScreen(
                onNodeClick = { nodeId ->
                    navController.navigate(Routes.lesson(nodeId), freshLessonNavOptions())
                },
                onReviewClick = { navController.navigate(Routes.REVIEW_HUB) },
                onSettingsClick = { navController.navigate(Routes.SETTINGS) },
            )
        }
        composable(
            route = Routes.LESSON_PATTERN,
            arguments = listOf(navArgument(Routes.ARG_NODE_ID) { type = NavType.LongType }),
        ) {
            LessonScreen(
                onFinished = { navController.popBackStack(Routes.HOME, inclusive = false) },
            )
        }

        // --- Review hub + leaves (P1.7, §8) ---
        composable(Routes.REVIEW_HUB) {
            ReviewHubScreen(
                onMistakes = { navController.navigate(Routes.MISTAKES) },
                onWords = { navController.navigate(Routes.WORDS) },
                onVocab = { navController.navigate(Routes.VOCAB) },
            )
        }
        composable(Routes.MISTAKES) {
            MistakesReviewScreen(onFinished = { navController.popBackStack(Routes.REVIEW_HUB, inclusive = false) })
        }
        composable(Routes.WORDS) { WordsScreen() }
        composable(Routes.VOCAB) {
            VocabPracticeScreen(onFinished = { navController.popBackStack(Routes.REVIEW_HUB, inclusive = false) })
        }

        // --- Settings/About (P1.8, §11/§4.5) ---
        composable(Routes.SETTINGS) {
            SettingsScreen(
                onBackup = { navController.navigate(Routes.BACKUP) },
                onAttribution = { navController.navigate(Routes.ATTRIBUTION) },
            )
        }
        composable(Routes.BACKUP) { BackupScreen() }
        composable(Routes.ATTRIBUTION) { AttributionScreen() }
    }
}

internal fun freshLessonNavOptions(): NavOptions = navOptions {
    popUpTo(Routes.HOME) { inclusive = false }
    launchSingleTop = true
}

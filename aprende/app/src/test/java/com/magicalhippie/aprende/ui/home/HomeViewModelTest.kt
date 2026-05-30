package com.magicalhippie.aprende.ui.home

import app.cash.turbine.test
import com.magicalhippie.aprende.domain.FakeContentRepository
import com.magicalhippie.aprende.domain.FakeProgressRepository
import com.magicalhippie.aprende.domain.MutableClock
import com.magicalhippie.aprende.domain.gamification.NEW_USER_STATS
import com.magicalhippie.aprende.domain.model.Node
import com.magicalhippie.aprende.domain.model.NodeProgress
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

/**
 * Unit test for the home ViewModel's StateFlow (P1.6, §12.1): the node list comes from the
 * (read-only) content repo, and streak / total XP / lazily-derived hearts come from
 * [com.magicalhippie.aprende.domain.model.UserStats].
 */
class HomeViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private val clock = MutableClock()

    @Before fun setUp() { Dispatchers.setMain(testDispatcher) }
    @After fun tearDown() { Dispatchers.resetMain() }

    @Test
    fun `uiState exposes nodes and live stats`() = runTest(testDispatcher) {
        val content = FakeContentRepository(
            nodes = listOf(Node(1, "Basics 1", 0), Node(2, "Basics 2", 1)),
        )
        val progress = FakeProgressRepository()
        progress.upsertUserStats(NEW_USER_STATS.copy(totalXp = 42, streakLength = 3))

        val vm = HomeViewModel(content, progress, clock)

        vm.uiState.test {
            // initial value (before init coroutine + flow run)
            awaitItem()
            runCurrent()
            val state = expectMostRecentItem()
            assertEquals(listOf("Basics 1", "Basics 2"), state.nodes.map { it.title })
            assertEquals(42, state.totalXp)
            assertEquals(3, state.streak)
            assertEquals(5, state.hearts) // full hearts for a new learner
            cancelAndIgnoreRemainingEvents()
        }
    }

    @Test
    fun `home unlocks the next node once the previous is completed`() = runTest(testDispatcher) {
        val content = FakeContentRepository(
            nodes = listOf(Node(1, "Basics 1", 0), Node(2, "Basics 2", 1)),
        )
        val progress = FakeProgressRepository()
        val vm = HomeViewModel(content, progress, clock)

        vm.uiState.test {
            awaitItem()
            runCurrent()
            val before = expectMostRecentItem()
            assertEquals(true, before.nodes.first { it.nodeId == 1L }.unlocked)
            assertEquals("second node starts locked", false, before.nodes.first { it.nodeId == 2L }.unlocked)

            // Completing node 1 must unlock node 2.
            progress.upsertNodeProgress(NodeProgress(1, level = 1, legendary = false, completedAtMillis = 1L))
            runCurrent()
            val after = expectMostRecentItem()
            assertEquals(true, after.nodes.first { it.nodeId == 1L }.completed)
            assertEquals("second node unlocks after first completes", true, after.nodes.first { it.nodeId == 2L }.unlocked)
            cancelAndIgnoreRemainingEvents()
        }
    }
}

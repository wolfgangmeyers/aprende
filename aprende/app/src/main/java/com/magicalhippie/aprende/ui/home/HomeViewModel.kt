package com.magicalhippie.aprende.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.magicalhippie.aprende.domain.gamification.Hearts
import com.magicalhippie.aprende.domain.gamification.NEW_USER_STATS
import com.magicalhippie.aprende.domain.model.Node
import com.magicalhippie.aprende.domain.model.UserStats
import com.magicalhippie.aprende.domain.repository.ContentRepository
import com.magicalhippie.aprende.domain.repository.ProgressRepository
import com.magicalhippie.aprende.domain.session.PathUnlock
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.time.Clock
import javax.inject.Inject

/** A Path node as the home list renders it (SPEC §7, §12.2). */
data class NodeUiModel(
    val nodeId: Long,
    val title: String,
    /** Whether the learner may start this node (positional unlock, §4.4). */
    val unlocked: Boolean = true,
    /** Whether the node's lesson has been completed at least once (crown level ≥ 1). */
    val completed: Boolean = false,
    val level: Int = 0,
)

/**
 * Immutable UI state for the home/Path screen (unidirectional data flow, §12.1). Combines the
 * read-only node list with the learner's live streak / total XP / current hearts.
 */
data class HomeUiState(
    val greeting: String = WELCOME_MESSAGE,
    val nodes: List<NodeUiModel> = emptyList(),
    val streak: Int = 0,
    val totalXp: Int = 0,
    val hearts: Int = Hearts.MAX,
    val loading: Boolean = true,
) {
    companion object {
        const val WELCOME_MESSAGE = "¡Bienvenido a Aprende!"
    }
}

/**
 * Home/Path ViewModel. Loads the (read-only) node list once and observes [UserStats] live, so
 * streak/XP/heart changes from completing a lesson reflect on return to the Path. Hearts are
 * **lazily derived** from stored count + elapsed time vs the injected [Clock] (SPEC §6.5/§9) —
 * never a background job — mirroring `HeartsUseCase.currentHearts()`.
 *
 * State is exposed as a single immutable [HomeUiState] via `stateIn(WhileSubscribed)` (§12.1),
 * collected with `collectAsStateWithLifecycle` in [HomeScreen].
 */
@HiltViewModel
class HomeViewModel @Inject constructor(
    private val content: ContentRepository,
    private val progress: ProgressRepository,
    private val clock: Clock,
) : ViewModel() {

    private val nodes = MutableStateFlow<List<Node>>(emptyList())
    private val loaded = MutableStateFlow(false)

    init {
        viewModelScope.launch {
            nodes.value = content.nodes().sortedBy(Node::displayOrder)
            loaded.value = true
        }
    }

    val uiState: StateFlow<HomeUiState> =
        combine(
            nodes,
            progress.userStatsFlow(),
            progress.nodeProgressFlow(),
            loaded,
        ) { nodeList, stats, nodeProgress, isLoaded ->
            val s: UserStats = stats ?: NEW_USER_STATS
            // Positional unlock (§4.4): node N+1 opens once node N is complete.
            val pathStates = PathUnlock.compute(nodeList, nodeProgress.associateBy { it.nodeId })
            HomeUiState(
                nodes = pathStates.map {
                    NodeUiModel(
                        nodeId = it.node.nodeId,
                        title = it.node.title,
                        unlocked = it.unlocked,
                        completed = it.completed,
                        level = it.level,
                    )
                },
                streak = s.streakLength,
                totalXp = s.totalXp,
                hearts = Hearts.current(s, clock.millis()),
                loading = !isLoaded,
            )
        }.stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(STOP_TIMEOUT_MILLIS),
            initialValue = HomeUiState(),
        )

    companion object {
        const val WELCOME_MESSAGE = HomeUiState.WELCOME_MESSAGE
        private const val STOP_TIMEOUT_MILLIS = 5_000L
    }
}

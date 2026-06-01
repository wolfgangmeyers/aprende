package com.magicalhippie.aprende.ui.home

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.magicalhippie.aprende.ui.theme.AprendeTheme

/**
 * Stateful entry point. Obtains the Hilt-provided [HomeViewModel], collects its [HomeUiState]
 * lifecycle-aware (collection pauses when backgrounded — §12.1), and defers all rendering to
 * the stateless [HomeContent] so the UI is testable without Hilt.
 */
@Composable
fun HomeScreen(
    onNodeClick: (Long) -> Unit,
    onReviewClick: () -> Unit = {},
    onSettingsClick: () -> Unit = {},
    viewModel: HomeViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    HomeContent(
        state = uiState,
        onNodeClick = onNodeClick,
        onReviewClick = onReviewClick,
        onSettingsClick = onSettingsClick,
    )
}

/** Stateless, preview- and test-friendly content. Renders only from [HomeUiState]. */
@Composable
fun HomeContent(
    state: HomeUiState,
    onNodeClick: (Long) -> Unit = {},
    onReviewClick: () -> Unit = {},
    onSettingsClick: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = state.greeting,
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.primary,
        )
        Spacer(Modifier.height(16.dp))
        StatsBar(streak = state.streak, totalXp = state.totalXp, hearts = state.hearts)
        Spacer(Modifier.height(16.dp))
        // Entry points to the reinforcement surfaces (P1.7) and settings/about (P1.8).
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            OutlinedButton(onClick = onReviewClick, modifier = Modifier.weight(1f)) { Text("Review") }
            OutlinedButton(onClick = onSettingsClick, modifier = Modifier.weight(1f)) { Text("Settings") }
        }
        Spacer(Modifier.height(24.dp))

        LazyColumn(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            items(state.nodes, key = { it.nodeId }) { node ->
                NodeCard(node = node, onClick = { onNodeClick(node.nodeId) })
            }
        }
    }
}

/** Streak / XP / hearts summary. The streak flame gently pulses (§12.1 whimsy). */
@Composable
private fun StatsBar(streak: Int, totalXp: Int, hearts: Int) {
    val transition = rememberInfiniteTransition(label = "streakFlame")
    val flameAlpha by transition.animateFloat(
        initialValue = 0.6f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(900), RepeatMode.Reverse),
        label = "flameAlpha",
    )
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceEvenly,
    ) {
        Text(
            text = "🔥 $streak",
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier
                .alpha(flameAlpha)
                .semantics { contentDescription = "Streak: $streak days" },
        )
        Text(
            text = "⭐ $totalXp XP",
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.semantics { contentDescription = "Total XP: $totalXp" },
        )
        Text(
            text = "❤️ $hearts",
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.semantics { contentDescription = "Hearts: $hearts" },
        )
    }
}

@Composable
private fun NodeCard(node: NodeUiModel, onClick: () -> Unit) {
    // Positional unlock (§4.4): locked nodes are not clickable; completed nodes show a crown level.
    val base = Modifier.fillMaxWidth()
    val cardModifier = if (node.unlocked) base.clickable(onClick = onClick) else base
    val marker = when {
        node.completed -> "✅"
        node.unlocked -> "▶️"
        else -> "🔒" // 🔒
    }
    val statusLabel = when {
        node.completed -> "Lv ${node.level}"
        !node.unlocked -> "Locked"
        else -> null
    }
    Card(modifier = cardModifier) {
        Row(modifier = Modifier.padding(20.dp)) {
            Text(text = "$marker ", style = MaterialTheme.typography.titleMedium)
            Text(
                text = node.title,
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.weight(1f),
            )
            if (statusLabel != null) {
                Text(text = statusLabel, style = MaterialTheme.typography.labelMedium)
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun HomeContentPreview() {
    AprendeTheme {
        HomeContent(
            state = HomeUiState(
                nodes = listOf(NodeUiModel(1, "Basics 1"), NodeUiModel(2, "Basics 2")),
                streak = 4,
                totalXp = 120,
                hearts = 5,
                loading = false,
            ),
        )
    }
}

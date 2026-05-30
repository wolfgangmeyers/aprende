package com.magicalhippie.aprende.domain.session

import com.magicalhippie.aprende.domain.model.Node
import com.magicalhippie.aprende.domain.model.NodeProgress

/** A Path node with its derived unlock/completion state for the home screen (SPEC §4.4, §7). */
data class PathNodeState(
    val node: Node,
    val unlocked: Boolean,
    val completed: Boolean,
    val level: Int,
)

/**
 * Pure positional-unlock rule (SPEC §4.4): nodes are ordered by `displayOrder`; the first node
 * is always unlocked, and node N+1 unlocks once node N is **completed** (crown level ≥ 1). A
 * completed node is always shown unlocked. Stateless and deterministic → unit-testable.
 */
object PathUnlock {
    fun compute(nodes: List<Node>, progressByNode: Map<Long, NodeProgress>): List<PathNodeState> {
        var prevCompleted = true // the first node is always unlocked
        return nodes.sortedBy { it.displayOrder }.map { node ->
            val level = progressByNode[node.nodeId]?.level ?: 0
            val completed = level >= 1
            val unlocked = prevCompleted || completed
            prevCompleted = completed
            PathNodeState(node = node, unlocked = unlocked, completed = completed, level = level)
        }
    }
}

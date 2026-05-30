package com.magicalhippie.aprende.domain.session

import com.magicalhippie.aprende.domain.model.Node
import com.magicalhippie.aprende.domain.model.NodeProgress
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Positional-unlock rule (SPEC §4.4): node N+1 opens once node N is completed. */
class PathUnlockTest {

    private val nodes = listOf(
        Node(nodeId = 1, title = "Basics 1", displayOrder = 0),
        Node(nodeId = 2, title = "Basics 2", displayOrder = 1),
        Node(nodeId = 3, title = "Basics 3", displayOrder = 2),
    )

    private fun completed(nodeId: Long) = NodeProgress(nodeId, level = 1, legendary = false, completedAtMillis = 1L)

    private fun stateOf(result: List<PathNodeState>, nodeId: Long) = result.first { it.node.nodeId == nodeId }

    @Test
    fun `with no progress only the first node is unlocked`() {
        val r = PathUnlock.compute(nodes, emptyMap())
        assertTrue("first node always unlocked", stateOf(r, 1).unlocked)
        assertFalse(stateOf(r, 2).unlocked)
        assertFalse(stateOf(r, 3).unlocked)
        assertTrue(r.none { it.completed })
    }

    @Test
    fun `completing a node unlocks the next and marks it completed`() {
        val r = PathUnlock.compute(nodes, mapOf(1L to completed(1)))
        assertTrue(stateOf(r, 1).completed)
        assertEquals(1, stateOf(r, 1).level)
        assertTrue("second unlocks once first is complete", stateOf(r, 2).unlocked)
        assertFalse("second not yet completed", stateOf(r, 2).completed)
        assertFalse("third still locked", stateOf(r, 3).unlocked)
    }

    @Test
    fun `completing two nodes unlocks the third`() {
        val r = PathUnlock.compute(nodes, mapOf(1L to completed(1), 2L to completed(2)))
        assertTrue(stateOf(r, 3).unlocked)
        assertFalse(stateOf(r, 3).completed)
    }

    @Test
    fun `nodes are ordered by displayOrder regardless of input order`() {
        val shuffled = listOf(nodes[2], nodes[0], nodes[1])
        val r = PathUnlock.compute(shuffled, emptyMap())
        assertEquals(listOf(1L, 2L, 3L), r.map { it.node.nodeId })
    }

    @Test
    fun `a completed node is always shown unlocked even if a predecessor is not complete`() {
        val r = PathUnlock.compute(nodes, mapOf(2L to completed(2)))
        assertTrue(stateOf(r, 2).unlocked)
        assertTrue(stateOf(r, 2).completed)
    }
}

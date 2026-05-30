package com.magicalhippie.aprende.domain.review

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pure JVM tests for [MatchSession] (P1.7 vocab practice, SPEC §8). No Android. Covers: matching
 * a correct lemma↔gloss pair clears it, a wrong pair resets the selection without clearing, and
 * the session completes only when every pair is matched.
 */
class MatchSessionTest {

    private val pairs = listOf(
        MatchPair(1, "perro", "dog"),
        MatchPair(2, "agua", "water"),
    )

    private fun tileOf(session: MatchSession, pairId: Long, side: MatchSide): MatchTile =
        session.tiles.first { it.pairId == pairId && it.side == side }

    @Test
    fun `correct pair matches and clears`() {
        val s = MatchSession(pairs)
        assertEquals(MatchTap.SELECTED, s.tap(tileOf(s, 1, MatchSide.LEMMA)))
        assertEquals(MatchTap.MATCHED, s.tap(tileOf(s, 1, MatchSide.GLOSS)))
        assertTrue(s.isCleared(1))
        assertEquals(1, s.clearedCount)
        assertNull("selection resets after a match", s.selectedTile())
        assertFalse(s.isComplete)
    }

    @Test
    fun `wrong pair resets selection and does not clear`() {
        val s = MatchSession(pairs)
        s.tap(tileOf(s, 1, MatchSide.LEMMA))
        val tap = s.tap(tileOf(s, 2, MatchSide.GLOSS)) // different pair
        assertEquals(MatchTap.MISMATCH, tap)
        assertFalse(s.isCleared(1))
        assertFalse(s.isCleared(2))
        assertNull("wrong pair resets the selection", s.selectedTile())
        assertEquals(0, s.clearedCount)
    }

    @Test
    fun `same-side tiles do not match`() {
        val s = MatchSession(pairs)
        s.tap(tileOf(s, 1, MatchSide.LEMMA))
        // Tapping another LEMMA (even of a different pair) is a mismatch, not a match.
        val tap = s.tap(tileOf(s, 2, MatchSide.LEMMA))
        assertEquals(MatchTap.MISMATCH, tap)
        assertEquals(0, s.clearedCount)
    }

    @Test
    fun `re-tapping the selected tile deselects`() {
        val s = MatchSession(pairs)
        val t = tileOf(s, 1, MatchSide.LEMMA)
        s.tap(t)
        assertEquals(MatchTap.IGNORED, s.tap(t))
        assertNull(s.selectedTile())
    }

    @Test
    fun `tapping a cleared tile is ignored`() {
        val s = MatchSession(pairs)
        s.tap(tileOf(s, 1, MatchSide.LEMMA))
        s.tap(tileOf(s, 1, MatchSide.GLOSS)) // clears pair 1
        assertEquals(MatchTap.IGNORED, s.tap(tileOf(s, 1, MatchSide.LEMMA)))
    }

    @Test
    fun `session completes when all pairs matched`() {
        val s = MatchSession(pairs)
        s.tap(tileOf(s, 1, MatchSide.LEMMA))
        s.tap(tileOf(s, 1, MatchSide.GLOSS))
        s.tap(tileOf(s, 2, MatchSide.GLOSS))
        s.tap(tileOf(s, 2, MatchSide.LEMMA)) // order within a pair doesn't matter
        assertTrue(s.isComplete)
        assertEquals(2, s.clearedCount)
    }

    @Test
    fun `tiles cover both sides of every pair`() {
        val s = MatchSession(pairs)
        assertEquals(4, s.tiles.size)
        assertEquals(setOf(1L, 2L), s.tiles.map { it.pairId }.toSet())
        assertEquals(2, s.tiles.count { it.side == MatchSide.LEMMA })
        assertEquals(2, s.tiles.count { it.side == MatchSide.GLOSS })
    }
}

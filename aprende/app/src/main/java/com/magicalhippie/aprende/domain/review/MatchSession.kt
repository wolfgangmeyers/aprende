package com.magicalhippie.aprende.domain.review

/**
 * A single lemma↔gloss pair to match in vocabulary practice (SPEC §8, Match-Madness-style).
 * [itemId] is the lexeme id (so a cleared pair can credit SRS later if desired); [lemma] is the
 * Spanish headword and [gloss] is its English meaning.
 */
data class MatchPair(val itemId: Long, val lemma: String, val gloss: String)

/** Which side of the board a tile sits on. */
enum class MatchSide { LEMMA, GLOSS }

/** A single tappable tile: a [pairId] (the pair it belongs to) on a [side], showing [text]. */
data class MatchTile(val pairId: Long, val side: MatchSide, val text: String)

/** The result of a single tap on a tile (pure state transition output). */
enum class MatchTap {
    /** First tile of a candidate pair selected (nothing to compare yet). */
    SELECTED,
    /** Two tiles selected and they belong to the same pair — both cleared. */
    MATCHED,
    /** Two tiles selected but different pairs — selection reset (SPEC §8 "wrong pair resets"). */
    MISMATCH,
    /** Tap ignored (already-cleared tile, or re-tapping the same selected tile). */
    IGNORED,
}

/**
 * Pure, JVM-testable untimed matching session over a handful of learned lexemes (SPEC §8
 * Vocabulary practice). NO Android / Compose / Room — the ViewModel wraps it and renders its
 * snapshot. Rules:
 *  - Tap one tile to select it; tap its correct match → both clear; tap a wrong tile → the
 *    selection resets (the wrong pair does NOT clear).
 *  - Tapping the currently-selected tile, or any already-cleared tile, is a no-op.
 *  - [isComplete] when every pair has been matched.
 *
 * Tiles are laid out with lemmas on one side and glosses on the other; the optional
 * [shuffle] seam lets the caller deterministically order tiles in tests.
 */
class MatchSession(
    pairs: List<MatchPair>,
    shuffle: (List<MatchTile>) -> List<MatchTile> = { it },
) {
    init {
        require(pairs.isNotEmpty()) { "MatchSession needs at least one pair" }
        require(pairs.map { it.itemId }.toSet().size == pairs.size) { "pair itemIds must be unique" }
    }

    /** All tiles (both sides), in presentation order. Stable for the lifetime of the session. */
    val tiles: List<MatchTile> = shuffle(
        pairs.flatMap {
            listOf(
                MatchTile(it.itemId, MatchSide.LEMMA, it.lemma),
                MatchTile(it.itemId, MatchSide.GLOSS, it.gloss),
            )
        },
    )

    private val totalPairs = pairs.size
    private val cleared = HashSet<Long>()
    private var selected: MatchTile? = null

    /** The currently-selected tile (null when nothing is selected). */
    fun selectedTile(): MatchTile? = selected

    /** True once [pairId]'s pair has been matched and removed from play. */
    fun isCleared(pairId: Long): Boolean = pairId in cleared

    val clearedCount: Int get() = cleared.size
    val isComplete: Boolean get() = cleared.size == totalPairs

    /**
     * Tap the tile [tile]. Returns the resulting [MatchTap]. A match requires the two tiles to
     * share a [pairId] but be on opposite [MatchSide]s (you match a lemma to its gloss, not a
     * lemma to itself).
     */
    fun tap(tile: MatchTile): MatchTap {
        if (tile.pairId in cleared) return MatchTap.IGNORED
        val current = selected
        if (current == null) {
            selected = tile
            return MatchTap.SELECTED
        }
        if (current == tile) {
            // Re-tapping the same tile: deselect it (forgiving — no penalty).
            selected = null
            return MatchTap.IGNORED
        }
        return if (current.pairId == tile.pairId && current.side != tile.side) {
            cleared.add(tile.pairId)
            selected = null
            MatchTap.MATCHED
        } else {
            // Wrong pair (or same side) → reset selection (SPEC §8).
            selected = null
            MatchTap.MISMATCH
        }
    }
}

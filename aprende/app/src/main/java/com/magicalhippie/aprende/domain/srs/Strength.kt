package com.magicalhippie.aprende.domain.srs

import com.magicalhippie.aprende.domain.model.SrsItem
import java.time.Clock
import javax.inject.Inject

/** An SRS item paired with its current recall strength R∈[0,1]. */
data class ItemStrength(val item: SrsItem, val strength: Double)

/**
 * Computes an item's current recall strength = FSRS retrievability `R(elapsed, S)` evaluated
 * now (SPEC §6.6). This is **lazy decay** (SPEC §6.5): strength is derived from the stored
 * `lastReviewMillis`/`stability` against the injected [Clock] at read time — never written by
 * a background job. Drives the Words-list strength meter and weakest-first ordering.
 */
class StrengthCalculator @Inject constructor(
    private val fsrs: Fsrs,
    private val clock: Clock,
) {
    fun strengthOf(item: SrsItem, nowMillis: Long = clock.millis()): Double {
        val elapsedDays = Fsrs.floorDayDelta(item.state.lastReviewMillis, nowMillis)
        return fsrs.retrievability(elapsedDays, item.state.stability)
    }

    fun withStrength(item: SrsItem, nowMillis: Long = clock.millis()): ItemStrength =
        ItemStrength(item, strengthOf(item, nowMillis))
}

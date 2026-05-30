package com.magicalhippie.aprende.domain.review

import com.magicalhippie.aprende.domain.model.SrsItem
import com.magicalhippie.aprende.domain.repository.ProgressRepository
import com.magicalhippie.aprende.domain.srs.ItemStrength
import com.magicalhippie.aprende.domain.srs.StrengthCalculator
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.time.Clock
import javax.inject.Inject

/**
 * Items currently due for review (SPEC §6.5/§8): `now >= dueAt`, soonest-due first. Pure
 * lazy computation over stored timestamps via the injected [Clock] — no background job.
 */
class GetDueItemsUseCase @Inject constructor(
    private val progress: ProgressRepository,
    private val clock: Clock,
) {
    suspend operator fun invoke(): List<SrsItem> = progress.dueItems(clock.millis())
}

/**
 * All seen items ordered **weakest-first** by current recall strength R (SPEC §8 / §6.6).
 * This is the distinct "by strength" query the Words list and the strength-based review use —
 * note "weak" (`R` low) is NOT the same as "due" (`now >= dueAt`), so this is separate from
 * [GetDueItemsUseCase].
 */
class SeenItemsByStrengthUseCase @Inject constructor(
    private val progress: ProgressRepository,
    private val strength: StrengthCalculator,
    private val clock: Clock,
) {
    operator fun invoke(): Flow<List<ItemStrength>> =
        progress.seenItemsFlow().map { items ->
            val now = clock.millis()
            items.map { strength.withStrength(it, now) }.sortedBy { it.strength }
        }
}

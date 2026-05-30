package com.magicalhippie.aprende.domain.srs

import com.magicalhippie.aprende.domain.FakeProgressRepository
import com.magicalhippie.aprende.domain.model.ItemType
import com.magicalhippie.aprende.domain.model.SrsItem
import com.magicalhippie.aprende.domain.model.SrsState
import com.magicalhippie.aprende.domain.review.GetDueItemsUseCase
import com.magicalhippie.aprende.domain.review.SeenItemsByStrengthUseCase
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset

/** P1.3: strength (lazy decay, §6.6) and the due / weakest-first review queries (§8). */
class StrengthAndReviewTest {

    private val now = Instant.parse("2026-01-01T12:00:00Z")
    private val nowMs = now.toEpochMilli()
    private val clock = Clock.fixed(now, ZoneOffset.UTC)
    private val day = 86_400_000L

    private fun srs(id: Long, stability: Double, lastReviewDaysAgo: Long, dueInDays: Long): SrsItem =
        SrsItem(
            itemId = id,
            itemType = ItemType.LEXEME,
            state = SrsItemState(
                difficulty = 5.0,
                stability = stability,
                lastReviewMillis = nowMs - lastReviewDaysAgo * day,
                dueAtMillis = nowMs + dueInDays * day,
            ),
            lifecycle = SrsState.REVIEW,
            timesSeen = 1, timesCorrect = 1, timesWrong = 0,
        )

    @Test
    fun `strength equals FSRS retrievability at the elapsed time`() {
        val calc = StrengthCalculator(Fsrs(), clock)
        val item = srs(id = 1, stability = 2.3065, lastReviewDaysAgo = 2, dueInDays = 0)
        // retrievability(2, 2.3065) — the verified reference value.
        assertEquals(0.9094932559773545, calc.strengthOf(item), 1e-6)
    }

    @Test
    fun `seen items are ordered weakest-first by current strength`() = runTest {
        val repo = FakeProgressRepository()
        repo.upsertSrsItem(srs(id = 1, stability = 50.0, lastReviewDaysAgo = 1, dueInDays = 40)) // strong
        repo.upsertSrsItem(srs(id = 2, stability = 1.0, lastReviewDaysAgo = 5, dueInDays = 0))   // weak
        val useCase = SeenItemsByStrengthUseCase(repo, StrengthCalculator(Fsrs(), clock), clock)

        val ordered = useCase().first()
        assertEquals("weakest item first", 2L, ordered.first().item.itemId)
        assertEquals(1L, ordered.last().item.itemId)
        assertTrue(ordered.first().strength < ordered.last().strength)
    }

    @Test
    fun `due items query returns only items due at or before now`() = runTest {
        val repo = FakeProgressRepository()
        repo.upsertSrsItem(srs(id = 1, stability = 5.0, lastReviewDaysAgo = 3, dueInDays = -1)) // due (past)
        repo.upsertSrsItem(srs(id = 2, stability = 5.0, lastReviewDaysAgo = 0, dueInDays = 5))  // not due
        val due = GetDueItemsUseCase(repo, clock)()
        assertEquals(1, due.size)
        assertEquals(1L, due.first().itemId)
    }
}

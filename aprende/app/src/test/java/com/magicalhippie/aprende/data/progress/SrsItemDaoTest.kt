package com.magicalhippie.aprende.data.progress

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * In-memory Room tests for [SrsItemDao] (P1.1). Runs on the JVM via Robolectric (no device).
 * Covers the composite-PK upsert round-trip and the lazy-decay `dueItems` query (SPEC §6.5).
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class SrsItemDaoTest {

    private lateinit var db: ProgressDatabase
    private lateinit var dao: SrsItemDao

    @Before
    fun setUp() {
        db = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            ProgressDatabase::class.java,
        ).allowMainThreadQueries().build()
        dao = db.srsItemDao()
    }

    @After
    fun tearDown() = db.close()

    private fun item(
        itemId: Long,
        itemType: String = "LEXEME",
        dueAt: Long,
        difficulty: Double = 5.0,
    ) = SrsItemEntity(
        itemId = itemId,
        itemType = itemType,
        difficulty = difficulty,
        stability = 2.0,
        lastReviewMillis = 0L,
        dueAtMillis = dueAt,
        state = "REVIEW",
        timesSeen = 1,
        timesCorrect = 1,
        timesWrong = 0,
    )

    @Test
    fun `upsert then getByItem round-trips`() = runTest {
        val row = item(itemId = 42, dueAt = 1_000L)
        dao.upsert(row)

        assertEquals(row, dao.getByItem(42, "LEXEME"))
        // A different itemType is a different PK and must not collide.
        assertNull(dao.getByItem(42, "GRAMMAR_RULE"))
    }

    @Test
    fun `dueItems returns only due rows ordered by dueAt`() = runTest {
        dao.upsert(item(itemId = 1, dueAt = 300L))
        dao.upsert(item(itemId = 2, dueAt = 100L))
        dao.upsert(item(itemId = 3, dueAt = 200L))
        dao.upsert(item(itemId = 4, dueAt = 999L)) // not due at now=250

        val due = dao.dueItems(nowMillis = 250L)

        assertEquals(listOf(2L, 3L), due.map { it.itemId }) // ascending dueAt, only <= now
    }

    @Test
    fun `composite-PK upsert replaces the right row`() = runTest {
        // Same itemId, two itemTypes — distinct rows.
        dao.upsert(item(itemId = 7, itemType = "LEXEME", dueAt = 100L, difficulty = 3.0))
        dao.upsert(item(itemId = 7, itemType = "GRAMMAR_RULE", dueAt = 100L, difficulty = 4.0))

        // Replace only the LEXEME row.
        dao.upsert(item(itemId = 7, itemType = "LEXEME", dueAt = 500L, difficulty = 9.0))

        val lexeme = dao.getByItem(7, "LEXEME")
        val grammar = dao.getByItem(7, "GRAMMAR_RULE")
        assertEquals(9.0, lexeme!!.difficulty, 0.0)
        assertEquals(500L, lexeme.dueAtMillis)
        // The grammar row is untouched.
        assertEquals(4.0, grammar!!.difficulty, 0.0)
        assertEquals(100L, grammar.dueAtMillis)
    }
}

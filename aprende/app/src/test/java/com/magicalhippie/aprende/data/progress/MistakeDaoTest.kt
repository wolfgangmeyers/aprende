package com.magicalhippie.aprende.data.progress

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * In-memory Room tests for [MistakeDao] (P1.1, SPEC §8). The mistakes queue is FIFO: drain
 * returns oldest-first and respects the limit; delete removes a cleared mistake.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class MistakeDaoTest {

    private lateinit var db: ProgressDatabase
    private lateinit var dao: MistakeDao

    @Before
    fun setUp() {
        db = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            ProgressDatabase::class.java,
        ).allowMainThreadQueries().build()
        dao = db.mistakeDao()
    }

    @After
    fun tearDown() = db.close()

    private fun mistake(exerciseId: Long, itemId: Long, missedAt: Long) =
        MistakeQueueEntity(
            exerciseId = exerciseId,
            itemId = itemId,
            itemType = "LEXEME",
            missedAt = missedAt,
        )

    @Test
    fun `drain returns FIFO and respects limit`() = runTest {
        dao.insert(mistake(exerciseId = 10, itemId = 1, missedAt = 100L))
        dao.insert(mistake(exerciseId = 11, itemId = 2, missedAt = 200L))
        dao.insert(mistake(exerciseId = 12, itemId = 3, missedAt = 300L))

        val drained = dao.drain(limit = 2)

        assertEquals(2, drained.size)
        assertEquals(listOf(10L, 11L), drained.map { it.exerciseId }) // insertion order
    }

    @Test
    fun `delete removes a cleared mistake`() = runTest {
        val id1 = dao.insert(mistake(exerciseId = 10, itemId = 1, missedAt = 100L))
        dao.insert(mistake(exerciseId = 11, itemId = 2, missedAt = 200L))

        // Clear the first by deleting the entity (id assigned by autoGenerate).
        val first = dao.drain(limit = 10).first { it.id == id1 }
        dao.delete(first)

        val remaining = dao.drain(limit = 10)
        assertEquals(listOf(11L), remaining.map { it.exerciseId })
    }

    @Test
    fun `deleteByIds clears multiple drained mistakes`() = runTest {
        dao.insert(mistake(exerciseId = 10, itemId = 1, missedAt = 100L))
        dao.insert(mistake(exerciseId = 11, itemId = 2, missedAt = 200L))
        dao.insert(mistake(exerciseId = 12, itemId = 3, missedAt = 300L))

        val drained = dao.drain(limit = 2)
        dao.deleteByIds(drained.map { it.id })

        val remaining = dao.drain(limit = 10)
        assertEquals(listOf(12L), remaining.map { it.exerciseId })
    }
}

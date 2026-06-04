package com.magicalhippie.aprende.data.progress

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.magicalhippie.aprende.data.backup.BackupCodec
import com.magicalhippie.aprende.domain.model.DailyActivity
import com.magicalhippie.aprende.domain.model.ItemType
import com.magicalhippie.aprende.domain.model.SrsItem
import com.magicalhippie.aprende.domain.model.SrsState
import com.magicalhippie.aprende.domain.model.UserStats
import com.magicalhippie.aprende.domain.srs.SrsItemState
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * **AC11** — Export progress to a file (JSON), "wipe app data" (a fresh empty DB), import the
 * file → streak/XP/SRS state restored (SPEC §11). Runs on the JVM via Robolectric against two
 * in-memory `progress.db` instances: the "old phone" DB is seeded, exported, encoded; a fresh
 * "new phone" DB then decodes + imports and must mirror the original state (streak / XP / SRS
 * rows / mistakes / daily activity).
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class BackupRestoreAc11Test {

    private lateinit var oldDb: ProgressDatabase
    private lateinit var newDb: ProgressDatabase

    private fun newInMemoryDb(): ProgressDatabase =
        Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            ProgressDatabase::class.java,
        ).allowMainThreadQueries().build()

    private fun repoFor(db: ProgressDatabase) = ProgressRepositoryImpl(
        db = db,
        srsItemDao = db.srsItemDao(),
        mistakeDao = db.mistakeDao(),
        dailyActivityDao = db.dailyActivityDao(),
        userStatsDao = db.userStatsDao(),
        achievementDao = db.achievementDao(),
        nodeProgressDao = db.nodeProgressDao(),
    )

    @After
    fun tearDown() {
        if (::oldDb.isInitialized) oldDb.close()
        if (::newDb.isInitialized) newDb.close()
    }

    @Test
    fun `export wipe import restores streak XP and SRS state`() = runTest {
        oldDb = newInMemoryDb()
        val oldRepo = repoFor(oldDb)

        // Seed the "old phone": SRS rows + user_stats (streak/XP) + a mistake + daily activity.
        val srs = SrsItem(
            itemId = 42,
            itemType = ItemType.LEXEME,
            state = SrsItemState(difficulty = 6.1, stability = 20.0, lastReviewMillis = 1_000L, dueAtMillis = 5_000L),
            lifecycle = SrsState.REVIEW,
            timesSeen = 5,
            timesCorrect = 4,
            timesWrong = 1,
        )
        oldRepo.upsertSrsItem(srs)
        val stats = UserStats(
            totalXp = 470,
            gems = 30,
            hearts = 5,
            heartsLostAtMillis = null,
            streakLength = 12,
            streakFreezes = 1,
            wordsLearned = 33,
            lastActiveLocalDate = "2026-05-30",
        )
        oldRepo.upsertUserStats(stats)
        oldRepo.enqueueMistake(exerciseId = 7, itemId = 42, itemType = ItemType.LEXEME, missedAtMillis = 1_111L)
        oldRepo.upsertDailyActivity(DailyActivity(localDate = "2026-05-30", xpEarned = 30, goalMet = true))

        // Export → encode (the JSON document the user writes via SAF).
        val json = BackupCodec.encode(oldRepo.exportSnapshot())

        // "Wipe app data" == a brand-new, empty progress.db.
        newDb = newInMemoryDb()
        val newRepo = repoFor(newDb)
        assertEquals("fresh DB starts empty", 0, newDb.srsItemDao().getAll().size)
        assertNull("fresh DB has no stats", newRepo.getUserStats())

        // Import the decoded snapshot into the fresh DB.
        newRepo.importSnapshot(BackupCodec.decode(json))

        // Streak / XP restored.
        val restoredStats = newRepo.getUserStats()!!
        assertEquals(12, restoredStats.streakLength)
        assertEquals(470, restoredStats.totalXp)
        assertEquals(33, restoredStats.wordsLearned)
        assertEquals(1, restoredStats.streakFreezes)
        assertEquals("2026-05-30", restoredStats.lastActiveLocalDate)

        // SRS row restored (FSRS state preserved).
        val restoredSrs = newRepo.getSrsItem(42, ItemType.LEXEME)!!
        assertEquals(srs, restoredSrs)

        // Mistake + daily activity restored.
        assertEquals(1, newDb.mistakeDao().getAll().size)
        assertEquals(7L, newDb.mistakeDao().getAll().first().exerciseId)
        assertEquals(true, newRepo.getDailyActivity("2026-05-30")?.goalMet)
    }
}

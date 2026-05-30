package com.magicalhippie.aprende.data.backup

import com.magicalhippie.aprende.domain.model.Achievement
import com.magicalhippie.aprende.domain.model.DailyActivity
import com.magicalhippie.aprende.domain.model.ItemType
import com.magicalhippie.aprende.domain.model.Mistake
import com.magicalhippie.aprende.domain.model.NodeProgress
import com.magicalhippie.aprende.domain.model.ProgressSnapshot
import com.magicalhippie.aprende.domain.model.SrsItem
import com.magicalhippie.aprende.domain.model.SrsState
import com.magicalhippie.aprende.domain.model.UserStats
import com.magicalhippie.aprende.domain.srs.SrsItemState
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Pure JVM round-trip tests for [BackupCodec] (P1.8, SPEC §11 / AC11). A populated
 * [ProgressSnapshot] must `encode → decode` back to an equal object — proving the versioned
 * JSON format preserves every progress table without an Android/Room dependency.
 */
class BackupCodecTest {

    private fun sampleSnapshot() = ProgressSnapshot(
        schemaVersion = ProgressSnapshot.CURRENT_SCHEMA_VERSION,
        srsItems = listOf(
            SrsItem(
                itemId = 10,
                itemType = ItemType.LEXEME,
                state = SrsItemState(difficulty = 5.3, stability = 12.7, lastReviewMillis = 1_000L, dueAtMillis = 2_000L),
                lifecycle = SrsState.REVIEW,
                timesSeen = 4,
                timesCorrect = 3,
                timesWrong = 1,
            ),
            SrsItem(
                itemId = 11,
                itemType = ItemType.GRAMMAR_RULE,
                state = SrsItemState(difficulty = 7.0, stability = 1.5, lastReviewMillis = 500L, dueAtMillis = 9_000L),
                lifecycle = SrsState.RELEARNING,
                timesSeen = 2,
                timesCorrect = 0,
                timesWrong = 2,
            ),
        ),
        nodeProgress = listOf(NodeProgress(nodeId = 1, level = 3, legendary = true, completedAtMillis = 42L)),
        mistakes = listOf(Mistake(id = 7, exerciseId = 99, itemId = 10, itemType = ItemType.LEXEME, missedAtMillis = 1_234L)),
        dailyActivity = listOf(DailyActivity(localDate = "2026-05-30", xpEarned = 30, goalMet = true)),
        userStats = UserStats(
            totalXp = 360,
            gems = 50,
            hearts = 4,
            heartsLostAtMillis = 7_777L,
            streakLength = 9,
            streakFreezes = 1,
            wordsLearned = 25,
            lastActiveLocalDate = "2026-05-30",
        ),
        achievements = listOf(Achievement(achievementId = "streak", level = 2, unlockedAtMillis = 8_888L)),
    )

    @Test
    fun `snapshot round-trips encode then decode`() {
        val original = sampleSnapshot()
        val decoded = BackupCodec.decode(BackupCodec.encode(original))
        assertEquals(original, decoded)
    }

    @Test
    fun `empty snapshot round-trips`() {
        val original = ProgressSnapshot(
            schemaVersion = ProgressSnapshot.CURRENT_SCHEMA_VERSION,
            srsItems = emptyList(),
            nodeProgress = emptyList(),
            mistakes = emptyList(),
            dailyActivity = emptyList(),
            userStats = null,
            achievements = emptyList(),
        )
        val decoded = BackupCodec.decode(BackupCodec.encode(original))
        assertEquals(original, decoded)
    }

    @Test
    fun `encoded JSON carries the schema version`() {
        val json = BackupCodec.encode(sampleSnapshot())
        // The versioned envelope is what lets the codec migrate older exports (SPEC §11).
        assertEquals(true, json.contains("\"schemaVersion\""))
    }
}

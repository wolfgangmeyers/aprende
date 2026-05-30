package com.magicalhippie.aprende.data.progress

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

/**
 * Room entities for the read-write `progress.db` (SPEC §10.2, D2).
 *
 * This is the learner's accumulated state — SRS rows, node progress, mistakes, daily
 * activity, totals, achievements. Unlike `content.db`, it is **never overwritten**: schema
 * bumps carry explicit `Migration` classes (see [Migrations]) so learner data survives every
 * app update. `progress.db` MUST NEVER use `fallbackToDestructiveMigration()` — that is the
 * exact D2 failure mode the two-DB split exists to prevent.
 *
 * Cross-DB references are by **id only** (no foreign keys into `content.db`); the repository
 * layer joins content↔progress in code (SPEC §12.1). That is why `itemId` / `nodeId` /
 * `exerciseId` are plain `Long` columns with no `@ForeignKey`.
 *
 * SQLite/Room type-affinity mapping (matches the conventions in `content/ContentEntities.kt`):
 *   - `INTEGER` ↔ Kotlin `Long`  (ids, epoch-millis timestamps)
 *   - `INTEGER` ↔ Kotlin `Int`   (small counts)
 *   - `INTEGER` ↔ Kotlin `Boolean` (0/1)
 *   - `REAL`    ↔ Kotlin `Double` (FSRS D/S)
 *   - `TEXT`    ↔ Kotlin `String` / `String?`
 *   - nullable SQLite columns ↔ Kotlin nullable types
 */

// ---------------------------------------------------------------------------------------
// srs_item — per-item FSRS memory state with a GENERIC item identity (SPEC §10.2).
//
// Composite PK (itemId, itemType) so the engine can schedule both lexemes and grammar
// rules (e.g. ser-vs-estar). `itemId` references content by id (no cross-DB FK).
// `dueAtMillis` is indexed for the hot "due today" query (SPEC §6.5 lazy decay:
// "is due now" = clock.now() >= dueAtMillis).
// ---------------------------------------------------------------------------------------
@Entity(
    tableName = "srs_item",
    primaryKeys = ["itemId", "itemType"],
    indices = [Index("dueAtMillis")],
)
data class SrsItemEntity(
    /** Content id this SRS row tracks (lexemeId or grammarRuleId). */
    val itemId: Long,
    /** Item kind — one of {"LEXEME","GRAMMAR_RULE"} (SPEC §10.2). */
    val itemType: String,
    // FSRS-6 state (mirrors domain SrsItemState; epoch-millis timestamps).
    val difficulty: Double,
    val stability: Double,
    val lastReviewMillis: Long,
    val dueAtMillis: Long,
    /** SRS lifecycle state — one of {"NEW","LEARNING","REVIEW","RELEARNING"}. */
    val state: String,
    val timesSeen: Int,
    val timesCorrect: Int,
    val timesWrong: Int,
)

// ---------------------------------------------------------------------------------------
// node_progress — crown-equivalent level per Path node (SPEC §10.2).
// ---------------------------------------------------------------------------------------
@Entity(tableName = "node_progress")
data class NodeProgressEntity(
    @PrimaryKey val nodeId: Long,
    val level: Int,
    val legendary: Boolean,
    val completedAt: Long?,
)

// ---------------------------------------------------------------------------------------
// mistake_queue — persistent FIFO of missed exercises (SPEC §8, §10.2).
//
// Auto-generated surrogate PK so the same (exerciseId,itemId) can be enqueued more than
// once and drained in insertion order.
// ---------------------------------------------------------------------------------------
@Entity(tableName = "mistake_queue")
data class MistakeQueueEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val exerciseId: Long,
    val itemId: Long,
    val itemType: String,
    val missedAt: Long,
)

// ---------------------------------------------------------------------------------------
// daily_activity — per-day XP + goal status; drives streak + daily-goal (SPEC §9, §10.2).
// ---------------------------------------------------------------------------------------
@Entity(tableName = "daily_activity")
data class DailyActivityEntity(
    /** Local date, ISO yyyy-MM-dd (from the injected Clock's zone — SPEC §12.3). */
    @PrimaryKey val localDate: String,
    val xpEarned: Int,
    val goalMet: Boolean,
)

// ---------------------------------------------------------------------------------------
// user_stats — single-row table of running totals (SPEC §9, §10.2).
//
// One logical row; `id` is always 0 so an upsert always replaces the singleton.
// ---------------------------------------------------------------------------------------
@Entity(tableName = "user_stats")
data class UserStatsEntity(
    @PrimaryKey val id: Int = SINGLETON_ID,
    val totalXp: Int,
    val gems: Int,
    val hearts: Int,
    /** When the most recent heart was lost; null when at full hearts (lazy regen, §9). */
    val heartsLostAtMillis: Long?,
    val streakLength: Int,
    val streakFreezes: Int,
    val wordsLearned: Int,
    /** ISO yyyy-MM-dd of the last goal-met day; null until the first (streak continuity, §9). */
    val lastActiveLocalDate: String? = null,
) {
    companion object {
        /** The only valid PK for the singleton stats row. */
        const val SINGLETON_ID: Int = 0
    }
}

// ---------------------------------------------------------------------------------------
// achievement — 10-level tier unlock state (SPEC §9, §10.2).
// ---------------------------------------------------------------------------------------
@Entity(tableName = "achievement")
data class AchievementEntity(
    @PrimaryKey val achievementId: String,
    val level: Int,
    val unlockedAtMillis: Long?,
)

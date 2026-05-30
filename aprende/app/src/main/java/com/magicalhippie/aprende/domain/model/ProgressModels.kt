package com.magicalhippie.aprende.domain.model

import com.magicalhippie.aprende.domain.srs.SrsItemState

/**
 * Plain domain models exposed by the repository layer (SPEC §12.1). The domain layer stays
 * free of Room types: repositories map Room entities ↔ these data classes. They reuse the
 * SRS engine's [SrsItemState] (P0.2) for the FSRS D/S/timestamps rather than redefining it.
 */

/** The kind of content an SRS row tracks (SPEC §10.2). Stored as its [name] in `srs_item.itemType`. */
enum class ItemType { LEXEME, GRAMMAR_RULE }

/** SRS lifecycle state (SPEC §10.2). Stored as its [name] in `srs_item.state`. */
enum class SrsState { NEW, LEARNING, REVIEW, RELEARNING }

/**
 * A persisted SRS row in domain terms: a generic item identity + its FSRS memory [state] +
 * lifetime counters. `itemId` references content by id (the repository performs the cross-DB
 * join; there is no FK — SPEC §12.1, D2).
 */
data class SrsItem(
    val itemId: Long,
    val itemType: ItemType,
    val state: SrsItemState,
    val lifecycle: SrsState,
    val timesSeen: Int,
    val timesCorrect: Int,
    val timesWrong: Int,
)

/** A persisted mistake awaiting review (SPEC §8). [id] is the queue surrogate key. */
data class Mistake(
    val id: Long,
    val exerciseId: Long,
    val itemId: Long,
    val itemType: ItemType,
    val missedAtMillis: Long,
)

/** Per-day activity driving streak + daily goal (SPEC §9). */
data class DailyActivity(
    val localDate: String,
    val xpEarned: Int,
    val goalMet: Boolean,
)

/** Crown-equivalent level reached on a Path node (SPEC §10.2 `node_progress`). */
data class NodeProgress(
    val nodeId: Long,
    val level: Int,
    val legendary: Boolean,
    val completedAtMillis: Long?,
)

/** An unlocked achievement tier (SPEC §9/§10.2 `achievement`). */
data class Achievement(
    val achievementId: String,
    val level: Int,
    val unlockedAtMillis: Long?,
)

/** Running learner totals (SPEC §9). */
data class UserStats(
    val totalXp: Int,
    val gems: Int,
    val hearts: Int,
    val heartsLostAtMillis: Long?,
    val streakLength: Int,
    val streakFreezes: Int,
    val wordsLearned: Int,
    /** ISO yyyy-MM-dd of the last day the daily goal was met (drives streak continuity, §9). */
    val lastActiveLocalDate: String? = null,
)

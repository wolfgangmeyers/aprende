package com.magicalhippie.aprende.domain.repository

import com.magicalhippie.aprende.domain.model.DailyActivity
import com.magicalhippie.aprende.domain.model.ItemType
import com.magicalhippie.aprende.domain.model.Mistake
import com.magicalhippie.aprende.domain.model.NodeProgress
import com.magicalhippie.aprende.domain.model.ProgressSnapshot
import com.magicalhippie.aprende.domain.model.SrsItem
import com.magicalhippie.aprende.domain.model.UserStats
import kotlinx.coroutines.flow.Flow

/**
 * Read-write access to the learner's accumulated state in `progress.db` (SPEC §10.2, §12.1).
 *
 * Declared in the domain layer; the Room-backed implementation lives in the data layer and is
 * bound via Hilt (`data/RepositoryModule.kt`). Domain use-cases depend on this interface, not
 * on DAOs (so tests inject fakes — SPEC §12.1). Returns plain domain models, never Room
 * entities.
 */
interface ProgressRepository {
    // --- SRS ---
    suspend fun upsertSrsItem(item: SrsItem)
    suspend fun getSrsItem(itemId: Long, itemType: ItemType): SrsItem?
    /** Items due at or before [nowMillis], soonest-due first (lazy decay — SPEC §6.5). */
    suspend fun dueItems(nowMillis: Long): List<SrsItem>
    /** All seen SRS rows, observable — drives the Words strength list (SPEC §6.6, §8). */
    fun seenItemsFlow(): Flow<List<SrsItem>>

    // --- Mistakes queue (SPEC §8) ---
    suspend fun enqueueMistake(exerciseId: Long, itemId: Long, itemType: ItemType, missedAtMillis: Long)
    /** Drain the oldest [limit] mistakes (FIFO); caller credits then clears them. */
    suspend fun drainMistakes(limit: Int): List<Mistake>
    /** Remove a cleared mistake from the queue (SPEC §8). */
    suspend fun clearMistakes(ids: List<Long>)

    // --- Daily activity (SPEC §9) ---
    suspend fun upsertDailyActivity(activity: DailyActivity)
    suspend fun getDailyActivity(localDate: String): DailyActivity?
    fun dailyActivityFlow(): Flow<List<DailyActivity>>

    // --- User stats (SPEC §9) ---
    fun userStatsFlow(): Flow<UserStats?>
    suspend fun getUserStats(): UserStats?
    suspend fun upsertUserStats(stats: UserStats)

    // --- Node progress (SPEC §7 step 6, §10.2 — drives positional unlock §4.4) ---
    suspend fun getNodeProgress(nodeId: Long): NodeProgress?
    suspend fun upsertNodeProgress(progress: NodeProgress)
    /** All node-completion rows, observable — the home/Path screen unlocks from this. */
    fun nodeProgressFlow(): Flow<List<NodeProgress>>

    // --- Achievements (SPEC §9) ---
    /** The currently unlocked level for an achievement, or 0 if never unlocked. */
    suspend fun getAchievementLevel(achievementId: String): Int
    suspend fun unlockAchievement(achievementId: String, level: Int, atMillis: Long)

    // --- Backup / restore (SPEC §11, C3 / AC11) ---
    /**
     * Read the entire learner state into a portable [ProgressSnapshot] (SPEC §11). Used by the
     * SAF export path; reads every progress table.
     */
    suspend fun exportSnapshot(): ProgressSnapshot

    /**
     * Replace the entire learner state with [snapshot] (SPEC §11, AC11 — "move to a new
     * phone"). Implementations clear every progress table then bulk-insert the snapshot's rows,
     * so a fresh/empty DB ends up exactly mirroring the exported state.
     */
    suspend fun importSnapshot(snapshot: ProgressSnapshot)
}

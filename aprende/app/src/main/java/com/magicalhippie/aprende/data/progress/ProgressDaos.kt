package com.magicalhippie.aprende.data.progress

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

/**
 * Read-write DAOs over `progress.db` (SPEC §10.2). Offline-first: one-shot reads/writes are
 * `suspend` (run off the main thread on `Dispatchers.IO`), observable reads return `Flow` so
 * the UI auto-updates on DB change (SPEC §12.1).
 */

@Dao
interface SrsItemDao {
    /** Insert-or-replace by composite PK (itemId, itemType). */
    @Upsert
    suspend fun upsert(item: SrsItemEntity)

    @Query("SELECT * FROM srs_item WHERE itemId = :itemId AND itemType = :itemType")
    suspend fun getByItem(itemId: Long, itemType: String): SrsItemEntity?

    /**
     * Items due at or before [nowMillis], soonest-due first. Lazy-decay due query (SPEC §6.5):
     * "is due now" = clock.now() >= dueAtMillis. Backed by the `dueAtMillis` index.
     */
    @Query("SELECT * FROM srs_item WHERE dueAtMillis <= :nowMillis ORDER BY dueAtMillis ASC")
    suspend fun dueItems(nowMillis: Long): List<SrsItemEntity>

    /** All seen SRS rows — drives the Words screen strength list (SPEC §6.6, §8). */
    @Query("SELECT * FROM srs_item ORDER BY dueAtMillis ASC")
    fun allSeen(): Flow<List<SrsItemEntity>>

    // --- backup / restore (SPEC §11) ---
    @Query("SELECT * FROM srs_item")
    suspend fun getAll(): List<SrsItemEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(items: List<SrsItemEntity>)

    @Query("DELETE FROM srs_item")
    suspend fun clear()
}

@Dao
interface MistakeDao {
    @Insert
    suspend fun insert(mistake: MistakeQueueEntity): Long

    /**
     * Drain the oldest [limit] mistakes (FIFO by insertion order). Returns rows; the caller
     * deletes them after crediting (SPEC §8 — clearing a mistake removes it from the queue).
     */
    @Query("SELECT * FROM mistake_queue ORDER BY id ASC LIMIT :limit")
    suspend fun drain(limit: Int): List<MistakeQueueEntity>

    @Delete
    suspend fun delete(mistake: MistakeQueueEntity)

    @Query("DELETE FROM mistake_queue WHERE id IN (:ids)")
    suspend fun deleteByIds(ids: List<Long>)

    // --- backup / restore (SPEC §11) ---
    @Query("SELECT * FROM mistake_queue ORDER BY id ASC")
    suspend fun getAll(): List<MistakeQueueEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(mistakes: List<MistakeQueueEntity>)

    @Query("DELETE FROM mistake_queue")
    suspend fun clear()
}

@Dao
interface DailyActivityDao {
    @Upsert
    suspend fun upsert(activity: DailyActivityEntity)

    @Query("SELECT * FROM daily_activity WHERE localDate = :localDate")
    suspend fun getByDate(localDate: String): DailyActivityEntity?

    /** Recent activity, newest-first — feeds streak computation (SPEC §9). */
    @Query("SELECT * FROM daily_activity ORDER BY localDate DESC")
    fun observeAll(): Flow<List<DailyActivityEntity>>

    // --- backup / restore (SPEC §11) ---
    @Query("SELECT * FROM daily_activity")
    suspend fun getAll(): List<DailyActivityEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(activity: List<DailyActivityEntity>)

    @Query("DELETE FROM daily_activity")
    suspend fun clear()
}

@Dao
interface UserStatsDao {
    /** Observe the singleton stats row (null until first write). */
    @Query("SELECT * FROM user_stats WHERE id = ${UserStatsEntity.SINGLETON_ID}")
    fun observe(): Flow<UserStatsEntity?>

    @Query("SELECT * FROM user_stats WHERE id = ${UserStatsEntity.SINGLETON_ID}")
    suspend fun get(): UserStatsEntity?

    @Upsert
    suspend fun upsert(stats: UserStatsEntity)

    // --- backup / restore (SPEC §11) ---
    @Query("DELETE FROM user_stats")
    suspend fun clear()
}

@Dao
interface NodeProgressDao {
    @Upsert
    suspend fun upsert(progress: NodeProgressEntity)

    @Query("SELECT * FROM node_progress WHERE nodeId = :nodeId")
    suspend fun getByNode(nodeId: Long): NodeProgressEntity?

    @Query("SELECT * FROM node_progress")
    fun observeAll(): Flow<List<NodeProgressEntity>>

    // --- backup / restore (SPEC §11) ---
    @Query("SELECT * FROM node_progress")
    suspend fun getAll(): List<NodeProgressEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(rows: List<NodeProgressEntity>)

    @Query("DELETE FROM node_progress")
    suspend fun clear()
}

@Dao
interface AchievementDao {
    @Upsert
    suspend fun upsert(achievement: AchievementEntity)

    @Query("SELECT * FROM achievement WHERE achievementId = :achievementId")
    suspend fun getById(achievementId: String): AchievementEntity?

    @Query("SELECT * FROM achievement")
    fun observeAll(): Flow<List<AchievementEntity>>

    // --- backup / restore (SPEC §11) ---
    @Query("SELECT * FROM achievement")
    suspend fun getAll(): List<AchievementEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(rows: List<AchievementEntity>)

    @Query("DELETE FROM achievement")
    suspend fun clear()
}

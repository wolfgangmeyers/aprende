package com.magicalhippie.aprende.data.progress

import com.magicalhippie.aprende.domain.model.Achievement
import com.magicalhippie.aprende.domain.model.DailyActivity
import com.magicalhippie.aprende.domain.model.ItemType
import com.magicalhippie.aprende.domain.model.Mistake
import com.magicalhippie.aprende.domain.model.NodeProgress
import com.magicalhippie.aprende.domain.model.ProgressSnapshot
import com.magicalhippie.aprende.domain.model.SrsItem
import com.magicalhippie.aprende.domain.model.SrsState
import com.magicalhippie.aprende.domain.model.UserStats
import com.magicalhippie.aprende.domain.repository.ProgressRepository
import com.magicalhippie.aprende.domain.srs.SrsItemState
import androidx.room.withTransaction
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject

/**
 * Room-backed [ProgressRepository] over `progress.db` (SPEC §10.2, §12.1).
 *
 * Single source of truth for learner state (no remote source — that is the whole point,
 * SPEC §12.1). Maps the Room entities ↔ plain domain models so the domain layer stays free
 * of Room types. enum ↔ String conversions are the only schema-coupling here.
 */
class ProgressRepositoryImpl @Inject constructor(
    private val db: ProgressDatabase,
    private val srsItemDao: SrsItemDao,
    private val mistakeDao: MistakeDao,
    private val dailyActivityDao: DailyActivityDao,
    private val userStatsDao: UserStatsDao,
    private val achievementDao: AchievementDao,
    private val nodeProgressDao: NodeProgressDao,
) : ProgressRepository {

    // --- Node progress ---
    override suspend fun getNodeProgress(nodeId: Long): NodeProgress? =
        nodeProgressDao.getByNode(nodeId)?.toDomain()

    override suspend fun upsertNodeProgress(progress: NodeProgress) =
        nodeProgressDao.upsert(progress.toEntity())

    override fun nodeProgressFlow(): Flow<List<NodeProgress>> =
        nodeProgressDao.observeAll().map { rows -> rows.map { it.toDomain() } }

    // --- Achievements ---
    override suspend fun getAchievementLevel(achievementId: String): Int =
        achievementDao.getById(achievementId)?.level ?: 0

    override suspend fun unlockAchievement(achievementId: String, level: Int, atMillis: Long) =
        achievementDao.upsert(AchievementEntity(achievementId = achievementId, level = level, unlockedAtMillis = atMillis))

    // --- SRS ---
    override suspend fun upsertSrsItem(item: SrsItem) = srsItemDao.upsert(item.toEntity())

    override suspend fun getSrsItem(itemId: Long, itemType: ItemType): SrsItem? =
        srsItemDao.getByItem(itemId, itemType.name)?.toDomain()

    override suspend fun dueItems(nowMillis: Long): List<SrsItem> =
        srsItemDao.dueItems(nowMillis).map { it.toDomain() }

    override fun seenItemsFlow(): Flow<List<SrsItem>> =
        srsItemDao.allSeen().map { rows -> rows.map { it.toDomain() } }

    // --- Mistakes ---
    override suspend fun enqueueMistake(
        exerciseId: Long,
        itemId: Long,
        itemType: ItemType,
        missedAtMillis: Long,
    ) {
        mistakeDao.insert(
            MistakeQueueEntity(
                exerciseId = exerciseId,
                itemId = itemId,
                itemType = itemType.name,
                missedAt = missedAtMillis,
            ),
        )
    }

    override suspend fun drainMistakes(limit: Int): List<Mistake> =
        mistakeDao.drain(limit).map { it.toDomain() }

    override suspend fun clearMistakes(ids: List<Long>) = mistakeDao.deleteByIds(ids)

    // --- Daily activity ---
    override suspend fun upsertDailyActivity(activity: DailyActivity) =
        dailyActivityDao.upsert(activity.toEntity())

    override suspend fun getDailyActivity(localDate: String): DailyActivity? =
        dailyActivityDao.getByDate(localDate)?.toDomain()

    override fun dailyActivityFlow(): Flow<List<DailyActivity>> =
        dailyActivityDao.observeAll().map { rows -> rows.map { it.toDomain() } }

    // --- User stats ---
    override fun userStatsFlow(): Flow<UserStats?> =
        userStatsDao.observe().map { it?.toDomain() }

    override suspend fun getUserStats(): UserStats? = userStatsDao.get()?.toDomain()

    override suspend fun upsertUserStats(stats: UserStats) = userStatsDao.upsert(stats.toEntity())

    // --- Backup / restore (SPEC §11, C3 / AC11) ---
    override suspend fun exportSnapshot(): ProgressSnapshot = ProgressSnapshot(
        schemaVersion = ProgressSnapshot.CURRENT_SCHEMA_VERSION,
        srsItems = srsItemDao.getAll().map { it.toDomain() },
        nodeProgress = nodeProgressDao.getAll().map { it.toDomain() },
        mistakes = mistakeDao.getAll().map { it.toDomain() },
        dailyActivity = dailyActivityDao.getAll().map { it.toDomain() },
        userStats = userStatsDao.get()?.toDomain(),
        achievements = achievementDao.getAll().map { it.toDomain() },
    )

    /**
     * Clear-then-insert every table so the DB ends up an exact mirror of [snapshot] (SPEC §11,
     * AC11). Wrapped in a single Room transaction so the restore is **all-or-nothing**: import is
     * reachable over *existing* learner state (the Backup screen offers it standalone), so a
     * cancellation (e.g. process death) or a failed `insertAll` mid-sequence must NOT leave
     * `progress.db` partially wiped — the never-overwritten learner DB the two-DB split (D2)
     * exists to protect. On any failure the transaction rolls back and the prior state survives.
     */
    override suspend fun importSnapshot(snapshot: ProgressSnapshot) {
        db.withTransaction {
            // Clear all tables, then bulk-insert the snapshot's rows — atomically.
            srsItemDao.clear()
            nodeProgressDao.clear()
            mistakeDao.clear()
            dailyActivityDao.clear()
            userStatsDao.clear()
            achievementDao.clear()

            srsItemDao.insertAll(snapshot.srsItems.map { it.toEntity() })
            nodeProgressDao.insertAll(snapshot.nodeProgress.map { it.toEntity() })
            mistakeDao.insertAll(snapshot.mistakes.map { it.toEntity() })
            dailyActivityDao.insertAll(snapshot.dailyActivity.map { it.toEntity() })
            snapshot.userStats?.let { userStatsDao.upsert(it.toEntity()) }
            achievementDao.insertAll(snapshot.achievements.map { it.toEntity() })
        }
    }
}

// --- entity <-> domain mapping (Room types confined to this layer) ---

private fun SrsItemEntity.toDomain(): SrsItem = SrsItem(
    itemId = itemId,
    itemType = ItemType.valueOf(itemType),
    state = SrsItemState(
        difficulty = difficulty,
        stability = stability,
        lastReviewMillis = lastReviewMillis,
        dueAtMillis = dueAtMillis,
    ),
    lifecycle = SrsState.valueOf(state),
    timesSeen = timesSeen,
    timesCorrect = timesCorrect,
    timesWrong = timesWrong,
)

private fun SrsItem.toEntity(): SrsItemEntity = SrsItemEntity(
    itemId = itemId,
    itemType = itemType.name,
    difficulty = state.difficulty,
    stability = state.stability,
    lastReviewMillis = state.lastReviewMillis,
    dueAtMillis = state.dueAtMillis,
    state = lifecycle.name,
    timesSeen = timesSeen,
    timesCorrect = timesCorrect,
    timesWrong = timesWrong,
)

private fun MistakeQueueEntity.toDomain(): Mistake = Mistake(
    id = id,
    exerciseId = exerciseId,
    itemId = itemId,
    itemType = ItemType.valueOf(itemType),
    missedAtMillis = missedAt,
)

/** Preserves the queue surrogate id so FIFO order survives an export→import round-trip (SPEC §8/§11). */
private fun Mistake.toEntity(): MistakeQueueEntity = MistakeQueueEntity(
    id = id,
    exerciseId = exerciseId,
    itemId = itemId,
    itemType = itemType.name,
    missedAt = missedAtMillis,
)

private fun NodeProgressEntity.toDomain(): NodeProgress = NodeProgress(
    nodeId = nodeId,
    level = level,
    legendary = legendary,
    completedAtMillis = completedAt,
)

private fun NodeProgress.toEntity(): NodeProgressEntity = NodeProgressEntity(
    nodeId = nodeId,
    level = level,
    legendary = legendary,
    completedAt = completedAtMillis,
)

private fun AchievementEntity.toDomain(): Achievement = Achievement(
    achievementId = achievementId,
    level = level,
    unlockedAtMillis = unlockedAtMillis,
)

private fun Achievement.toEntity(): AchievementEntity = AchievementEntity(
    achievementId = achievementId,
    level = level,
    unlockedAtMillis = unlockedAtMillis,
)

private fun DailyActivityEntity.toDomain(): DailyActivity = DailyActivity(
    localDate = localDate,
    xpEarned = xpEarned,
    goalMet = goalMet,
)

private fun DailyActivity.toEntity(): DailyActivityEntity = DailyActivityEntity(
    localDate = localDate,
    xpEarned = xpEarned,
    goalMet = goalMet,
)

private fun UserStatsEntity.toDomain(): UserStats = UserStats(
    totalXp = totalXp,
    gems = gems,
    hearts = hearts,
    heartsLostAtMillis = heartsLostAtMillis,
    streakLength = streakLength,
    streakFreezes = streakFreezes,
    wordsLearned = wordsLearned,
    lastActiveLocalDate = lastActiveLocalDate,
)

private fun UserStats.toEntity(): UserStatsEntity = UserStatsEntity(
    id = UserStatsEntity.SINGLETON_ID,
    totalXp = totalXp,
    gems = gems,
    hearts = hearts,
    heartsLostAtMillis = heartsLostAtMillis,
    streakLength = streakLength,
    streakFreezes = streakFreezes,
    wordsLearned = wordsLearned,
    lastActiveLocalDate = lastActiveLocalDate,
)

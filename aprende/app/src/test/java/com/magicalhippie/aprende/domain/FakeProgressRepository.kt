package com.magicalhippie.aprende.domain

import com.magicalhippie.aprende.domain.model.Achievement
import com.magicalhippie.aprende.domain.model.DailyActivity
import com.magicalhippie.aprende.domain.model.ItemType
import com.magicalhippie.aprende.domain.model.Mistake
import com.magicalhippie.aprende.domain.model.NodeProgress
import com.magicalhippie.aprende.domain.model.ProgressSnapshot
import com.magicalhippie.aprende.domain.model.SrsItem
import com.magicalhippie.aprende.domain.model.UserStats
import com.magicalhippie.aprende.domain.repository.ProgressRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow

/**
 * In-memory [ProgressRepository] for JVM unit tests. Enforces the same invariants the Room
 * implementation must (composite-key uniqueness, FIFO mistake drain, dueAt filtering) so a
 * test passing here would also pass against Room (test-double fidelity).
 */
class FakeProgressRepository : ProgressRepository {
    private val srs = LinkedHashMap<Pair<Long, ItemType>, SrsItem>()
    private val seen = MutableStateFlow<List<SrsItem>>(emptyList())
    private val mistakes = mutableListOf<Mistake>()
    private var nextMistakeId = 1L
    private val daily = LinkedHashMap<String, DailyActivity>()
    private val dailyFlow = MutableStateFlow<List<DailyActivity>>(emptyList())
    private var stats: UserStats? = null
    private val statsFlow = MutableStateFlow<UserStats?>(null)

    override suspend fun upsertSrsItem(item: SrsItem) {
        srs[item.itemId to item.itemType] = item
        seen.value = srs.values.toList()
    }

    override suspend fun getSrsItem(itemId: Long, itemType: ItemType): SrsItem? = srs[itemId to itemType]

    override suspend fun dueItems(nowMillis: Long): List<SrsItem> =
        srs.values.filter { it.state.dueAtMillis <= nowMillis }.sortedBy { it.state.dueAtMillis }

    override fun seenItemsFlow(): Flow<List<SrsItem>> = seen

    override suspend fun enqueueMistake(exerciseId: Long, itemId: Long, itemType: ItemType, missedAtMillis: Long) {
        mistakes.add(Mistake(nextMistakeId++, exerciseId, itemId, itemType, missedAtMillis))
    }

    override suspend fun drainMistakes(limit: Int): List<Mistake> = mistakes.take(limit)

    override suspend fun clearMistakes(ids: List<Long>) {
        mistakes.removeAll { it.id in ids }
    }

    override suspend fun upsertDailyActivity(activity: DailyActivity) {
        daily[activity.localDate] = activity
        dailyFlow.value = daily.values.toList()
    }

    override suspend fun getDailyActivity(localDate: String): DailyActivity? = daily[localDate]

    override fun dailyActivityFlow(): Flow<List<DailyActivity>> = dailyFlow

    override fun userStatsFlow(): Flow<UserStats?> = statsFlow

    override suspend fun getUserStats(): UserStats? = stats

    override suspend fun upsertUserStats(stats: UserStats) {
        this.stats = stats
        statsFlow.value = stats
    }

    private val achievements = LinkedHashMap<String, Achievement>()
    private val nodeProgress = LinkedHashMap<Long, NodeProgress>()
    private val nodeProgressFlow = MutableStateFlow<List<NodeProgress>>(emptyList())

    override suspend fun getNodeProgress(nodeId: Long): NodeProgress? = nodeProgress[nodeId]

    override suspend fun upsertNodeProgress(progress: NodeProgress) {
        nodeProgress[progress.nodeId] = progress
        nodeProgressFlow.value = nodeProgress.values.toList()
    }

    override fun nodeProgressFlow(): Flow<List<NodeProgress>> = nodeProgressFlow

    override suspend fun getAchievementLevel(achievementId: String): Int = achievements[achievementId]?.level ?: 0

    override suspend fun unlockAchievement(achievementId: String, level: Int, atMillis: Long) {
        achievements[achievementId] = Achievement(achievementId, level, atMillis)
    }

    // --- Backup / restore (SPEC §11, AC11) ---
    override suspend fun exportSnapshot(): ProgressSnapshot = ProgressSnapshot(
        schemaVersion = ProgressSnapshot.CURRENT_SCHEMA_VERSION,
        srsItems = srs.values.toList(),
        nodeProgress = nodeProgress.values.toList(),
        mistakes = mistakes.toList(),
        dailyActivity = daily.values.toList(),
        userStats = stats,
        achievements = achievements.values.toList(),
    )

    override suspend fun importSnapshot(snapshot: ProgressSnapshot) {
        // Clear-then-insert, mirroring ProgressRepositoryImpl.
        srs.clear(); mistakes.clear(); daily.clear(); achievements.clear(); nodeProgress.clear()
        snapshot.srsItems.forEach { srs[it.itemId to it.itemType] = it }
        snapshot.nodeProgress.forEach { nodeProgress[it.nodeId] = it }
        mistakes.addAll(snapshot.mistakes)
        nextMistakeId = (snapshot.mistakes.maxOfOrNull { it.id } ?: 0L) + 1
        snapshot.dailyActivity.forEach { daily[it.localDate] = it }
        snapshot.achievements.forEach { achievements[it.achievementId] = it }
        stats = snapshot.userStats
        seen.value = srs.values.toList()
        dailyFlow.value = daily.values.toList()
        statsFlow.value = stats
        nodeProgressFlow.value = nodeProgress.values.toList()
    }

    // test helpers
    fun allMistakes(): List<Mistake> = mistakes.toList()
    fun srsCount(): Int = srs.size
}

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
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * Versioned, JVM-testable JSON codec for a [ProgressSnapshot] (SPEC §11, C3 / AC11).
 *
 * **Why DTOs here (not annotations on domain models):** the wire format is a data-layer
 * concern, so the `@Serializable` shapes live in this package and the codec maps domain ↔ DTO.
 * This keeps the domain layer free of kotlinx.serialization (mirrors how Room types are
 * confined to the data layer — SPEC §12.1). The DTO field set is the stable persisted contract.
 * Today [decode] reads only the current schema version (additive fields are tolerated via
 * `ignoreUnknownKeys`, giving forward-compatibility). Before removing/renaming a field, bump
 * [ProgressSnapshot.CURRENT_SCHEMA_VERSION] and add the corresponding version branch in [decode]
 * — there is no such branch yet because v1 is the only version.
 *
 * Pure: [encode]/[decode] only touch [Json] + the DTOs — no Android, no Room — so they round-
 * trip under a plain JVM unit test (BackupCodecTest).
 */
object BackupCodec {

    private val json = Json {
        prettyPrint = true
        // Tolerate fields a newer export may add, so an older app can still import (forward-compat).
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    fun encode(snapshot: ProgressSnapshot): String = json.encodeToString(snapshot.toDto())

    fun decode(text: String): ProgressSnapshot = json.decodeFromString<SnapshotDto>(text).toDomain()
}

// --- Serializable DTOs (the stable JSON contract) ---

@Serializable
internal data class SnapshotDto(
    val schemaVersion: Int,
    val srsItems: List<SrsItemDto> = emptyList(),
    val nodeProgress: List<NodeProgressDto> = emptyList(),
    val mistakes: List<MistakeDto> = emptyList(),
    val dailyActivity: List<DailyActivityDto> = emptyList(),
    val userStats: UserStatsDto? = null,
    val achievements: List<AchievementDto> = emptyList(),
)

@Serializable
internal data class SrsItemDto(
    val itemId: Long,
    val itemType: String,
    val difficulty: Double,
    val stability: Double,
    val lastReviewMillis: Long,
    val dueAtMillis: Long,
    val lifecycle: String,
    val timesSeen: Int,
    val timesCorrect: Int,
    val timesWrong: Int,
)

@Serializable
internal data class NodeProgressDto(
    val nodeId: Long,
    val level: Int,
    val legendary: Boolean,
    val completedAtMillis: Long? = null,
)

@Serializable
internal data class MistakeDto(
    val id: Long,
    val exerciseId: Long,
    val itemId: Long,
    val itemType: String,
    val missedAtMillis: Long,
)

@Serializable
internal data class DailyActivityDto(
    val localDate: String,
    val xpEarned: Int,
    val goalMet: Boolean,
)

@Serializable
internal data class UserStatsDto(
    val totalXp: Int,
    val gems: Int,
    val hearts: Int,
    val heartsLostAtMillis: Long? = null,
    val streakLength: Int,
    val streakFreezes: Int,
    val wordsLearned: Int,
    val lastActiveLocalDate: String? = null,
)

@Serializable
internal data class AchievementDto(
    val achievementId: String,
    val level: Int,
    val unlockedAtMillis: Long? = null,
)

// --- domain <-> DTO mapping (serialization confined to this layer) ---

private fun ProgressSnapshot.toDto(): SnapshotDto = SnapshotDto(
    schemaVersion = schemaVersion,
    srsItems = srsItems.map { it.toDto() },
    nodeProgress = nodeProgress.map { it.toDto() },
    mistakes = mistakes.map { it.toDto() },
    dailyActivity = dailyActivity.map { it.toDto() },
    userStats = userStats?.toDto(),
    achievements = achievements.map { it.toDto() },
)

private fun SnapshotDto.toDomain(): ProgressSnapshot = ProgressSnapshot(
    schemaVersion = schemaVersion,
    srsItems = srsItems.map { it.toDomain() },
    nodeProgress = nodeProgress.map { it.toDomain() },
    mistakes = mistakes.map { it.toDomain() },
    dailyActivity = dailyActivity.map { it.toDomain() },
    userStats = userStats?.toDomain(),
    achievements = achievements.map { it.toDomain() },
)

private fun SrsItem.toDto(): SrsItemDto = SrsItemDto(
    itemId = itemId,
    itemType = itemType.name,
    difficulty = state.difficulty,
    stability = state.stability,
    lastReviewMillis = state.lastReviewMillis,
    dueAtMillis = state.dueAtMillis,
    lifecycle = lifecycle.name,
    timesSeen = timesSeen,
    timesCorrect = timesCorrect,
    timesWrong = timesWrong,
)

private fun SrsItemDto.toDomain(): SrsItem = SrsItem(
    itemId = itemId,
    itemType = ItemType.valueOf(itemType),
    state = SrsItemState(
        difficulty = difficulty,
        stability = stability,
        lastReviewMillis = lastReviewMillis,
        dueAtMillis = dueAtMillis,
    ),
    lifecycle = SrsState.valueOf(lifecycle),
    timesSeen = timesSeen,
    timesCorrect = timesCorrect,
    timesWrong = timesWrong,
)

private fun NodeProgress.toDto(): NodeProgressDto =
    NodeProgressDto(nodeId, level, legendary, completedAtMillis)

private fun NodeProgressDto.toDomain(): NodeProgress =
    NodeProgress(nodeId, level, legendary, completedAtMillis)

private fun Mistake.toDto(): MistakeDto =
    MistakeDto(id, exerciseId, itemId, itemType.name, missedAtMillis)

private fun MistakeDto.toDomain(): Mistake =
    Mistake(id, exerciseId, itemId, ItemType.valueOf(itemType), missedAtMillis)

private fun DailyActivity.toDto(): DailyActivityDto =
    DailyActivityDto(localDate, xpEarned, goalMet)

private fun DailyActivityDto.toDomain(): DailyActivity =
    DailyActivity(localDate, xpEarned, goalMet)

private fun UserStats.toDto(): UserStatsDto = UserStatsDto(
    totalXp = totalXp,
    gems = gems,
    hearts = hearts,
    heartsLostAtMillis = heartsLostAtMillis,
    streakLength = streakLength,
    streakFreezes = streakFreezes,
    wordsLearned = wordsLearned,
    lastActiveLocalDate = lastActiveLocalDate,
)

private fun UserStatsDto.toDomain(): UserStats = UserStats(
    totalXp = totalXp,
    gems = gems,
    hearts = hearts,
    heartsLostAtMillis = heartsLostAtMillis,
    streakLength = streakLength,
    streakFreezes = streakFreezes,
    wordsLearned = wordsLearned,
    lastActiveLocalDate = lastActiveLocalDate,
)

private fun Achievement.toDto(): AchievementDto =
    AchievementDto(achievementId, level, unlockedAtMillis)

private fun AchievementDto.toDomain(): Achievement =
    Achievement(achievementId, level, unlockedAtMillis)

package com.magicalhippie.aprende.domain.model

/**
 * A complete, point-in-time copy of the learner's `progress.db` state (SPEC §11, C3 / AC11).
 *
 * This is the **portability unit**: the user-driven export/import path serializes one of these
 * to a versioned JSON document via SAF and reconstructs it on a new device. It is a plain
 * domain aggregate of the existing progress domain models (no Room, no kotlinx.serialization
 * annotations) so the domain layer stays persistence- and codec-agnostic (SPEC §12.1); the
 * versioned wire format + `@Serializable` DTOs live in `data/backup/`.
 *
 * [schemaVersion] is the snapshot document's own version (independent of the Room
 * `progress.db` schema version). It exists so the codec CAN add version handling if the JSON
 * format ever changes incompatibly; v1 is the only version today, so no such migration exists yet.
 */
data class ProgressSnapshot(
    val schemaVersion: Int,
    val srsItems: List<SrsItem>,
    val nodeProgress: List<NodeProgress>,
    val mistakes: List<Mistake>,
    val dailyActivity: List<DailyActivity>,
    val userStats: UserStats?,
    val achievements: List<Achievement>,
) {
    companion object {
        /** Current snapshot document schema version (bump on a breaking JSON change). */
        const val CURRENT_SCHEMA_VERSION: Int = 1
    }
}

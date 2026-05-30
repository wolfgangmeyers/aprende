package com.magicalhippie.aprende.data.progress

import androidx.room.Database
import androidx.room.RoomDatabase

/**
 * The read-write learner-state database `progress.db` (SPEC §10.2, D2).
 *
 * Carries **explicit `Migration` classes** (see [PROGRESS_MIGRATIONS]) — it is NEVER
 * destructively migrated, because that would wipe the learner's SRS state / streak / XP
 * (the exact D2 failure mode the two-DB split prevents). Contrast `content.db`, which is
 * read-only and intentionally rebuilt from its bundled asset on a version bump.
 *
 * `exportSchema = true` writes the schema JSON to `app/schemas/` (configured via
 * `room.schemaLocation` in build.gradle.kts) so future migrations can be authored and
 * validated against a checked-in schema.
 */
@Database(
    entities = [
        SrsItemEntity::class,
        NodeProgressEntity::class,
        MistakeQueueEntity::class,
        DailyActivityEntity::class,
        UserStatsEntity::class,
        AchievementEntity::class,
    ],
    version = 1,
    exportSchema = true,
)
abstract class ProgressDatabase : RoomDatabase() {
    abstract fun srsItemDao(): SrsItemDao
    abstract fun mistakeDao(): MistakeDao
    abstract fun dailyActivityDao(): DailyActivityDao
    abstract fun userStatsDao(): UserStatsDao
    abstract fun nodeProgressDao(): NodeProgressDao
    abstract fun achievementDao(): AchievementDao

    companion object {
        const val DATABASE_NAME: String = "progress.db"
    }
}

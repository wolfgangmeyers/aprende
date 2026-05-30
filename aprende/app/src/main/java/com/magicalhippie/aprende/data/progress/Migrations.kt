package com.magicalhippie.aprende.data.progress

import androidx.room.migration.Migration

/**
 * Explicit Room migrations for `progress.db` (SPEC §10.2, D2).
 *
 * `progress.db` is the never-overwritten learner-state DB: it MUST carry an explicit
 * migration for every schema bump so existing SRS state / streak / XP survive. It must
 * NEVER call `fallbackToDestructiveMigration()` (that wipes learner data — the D2 failure
 * mode the two-DB split exists to prevent).
 *
 * At version 1 there are no migrations yet. When the schema is bumped to version N+1, add a
 * `Migration(N, N + 1)` here, e.g.:
 *
 *     val MIGRATION_1_2 = object : Migration(1, 2) {
 *         override fun migrate(db: SupportSQLiteDatabase) {
 *             db.execSQL("ALTER TABLE srs_item ADD COLUMN newCol INTEGER NOT NULL DEFAULT 0")
 *         }
 *     }
 *
 * and append it to [PROGRESS_MIGRATIONS]. The Hilt builder spreads this array into
 * `.addMigrations(...)`.
 */
val PROGRESS_MIGRATIONS: Array<Migration> = emptyArray()

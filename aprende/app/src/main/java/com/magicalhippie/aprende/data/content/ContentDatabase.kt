package com.magicalhippie.aprende.data.content

import androidx.room.Database
import androidx.room.RoomDatabase

/**
 * The read-only curriculum database, pre-populated from the bundled `content.db` asset
 * via `createFromAsset` (SPEC §10.1, D2). Never written at runtime — see
 * [ContentDataModule] for the builder and the (intentional) destructive-fallback policy.
 *
 * `version` must match `PRAGMA user_version` of the bundled asset (the pipeline writes
 * `SCHEMA_VERSION = 1`). `exportSchema = true` writes the schema JSON to `app/schemas/`
 * (configured via `room.schemaLocation` in build.gradle.kts) so the content build can be
 * validated against it.
 *
 * The FTS entity [SentenceFts] is listed alongside its content entity [SentenceEntity];
 * Room emits the external-content `CREATE VIRTUAL TABLE ... USING fts4(... content="sentence")`
 * that the asset mirrors.
 */
@Database(
    entities = [
        LexemeEntity::class,
        SentenceEntity::class,
        SentenceFts::class,
        AcceptedAnswerEntity::class,
        SentenceLexemeEntity::class,
        ConjugationLemmaMapEntity::class,
        ExerciseEntity::class,
        NodeEntity::class,
    ],
    version = 1,
    exportSchema = true,
)
abstract class ContentDatabase : RoomDatabase() {
    abstract fun lexemeDao(): LexemeDao
    abstract fun sentenceDao(): SentenceDao
    abstract fun acceptedAnswerDao(): AcceptedAnswerDao
    abstract fun exerciseDao(): ExerciseDao
    abstract fun conjugationDao(): ConjugationDao
    abstract fun nodeDao(): NodeDao
    abstract fun attributionDao(): AttributionDao
}

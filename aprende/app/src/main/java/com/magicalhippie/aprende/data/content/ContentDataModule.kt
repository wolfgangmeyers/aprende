package com.magicalhippie.aprende.data.content

import android.content.Context
import androidx.room.Room
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * Hilt bindings for the read-only content database (SPEC §10.1, D2).
 *
 * `content.db` is **read-only and replaceable**: on a content update, the copied DB is
 * refreshed from the bundled asset before Room opens it. Schema-version bumps still use
 * `createFromAsset` + destructive rebuild, but same-schema content updates are covered by
 * [ContentDatabaseRefresher]. It never holds learner state, so `fallbackToDestructiveMigration()`
 * is the CORRECT policy HERE — and ONLY here. The read-write `progress.db` (P1.1) must NEVER use
 * destructive fallback (it would wipe SRS state / streak / XP — exactly the D2 failure mode the
 * two-DB split exists to prevent).
 */
@Module
@InstallIn(SingletonComponent::class)
object ContentDataModule {

    @Provides
    @Singleton
    fun provideContentDatabase(
        @ApplicationContext context: Context,
    ): ContentDatabase =
        Room.databaseBuilder(
            context,
            ContentDatabase::class.java,
            ContentDatabase.DATABASE_NAME,
        )
            .also { ContentDatabaseRefresher.refreshIfBundledAssetChanged(context) }
            // Pre-populate from the bundled asset shipped under assets/database/.
            .createFromAsset("database/content.db")
            // Read-only/replaceable DB: schema-version changes rebuild from the fresh asset.
            // Same-schema asset changes are handled above by ContentDatabaseRefresher.
            .fallbackToDestructiveMigration()
            .build()

    @Provides
    fun provideLexemeDao(db: ContentDatabase): LexemeDao = db.lexemeDao()

    @Provides
    fun provideSentenceDao(db: ContentDatabase): SentenceDao = db.sentenceDao()

    @Provides
    fun provideAcceptedAnswerDao(db: ContentDatabase): AcceptedAnswerDao = db.acceptedAnswerDao()

    @Provides
    fun provideExerciseDao(db: ContentDatabase): ExerciseDao = db.exerciseDao()

    @Provides
    fun provideConjugationDao(db: ContentDatabase): ConjugationDao = db.conjugationDao()

    @Provides
    fun provideNodeDao(db: ContentDatabase): NodeDao = db.nodeDao()

    @Provides
    fun provideAttributionDao(db: ContentDatabase): AttributionDao = db.attributionDao()
}

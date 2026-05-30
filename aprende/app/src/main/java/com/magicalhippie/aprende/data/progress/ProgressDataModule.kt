package com.magicalhippie.aprende.data.progress

import android.content.Context
import androidx.room.Room
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * Hilt bindings for the read-write progress database (SPEC §10.2, D2).
 *
 * Built with `Room.databaseBuilder(...)` + **explicit `.addMigrations(...)`** and
 * deliberately WITHOUT `fallbackToDestructiveMigration()`: `progress.db` carries the
 * learner's accumulated state and must survive every app/schema update. If a future schema
 * bump ships without a corresponding `Migration` in [PROGRESS_MIGRATIONS], Room will throw
 * at open time — that is the intended fail-loud behavior (better than silently wiping
 * learner data). Contrast `content/ContentDataModule.kt`, where destructive fallback is the
 * correct policy because that DB holds no learner state.
 */
@Module
@InstallIn(SingletonComponent::class)
object ProgressDataModule {

    @Provides
    @Singleton
    fun provideProgressDatabase(
        @ApplicationContext context: Context,
    ): ProgressDatabase =
        Room.databaseBuilder(context, ProgressDatabase::class.java, ProgressDatabase.DATABASE_NAME)
            // Explicit migrations only — NO destructive fallback (D2). Empty at v1.
            .addMigrations(*PROGRESS_MIGRATIONS)
            .build()

    @Provides
    fun provideSrsItemDao(db: ProgressDatabase): SrsItemDao = db.srsItemDao()

    @Provides
    fun provideMistakeDao(db: ProgressDatabase): MistakeDao = db.mistakeDao()

    @Provides
    fun provideDailyActivityDao(db: ProgressDatabase): DailyActivityDao = db.dailyActivityDao()

    @Provides
    fun provideUserStatsDao(db: ProgressDatabase): UserStatsDao = db.userStatsDao()

    @Provides
    fun provideNodeProgressDao(db: ProgressDatabase): NodeProgressDao = db.nodeProgressDao()

    @Provides
    fun provideAchievementDao(db: ProgressDatabase): AchievementDao = db.achievementDao()
}

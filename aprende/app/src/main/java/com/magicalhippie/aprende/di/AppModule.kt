package com.magicalhippie.aprende.di

import com.magicalhippie.aprende.domain.srs.Fsrs
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import java.time.Clock
import javax.inject.Singleton

/**
 * Application-scoped Hilt bindings.
 *
 * Provides the single [Clock] every time-dependent component injects (SPEC §12.3):
 * streak roll-over, SRS due-checks, and lazy decay all read time through this seam,
 * so production uses the real zone while tests bind a [Clock.fixed] for determinism
 * across midnight/DST/timezone boundaries.
 */
@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideClock(): Clock = Clock.systemDefaultZone()

    /** The single FSRS-6 engine with shipped default weights (SPEC D1). */
    @Provides
    @Singleton
    fun provideFsrs(): Fsrs = Fsrs()
}

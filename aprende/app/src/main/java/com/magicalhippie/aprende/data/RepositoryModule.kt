package com.magicalhippie.aprende.data

import com.magicalhippie.aprende.data.content.ContentRepositoryImpl
import com.magicalhippie.aprende.data.progress.ProgressRepositoryImpl
import com.magicalhippie.aprende.data.settings.SettingsRepositoryImpl
import com.magicalhippie.aprende.data.translation.OfflineTranslationRepositoryImpl
import com.magicalhippie.aprende.domain.repository.ContentRepository
import com.magicalhippie.aprende.domain.repository.ProgressRepository
import com.magicalhippie.aprende.domain.repository.SettingsRepository
import com.magicalhippie.aprende.domain.repository.TranslationRepository
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * Binds the data-layer repository implementations to the domain-layer interfaces (SPEC §12.1).
 *
 * Domain use-cases and ViewModels depend on the interfaces; Hilt injects these Room/DataStore
 * impls in production and fakes in tests. The DAOs / Database / DataStore the impls need are
 * provided by `ProgressDataModule`, `ContentDataModule`, and `SettingsDataModule`.
 */
@Module
@InstallIn(SingletonComponent::class)
abstract class RepositoryModule {

    @Binds
    @Singleton
    abstract fun bindProgressRepository(impl: ProgressRepositoryImpl): ProgressRepository

    @Binds
    @Singleton
    abstract fun bindContentRepository(impl: ContentRepositoryImpl): ContentRepository

    @Binds
    @Singleton
    abstract fun bindSettingsRepository(impl: SettingsRepositoryImpl): SettingsRepository

    @Binds
    @Singleton
    abstract fun bindTranslationRepository(impl: OfflineTranslationRepositoryImpl): TranslationRepository
}

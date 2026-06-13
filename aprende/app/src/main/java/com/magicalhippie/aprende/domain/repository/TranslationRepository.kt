package com.magicalhippie.aprende.domain.repository

import com.magicalhippie.aprende.domain.translation.TranslationLookupResult

/** Local Spanish-to-English lookup service. Implementations must not call paid cloud APIs. */
interface TranslationRepository {
    suspend fun lookupSpanishToEnglish(input: String): TranslationLookupResult
}

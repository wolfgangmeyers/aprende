package com.magicalhippie.aprende.domain.translation

/**
 * Spanish-to-English lookup backed by the bundled, vetted curriculum data. This is deliberately
 * a local glossary/example lookup, not an invented or cloud-generated translation.
 */
data class TranslationLookupResult(
    val query: String,
    val matches: List<TranslationMatch>,
) {
    val bestEnglish: String? = matches
        .firstOrNull { it.kind != TranslationMatchKind.EXAMPLE }
        ?.english
    val hasMatches: Boolean = matches.isNotEmpty()
}

data class TranslationMatch(
    val spanish: String,
    val english: String,
    val kind: TranslationMatchKind,
    val note: String? = null,
)

enum class TranslationMatchKind {
    WORD,
    WORD_FORM,
    EXACT_PHRASE,
    EXAMPLE,
}

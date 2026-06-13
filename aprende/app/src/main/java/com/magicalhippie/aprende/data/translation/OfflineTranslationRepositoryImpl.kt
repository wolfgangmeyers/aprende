package com.magicalhippie.aprende.data.translation

import com.magicalhippie.aprende.data.content.ConjugationDao
import com.magicalhippie.aprende.data.content.LexemeDao
import com.magicalhippie.aprende.data.content.LexemeEntity
import com.magicalhippie.aprende.data.content.SentenceDao
import com.magicalhippie.aprende.data.content.SentenceEntity
import com.magicalhippie.aprende.domain.repository.TranslationRepository
import com.magicalhippie.aprende.domain.translation.TranslationLookupResult
import com.magicalhippie.aprende.domain.translation.TranslationMatch
import com.magicalhippie.aprende.domain.translation.TranslationMatchKind
import java.text.Normalizer
import java.util.Locale
import javax.inject.Inject

/**
 * Offline Spanish-to-English lookup over the bundled `content.db`.
 *
 * Full neural machine translation was intentionally not added here: ML Kit is free and on-device
 * at translation time, but its language packs are downloaded dynamically on first use. This
 * implementation is immediately offline and no-cost by reusing vetted lexeme glosses and sentence
 * translations that already ship with the app.
 */
class OfflineTranslationRepositoryImpl @Inject constructor(
    private val lexemeDao: LexemeDao,
    private val conjugationDao: ConjugationDao,
    private val sentenceDao: SentenceDao,
) : TranslationRepository {

    override suspend fun lookupSpanishToEnglish(input: String): TranslationLookupResult {
        val query = normalizeWhitespace(input)
        if (query.isBlank()) return TranslationLookupResult(query = "", matches = emptyList())
        val normalizedQuery = normalizeForComparison(query)
        var sentenceRows: List<SentenceEntity>? = null
        suspend fun allSentences(): List<SentenceEntity> {
            if (sentenceRows == null) sentenceRows = sentenceDao.allForLookup()
            return sentenceRows.orEmpty()
        }

        val matches = mutableListOf<TranslationMatch>()
        val exactLexeme = lexemeByLemma(query, normalizedQuery)
        if (exactLexeme != null) {
            matches.addIfNew(exactLexeme.toWordMatch())
        }

        val surfaceForm = surfaceForm(query, normalizedQuery)
        if (surfaceForm != null && surfaceForm.lemmaLexemeId != exactLexeme?.lexemeId) {
            lexemeDao.getById(surfaceForm.lemmaLexemeId)?.let { lemma ->
                matches.addIfNew(
                    TranslationMatch(
                        spanish = query,
                        english = lemma.englishGloss,
                        kind = TranslationMatchKind.WORD_FORM,
                        note = "Form of ${lemma.lemma}",
                    ),
                )
            }
        }

        val exactSentence = sentenceDao.getBySpanishTextIgnoreCase(query)
            ?: if (normalizedQuery.contains(" ")) {
                allSentences().firstOrNull { normalizeForComparison(it.spanishText) == normalizedQuery }
            } else {
                null
            }
        if (exactSentence != null) {
            matches.addIfNew(exactSentence.toPhraseMatch())
        }

        val examples = sentenceExamples(query, normalizedQuery, ::allSentences)
        val exactFromExamples = examples.firstOrNull {
            normalizeForComparison(it.spanishText) == normalizedQuery
        }
        if (exactSentence == null && exactFromExamples != null) {
            matches.addIfNew(exactFromExamples.toPhraseMatch())
        }
        examples
            .asSequence()
            .filterNot { normalizeForComparison(it.spanishText) == normalizedQuery }
            .take(MAX_EXAMPLES)
            .forEach { matches.addIfNew(it.toExampleMatch()) }

        return TranslationLookupResult(query = query, matches = matches)
    }

    private suspend fun lexemeByLemma(query: String, normalizedQuery: String): LexemeEntity? =
        lexemeDao.getByLemmaIgnoreCase(query)
            ?: lexemeDao.allForLookup().firstOrNull { normalizeForComparison(it.lemma) == normalizedQuery }

    private suspend fun surfaceForm(query: String, normalizedQuery: String) =
        conjugationDao.getBySurfaceFormIgnoreCase(query.lowercase(Locale.ROOT))
            ?: conjugationDao.allForLookup().firstOrNull {
                normalizeForComparison(it.surfaceForm) == normalizedQuery
            }

    private suspend fun sentenceExamples(
        query: String,
        normalizedQuery: String,
        loadAllSentences: suspend () -> List<SentenceEntity>,
    ): List<SentenceEntity> {
        val ftsQuery = buildFtsQuery(query) ?: return emptyList()
        val ftsMatches = sentenceDao.searchSpanish(ftsQuery, SENTENCE_SEARCH_LIMIT)
        val fallbackMatches = if (ftsMatches.size >= SENTENCE_SEARCH_LIMIT) {
            emptyList()
        } else {
            loadAllSentences()
                .asSequence()
                .filter { it.matchesNormalizedTokens(normalizedQuery) }
                .take(SENTENCE_SEARCH_LIMIT)
                .toList()
        }
        return (ftsMatches + fallbackMatches).distinctBy {
            normalizeForComparison(it.spanishText) to it.englishText.lowercase(Locale.ROOT)
        }
    }

    private companion object {
        private const val MAX_EXAMPLES = 3
        private const val SENTENCE_SEARCH_LIMIT = 6
        private val whitespace = Regex("\\s+")
        private val combiningMarks = Regex("\\p{Mn}+")
        private val comparisonPunctuation = Regex("[^\\p{L}\\p{Nd}]+")
        private val tokenRegex = Regex("[\\p{L}\\p{Nd}]+")

        fun normalizeWhitespace(input: String): String =
            input.trim().replace(whitespace, " ")

        fun normalizeForComparison(input: String): String {
            val withoutMarks = Normalizer
                .normalize(input, Normalizer.Form.NFD)
                .replace(combiningMarks, "")
            return withoutMarks
                .lowercase(Locale.ROOT)
                .replace(comparisonPunctuation, " ")
                .trim()
                .replace(whitespace, " ")
        }

        fun buildFtsQuery(input: String): String? {
            val tokens = tokenRegex.findAll(input)
                .map { it.value.lowercase(Locale.ROOT) }
                .filter { it.isNotBlank() }
                .take(8)
                .toList()
            if (tokens.isEmpty()) return null
            return tokens.joinToString(separator = " ") { "$it*" }
        }

        fun SentenceEntity.matchesNormalizedTokens(normalizedQuery: String): Boolean {
            val tokens = normalizedQuery.split(" ").filter { it.isNotBlank() }
            if (tokens.isEmpty()) return false
            val words = normalizeForComparison(spanishText).split(" ").filter { it.isNotBlank() }
            return tokens.all { token -> words.any { word -> word.startsWith(token) } }
        }

        fun LexemeEntity.toWordMatch(): TranslationMatch =
            TranslationMatch(
                spanish = lemma,
                english = englishGloss,
                kind = TranslationMatchKind.WORD,
                note = pos,
            )

        fun SentenceEntity.toPhraseMatch(): TranslationMatch =
            TranslationMatch(
                spanish = spanishText,
                english = englishText,
                kind = TranslationMatchKind.EXACT_PHRASE,
            )

        fun SentenceEntity.toExampleMatch(): TranslationMatch =
            TranslationMatch(
                spanish = spanishText,
                english = englishText,
                kind = TranslationMatchKind.EXAMPLE,
            )

        fun MutableList<TranslationMatch>.addIfNew(match: TranslationMatch) {
            val duplicate = any {
                normalizeForComparison(it.spanish) == normalizeForComparison(match.spanish) &&
                    it.english.equals(match.english, ignoreCase = true)
            }
            if (!duplicate) add(match)
        }
    }
}

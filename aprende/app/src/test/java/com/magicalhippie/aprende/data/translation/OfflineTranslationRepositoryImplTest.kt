package com.magicalhippie.aprende.data.translation

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.magicalhippie.aprende.data.content.ContentDatabase
import com.magicalhippie.aprende.domain.translation.TranslationMatchKind
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class OfflineTranslationRepositoryImplTest {

    private lateinit var db: ContentDatabase
    private lateinit var repo: OfflineTranslationRepositoryImpl

    @Before
    fun setUp() {
        db = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            ContentDatabase::class.java,
        ).allowMainThreadQueries().build()

        insertLexeme(id = 1, lemma = "perro", pos = "noun", gloss = "dog")
        insertLexeme(id = 2, lemma = "tener", pos = "verb", gloss = "to have")
        insertLexeme(id = 3, lemma = "teléfono", pos = "noun", gloss = "phone")
        db.openHelper.writableDatabase.execSQL(
            "INSERT INTO conjugation_lemma_map (surfaceForm, lemmaLexemeId, source, license) " +
                "VALUES ('tengo', 2, 'test', 'CC0')",
        )
        insertSentence(
            id = 10,
            spanish = "Tengo un perro.",
            english = "I have a dog.",
        )
        insertSentence(
            id = 11,
            spanish = "Mi teléfono funciona.",
            english = "My phone works.",
        )

        repo = OfflineTranslationRepositoryImpl(
            lexemeDao = db.lexemeDao(),
            conjugationDao = db.conjugationDao(),
            sentenceDao = db.sentenceDao(),
        )
    }

    @After
    fun tearDown() = db.close()

    @Test
    fun `exact word lookup returns bundled English gloss`() = runTest {
        val result = repo.lookupSpanishToEnglish("perro")

        assertEquals("dog", result.bestEnglish)
        assertTrue(result.matches.any { it.kind == TranslationMatchKind.WORD && it.spanish == "perro" })
    }

    @Test
    fun `conjugated surface form resolves to lemma gloss`() = runTest {
        val result = repo.lookupSpanishToEnglish("Tengo")

        assertEquals("to have", result.bestEnglish)
        assertTrue(result.matches.any { it.kind == TranslationMatchKind.WORD_FORM && it.note == "Form of tener" })
    }

    @Test
    fun `phrase lookup tolerates missing final punctuation`() = runTest {
        val result = repo.lookupSpanishToEnglish("Tengo un perro")

        assertEquals("I have a dog.", result.bestEnglish)
        assertTrue(result.matches.any { it.kind == TranslationMatchKind.EXACT_PHRASE })
    }

    @Test
    fun `accentless word lookup finds accented bundled lemma`() = runTest {
        val result = repo.lookupSpanishToEnglish("telefono")

        assertEquals("phone", result.bestEnglish)
        assertTrue(result.matches.any { it.kind == TranslationMatchKind.WORD && it.spanish == "teléfono" })
    }

    @Test
    fun `accentless phrase lookup finds accented bundled sentence`() = runTest {
        val result = repo.lookupSpanishToEnglish("Mi telefono funciona")

        assertEquals("My phone works.", result.bestEnglish)
        assertTrue(result.matches.any { it.kind == TranslationMatchKind.EXACT_PHRASE })
    }

    @Test
    fun `unknown input returns an empty offline result`() = runTest {
        val result = repo.lookupSpanishToEnglish("zzznotaword")

        assertFalse(result.hasMatches)
    }

    private fun insertLexeme(id: Long, lemma: String, pos: String, gloss: String) {
        db.openHelper.writableDatabase.execSQL(
            "INSERT INTO lexeme (" +
                "lexemeId, lemma, pos, gender, englishGloss, frequencyRank, cefrBand, difficultyPrior, " +
                "source, sourceId, license, vettingStatus, reviewedBy, reviewedAt" +
                ") VALUES (?, ?, ?, NULL, ?, ?, 'A1', 0.1, 'test', ?, 'CC0', 'REVIEWED', 'reviewer', 0)",
            arrayOf<Any?>(id, lemma, pos, gloss, id.toInt(), "lexeme-$id"),
        )
    }

    private fun insertSentence(id: Long, spanish: String, english: String) {
        db.openHelper.writableDatabase.execSQL(
            "INSERT INTO sentence (" +
                "sentenceId, spanishText, englishText, source, sourceId, license, " +
                "vettingStatus, reviewedBy, reviewedAt" +
                ") VALUES (?, ?, ?, 'test', ?, 'CC0', 'REVIEWED', 'reviewer', 0)",
            arrayOf<Any?>(id, spanish, english, "sentence-$id"),
        )
    }
}

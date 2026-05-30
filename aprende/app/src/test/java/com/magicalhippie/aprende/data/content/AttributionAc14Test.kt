package com.magicalhippie.aprende.data.content

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.magicalhippie.aprende.domain.model.Attribution
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * **AC14** — every bundled content row resolves to a source visible in the attribution screen.
 * This covers the data half: seed `lexeme`/`sentence`/`accepted_answer` rows with provenance
 * (the same columns the §4.6 vetting gate populates) into an in-memory `content.db`, then assert
 * [ContentRepositoryImpl.attributions] returns the DISTINCT `(source, license)` credits. The UI
 * half is covered by AttributionScreenTest (Robolectric Compose).
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class AttributionAc14Test {

    private lateinit var db: ContentDatabase
    private lateinit var repo: ContentRepositoryImpl

    @Before
    fun setUp() {
        db = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            ContentDatabase::class.java,
        ).allowMainThreadQueries().build()

        val w = db.openHelper.writableDatabase
        // Two lexemes from Wiktionary, plus a duplicate license to prove DISTINCT dedupes.
        w.execSQL(
            "INSERT INTO lexeme (lexemeId, lemma, pos, gender, englishGloss, frequencyRank, cefrBand, difficultyPrior, source, sourceId, license, vettingStatus, reviewedBy, reviewedAt) " +
                "VALUES (1,'perro','noun',NULL,'dog',1,'A1',5.0,'wiktionary','perro','CC-BY-SA-3.0','REVIEWED','r','100')",
        )
        w.execSQL(
            "INSERT INTO lexeme (lexemeId, lemma, pos, gender, englishGloss, frequencyRank, cefrBand, difficultyPrior, source, sourceId, license, vettingStatus, reviewedBy, reviewedAt) " +
                "VALUES (2,'agua','noun',NULL,'water',2,'A1',5.0,'wiktionary','agua','CC-BY-SA-3.0','REVIEWED','r','100')",
        )
        // A sentence from Tatoeba.
        w.execSQL(
            "INSERT INTO sentence (sentenceId, spanishText, englishText, source, sourceId, license, vettingStatus, reviewedBy, reviewedAt) " +
                "VALUES (10,'Tengo un perro.','I have a dog.','tatoeba','tatoeba:12345','CC-BY-2.0-FR','REVIEWED','r','100')",
        )
        // An authored accepted-answer.
        w.execSQL(
            "INSERT INTO accepted_answer (acceptedAnswerId, sentenceId, direction, answerText, source, sourceId, license, vettingStatus, reviewedBy, reviewedAt) " +
                "VALUES (100,10,'ES_TO_EN','I have a dog','authored','authored:aa1','proprietary','REVIEWED','r','100')",
        )

        repo = ContentRepositoryImpl(
            lexemeDao = db.lexemeDao(),
            exerciseDao = db.exerciseDao(),
            conjugationDao = db.conjugationDao(),
            nodeDao = db.nodeDao(),
            acceptedAnswerDao = db.acceptedAnswerDao(),
            sentenceDao = db.sentenceDao(),
            attributionDao = db.attributionDao(),
        )
    }

    @After
    fun tearDown() = db.close()

    @Test
    fun `attributions returns distinct seeded sources`() = runTest {
        val credits = repo.attributions()
        // DISTINCT collapses the two Wiktionary lexemes into one credit.
        assertEquals(
            listOf(
                Attribution(source = "authored", license = "proprietary"),
                Attribution(source = "tatoeba", license = "CC-BY-2.0-FR"),
                Attribution(source = "wiktionary", license = "CC-BY-SA-3.0"),
            ),
            credits,
        )
    }

    @Test
    fun `every seeded source is represented`() = runTest {
        val sources = repo.attributions().map { it.source }.toSet()
        assertTrue(sources.containsAll(setOf("tatoeba", "wiktionary", "authored")))
    }
}

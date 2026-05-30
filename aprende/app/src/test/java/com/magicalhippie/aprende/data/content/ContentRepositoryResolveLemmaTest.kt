package com.magicalhippie.aprende.data.content

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * Tests the hot grading-path lemma resolution + unknown-surface-form fallback (SPEC §12.1,
 * §12.4). The content DB is read-only at runtime, so we seed `conjugation_lemma_map` with raw
 * SQL into an in-memory ContentDatabase, then exercise [ContentRepositoryImpl.resolveLemma].
 *
 * Key contract: an UNKNOWN form returns `null` (so the caller applies the exact-lemma
 * fallback) and never throws — it must never silently fail to credit the learner.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ContentRepositoryResolveLemmaTest {

    private lateinit var db: ContentDatabase
    private lateinit var repo: ContentRepositoryImpl

    @Before
    fun setUp() {
        db = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            ContentDatabase::class.java,
        ).allowMainThreadQueries().build()

        // Seed the conjugation map directly (the runtime DAO is read-only). Room created the
        // table from ConjugationLemmaMapEntity; column names match the entity properties.
        db.openHelper.writableDatabase.execSQL(
            "INSERT INTO conjugation_lemma_map (surfaceForm, lemmaLexemeId, source, license) " +
                "VALUES ('tuvo', 555, 'test', 'CC0')",
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
    fun `known surface form resolves to its lemma id`() = runTest {
        assertEquals(555L, repo.resolveLemma("tuvo"))
    }

    @Test
    fun `unknown surface form returns null without throwing (fallback path)`() = runTest {
        // No exception, just null -> caller falls back to exact-lemma match (SPEC §12.1).
        assertNull(repo.resolveLemma("zzznotaword"))
    }
}

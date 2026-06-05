package com.magicalhippie.aprende.data.content

import androidx.room.Dao
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

/**
 * Read-only DAOs over `content.db` (SPEC §10.1). Offline-first: queries are `suspend`
 * funs (one-shot reads off the main thread) or `Flow` (observable lists). There are no
 * inserts/updates/deletes — the content DB is never written at runtime (D2); it is
 * replaced wholesale by a new bundled asset on a version bump.
 */

@Dao
interface LexemeDao {
    @Query("SELECT * FROM lexeme WHERE lexemeId = :lexemeId")
    suspend fun getById(lexemeId: Long): LexemeEntity?

    @Query("SELECT * FROM lexeme WHERE lemma = :lemma LIMIT 1")
    suspend fun getByLemma(lemma: String): LexemeEntity?

    /** Words list, frequency-ordered (SPEC §6 Words screen). */
    @Query("SELECT * FROM lexeme ORDER BY frequencyRank ASC")
    fun observeAll(): Flow<List<LexemeEntity>>

    @Query("SELECT COUNT(*) FROM lexeme")
    suspend fun count(): Int
}

@Dao
interface SentenceDao {
    @Query("SELECT * FROM sentence WHERE sentenceId = :sentenceId")
    suspend fun getById(sentenceId: Long): SentenceEntity?

    @Query("SELECT * FROM sentence WHERE sentenceId IN (:sentenceIds)")
    suspend fun getByIds(sentenceIds: List<Long>): List<SentenceEntity>

    /**
     * Full-text search over Spanish/English text via the external-content FTS4 index.
     * `sentence_fts.rowid` equals `sentence.sentenceId` (the pipeline back-fills it that
     * way), so we MATCH in FTS and join back to the content rows by id.
     */
    @Query(
        "SELECT * FROM sentence WHERE sentenceId IN " +
            "(SELECT rowid FROM sentence_fts WHERE sentence_fts MATCH :query)"
    )
    suspend fun search(query: String): List<SentenceEntity>

    @Query("SELECT COUNT(*) FROM sentence")
    suspend fun count(): Int
}

@Dao
interface AcceptedAnswerDao {
    /** All accepted answers for a sentence in a given grading direction (deterministic grading). */
    @Query(
        "SELECT * FROM accepted_answer WHERE sentenceId = :sentenceId AND direction = :direction"
    )
    suspend fun getForSentence(sentenceId: Long, direction: String): List<AcceptedAnswerEntity>

    @Query("SELECT * FROM accepted_answer WHERE sentenceId = :sentenceId")
    suspend fun getAllForSentence(sentenceId: Long): List<AcceptedAnswerEntity>
}

@Dao
interface ExerciseDao {
    @Query("SELECT * FROM exercise WHERE exerciseId = :exerciseId")
    suspend fun getById(exerciseId: Long): ExerciseEntity?

    @Query("SELECT * FROM exercise WHERE exerciseId IN (:exerciseIds)")
    suspend fun getByIds(exerciseIds: List<Long>): List<ExerciseEntity>

    @Query("SELECT * FROM exercise WHERE sentenceId = :sentenceId")
    suspend fun getForSentence(sentenceId: Long): List<ExerciseEntity>

    @Query("SELECT * FROM exercise WHERE nodeId = :nodeId ORDER BY exerciseId ASC")
    suspend fun forNode(nodeId: Long): List<ExerciseEntity>
}

@Dao
interface NodeDao {
    /** All Path nodes in display order — the home/Path list (SPEC §7, §12.2). */
    @Query("SELECT * FROM node ORDER BY displayOrder ASC")
    suspend fun getAll(): List<NodeEntity>
}

/**
 * A distinct `(source, license)` credit row (SPEC §4.5/§4.6, AC14). A plain query POJO Room
 * maps the UNION result onto — column names match exactly. Not a Room `@Entity` (it has no
 * table of its own); it is the projection of [AttributionDao.distinctAttributions].
 */
data class AttributionRow(
    val source: String,
    val license: String,
)

@Dao
interface AttributionDao {
    /**
     * Distinct `(source, license)` across the content-bearing tables `lexeme`, `sentence`,
     * and `accepted_answer` (the vetted provenance columns, C5 / §4.6), plus
     * `content_attribution` for corpus-level metadata credits such as the frequency spine.
     * UNION dedupes; the outer ORDER BY makes the credits screen deterministic (AC14).
     * This READS the vetting trail — it does not bypass the build-time gate that populated it.
     */
    @Query(
        "SELECT source, license FROM (" +
            "SELECT source, license FROM lexeme " +
            "UNION SELECT source, license FROM sentence " +
            "UNION SELECT source, license FROM accepted_answer " +
            "UNION SELECT source, license FROM content_attribution" +
            ") ORDER BY source ASC, license ASC"
    )
    suspend fun distinctAttributions(): List<AttributionRow>
}

@Dao
interface ConjugationDao {
    /**
     * Hot grading-path lookup: typed surface form → lemma lexeme id (§12.4). Returns null
     * for unknown forms so the repository can apply the exact-lemma fallback and log for
     * content review (never silently fail to credit).
     */
    @Query("SELECT * FROM conjugation_lemma_map WHERE surfaceForm = :surfaceForm")
    suspend fun getBySurfaceForm(surfaceForm: String): ConjugationLemmaMapEntity?
}

package com.magicalhippie.aprende.data.content

import android.util.Log
import com.magicalhippie.aprende.domain.model.Attribution
import com.magicalhippie.aprende.domain.model.Exercise
import com.magicalhippie.aprende.domain.model.Lexeme
import com.magicalhippie.aprende.domain.model.Node
import com.magicalhippie.aprende.domain.model.SentenceText
import com.magicalhippie.aprende.domain.repository.ContentRepository
import javax.inject.Inject

/**
 * Room-backed [ContentRepository] over the read-only `content.db` (SPEC §10.1, §12.1).
 *
 * Wraps the P0.3 content DAOs and maps the Room entities ↔ plain domain models so the domain
 * layer stays free of Room types. This is the only layer that bridges content↔progress (by id;
 * no cross-DB FK — SPEC §12.1, D2); the cross-DB join itself lives in the progress-aware
 * use-cases that compose this repo with [com.magicalhippie.aprende.domain.repository.ProgressRepository].
 */
class ContentRepositoryImpl @Inject constructor(
    private val lexemeDao: LexemeDao,
    private val exerciseDao: ExerciseDao,
    private val conjugationDao: ConjugationDao,
    private val nodeDao: NodeDao,
    private val acceptedAnswerDao: AcceptedAnswerDao,
    private val sentenceDao: SentenceDao,
    private val attributionDao: AttributionDao,
) : ContentRepository {

    override suspend fun getLexeme(lexemeId: Long): Lexeme? =
        lexemeDao.getById(lexemeId)?.toDomain()

    override suspend fun getExercise(exerciseId: Long): Exercise? =
        exerciseDao.getById(exerciseId)?.toDomain()

    override suspend fun nodes(): List<Node> =
        nodeDao.getAll().map { it.toDomain() }

    override suspend fun sentenceText(sentenceId: Long): SentenceText? =
        sentenceDao.getById(sentenceId)?.let {
            SentenceText(it.sentenceId, it.spanishText, it.englishText)
        }

    override suspend fun exercisesForNode(nodeId: Long): List<Exercise> =
        exerciseDao.forNode(nodeId).map { it.toDomain() }

    override suspend fun acceptedAnswers(sentenceId: Long, direction: String): List<String> =
        acceptedAnswerDao.getForSentence(sentenceId, direction).map { it.answerText }

    /**
     * Hot grading-path lookup: surface form → lemma lexeme id (SPEC §12.4).
     *
     * **Unknown-surface-form fallback (SPEC §12.1):** an unknown form returns `null` and is
     * logged for content review — never an exception, never a silent drop. The caller (the
     * grading use-case) then falls back to an exact-lemma match against the exercise's target
     * item so the learner is still credited.
     */
    override suspend fun resolveLemma(surfaceForm: String): Long? {
        val hit = conjugationDao.getBySurfaceForm(surfaceForm)
        if (hit == null) {
            // Log so unmapped forms can be added to the conjugation map during content review.
            // The caller MUST apply the exact-lemma fallback — we never silently fail to credit.
            Log.i(TAG, "Unknown surface form '$surfaceForm' — not in conjugation_lemma_map; caller falls back to exact-lemma match (SPEC §12.1)")
            return null
        }
        return hit.lemmaLexemeId
    }

    override suspend fun attributions(): List<Attribution> =
        attributionDao.distinctAttributions().map { Attribution(source = it.source, license = it.license) }

    private companion object {
        const val TAG = "ContentRepository"
    }
}

// --- entity -> domain mapping (Room types confined to this layer) ---

private fun LexemeEntity.toDomain(): Lexeme = Lexeme(
    lexemeId = lexemeId,
    lemma = lemma,
    pos = pos,
    englishGloss = englishGloss,
    frequencyRank = frequencyRank,
    cefrBand = cefrBand,
)

private fun NodeEntity.toDomain(): Node = Node(
    nodeId = nodeId,
    title = title,
    displayOrder = displayOrder,
)

private fun ExerciseEntity.toDomain(): Exercise = Exercise(
    exerciseId = exerciseId,
    nodeId = nodeId,
    sentenceId = sentenceId,
    type = type,
    direction = direction,
    targetItemId = targetItemId,
    targetItemType = targetItemType,
    promptHint = promptHint,
)

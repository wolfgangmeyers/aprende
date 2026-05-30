package com.magicalhippie.aprende.domain

import com.magicalhippie.aprende.domain.model.Attribution
import com.magicalhippie.aprende.domain.model.Exercise
import com.magicalhippie.aprende.domain.model.Lexeme
import com.magicalhippie.aprende.domain.model.Node
import com.magicalhippie.aprende.domain.model.SentenceText
import com.magicalhippie.aprende.domain.repository.ContentRepository

/** In-memory [ContentRepository] for JVM unit tests. */
class FakeContentRepository(
    private val exercisesByNode: Map<Long, List<Exercise>> = emptyMap(),
    private val lemmaMap: Map<String, Long> = emptyMap(),
    private val lexemes: Map<Long, Lexeme> = emptyMap(),
    private val nodes: List<Node> = emptyList(),
    /** Accepted answers keyed by (sentenceId, direction) for free-text grading. */
    private val acceptedAnswers: Map<Pair<Long, String>, List<String>> = emptyMap(),
    private val sentences: Map<Long, SentenceText> = emptyMap(),
    private val attributions: List<Attribution> = emptyList(),
) : ContentRepository {
    override suspend fun getLexeme(lexemeId: Long): Lexeme? = lexemes[lexemeId]

    override suspend fun getExercise(exerciseId: Long): Exercise? =
        exercisesByNode.values.flatten().find { it.exerciseId == exerciseId }

    override suspend fun nodes(): List<Node> = nodes

    override suspend fun sentenceText(sentenceId: Long): SentenceText? = sentences[sentenceId]

    override suspend fun exercisesForNode(nodeId: Long): List<Exercise> =
        exercisesByNode[nodeId] ?: emptyList()

    override suspend fun acceptedAnswers(sentenceId: Long, direction: String): List<String> =
        acceptedAnswers[sentenceId to direction] ?: emptyList()

    override suspend fun resolveLemma(surfaceForm: String): Long? = lemmaMap[surfaceForm]

    override suspend fun attributions(): List<Attribution> = attributions
}

/** Test helper: build an exercise whose target is a lexeme. */
fun exercise(id: Long, targetItemId: Long, nodeId: Long = 1, type: String = "TYPED_TRANSLATION"): Exercise =
    Exercise(
        exerciseId = id,
        nodeId = nodeId,
        sentenceId = id,
        type = type,
        direction = "ES_TO_EN",
        targetItemId = targetItemId,
        targetItemType = "LEXEME",
        promptHint = null,
    )

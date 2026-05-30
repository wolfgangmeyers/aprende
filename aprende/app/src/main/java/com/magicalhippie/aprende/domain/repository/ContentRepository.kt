package com.magicalhippie.aprende.domain.repository

import com.magicalhippie.aprende.domain.model.Attribution
import com.magicalhippie.aprende.domain.model.Exercise
import com.magicalhippie.aprende.domain.model.Lexeme
import com.magicalhippie.aprende.domain.model.Node
import com.magicalhippie.aprende.domain.model.SentenceText

/**
 * Read-only access to the bundled curriculum in `content.db` (SPEC §10.1, §12.1).
 *
 * Declared in the domain layer; the Room-backed implementation wraps the content DAOs and is
 * bound via Hilt. Returns plain domain models, never Room entities.
 */
interface ContentRepository {
    suspend fun getLexeme(lexemeId: Long): Lexeme?
    suspend fun getExercise(exerciseId: Long): Exercise?

    /** All Path nodes in display order — the home/Path list (SPEC §7, §12.2). */
    suspend fun nodes(): List<Node>

    /** The (spanishText, englishText) of a sentence, or null — drives the lesson prompt (SPEC §7). */
    suspend fun sentenceText(sentenceId: Long): SentenceText?

    /** All exercises belonging to a Path node — the candidate pool for a lesson (SPEC §7). */
    suspend fun exercisesForNode(nodeId: Long): List<Exercise>

    /**
     * The vetted accepted-answer texts for a sentence in a grading direction (content.db
     * `accepted_answer`, C5/§4.6) — the only legitimate source of free-text answer keys
     * (SPEC §5.5; never invented at runtime). Empty if the sentence has none.
     */
    suspend fun acceptedAnswers(sentenceId: Long, direction: String): List<String>

    /**
     * Resolve a typed surface form to its lemma's lexeme id via `conjugation_lemma_map`
     * (hot grading path, SPEC §12.4).
     *
     * **Unknown-surface-form fallback (SPEC §12.1):** if [surfaceForm] is not in the map,
     * returns `null` AND logs it for content review — the caller must then fall back to an
     * exact-lemma match against the exercise's target item, never silently failing to credit
     * the learner.
     */
    suspend fun resolveLemma(surfaceForm: String): Long?

    /**
     * The distinct `(source, license)` credits across the content-bearing tables
     * (`lexeme` / `sentence` / `accepted_answer`) — the vetted provenance that the in-app
     * credits screen renders (SPEC §4.5/§4.6, C4/C5, AC14). Sorted deterministically. This
     * READS the vetting trail; it never bypasses the build-time gate that put it there.
     */
    suspend fun attributions(): List<Attribution>
}

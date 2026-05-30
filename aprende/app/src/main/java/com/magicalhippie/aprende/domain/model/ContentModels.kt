package com.magicalhippie.aprende.domain.model

/**
 * Plain domain models for read-only content (SPEC §12.1). The data layer maps the
 * `content.db` Room entities ↔ these, keeping the domain layer free of Room types. Only the
 * fields the domain needs in P1.1 are surfaced; later phases extend these as needed.
 */

/** A dictionary headword (SPEC §10.1 `lexeme`). */
data class Lexeme(
    val lexemeId: Long,
    val lemma: String,
    val pos: String,
    val englishGloss: String,
    val frequencyRank: Int,
    val cefrBand: String,
)

/** The bilingual text of a sentence (SPEC §10.1 `sentence`) — the lesson prompt source. */
data class SentenceText(
    val sentenceId: Long,
    val spanishText: String,
    val englishText: String,
)

/** A Path node — the unit a lesson is generated for (SPEC §10.1 `node`, §7). */
data class Node(
    val nodeId: Long,
    val title: String,
    val displayOrder: Int,
)

/**
 * A distinct content credit: a `(source, license)` pair drawn from the vetted provenance
 * columns of `content.db` (SPEC §4.5/§4.6, C4/C5, AC14). Surfaced verbatim from the data —
 * the attribution screen renders these credits and never invents them.
 */
data class Attribution(
    val source: String,
    val license: String,
)

/** A curriculum exercise (SPEC §10.1 `exercise`). */
data class Exercise(
    val exerciseId: Long,
    val nodeId: Long,
    val sentenceId: Long,
    val type: String,
    val direction: String,
    val targetItemId: Long,
    val targetItemType: String,
    val promptHint: String?,
)

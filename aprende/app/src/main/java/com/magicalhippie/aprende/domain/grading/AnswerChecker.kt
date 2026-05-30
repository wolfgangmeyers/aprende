package com.magicalhippie.aprende.domain.grading

import java.text.Normalizer

/** Outcome of checking one answer (SPEC §5.5). */
enum class GradeVerdict { CORRECT, CORRECT_WITH_TYPO, WRONG }

data class GradeResult(val verdict: GradeVerdict) {
    val correct: Boolean get() = verdict != GradeVerdict.WRONG

    /** True when accepted only after accent-insensitive / edit-distance leniency (soft "typo"). */
    val forgivenTypo: Boolean get() = verdict == GradeVerdict.CORRECT_WITH_TYPO
}

/**
 * Deterministic, on-device answer checking (SPEC §5.5). Pure Kotlin — no Android, no NLP,
 * no network — so it runs client-only and is fully JVM-unit-testable.
 *
 * Free text (typed translation, listen-and-type, fill-in-the-blank):
 *   1. normalize (NFC, lowercase, trim, strip terminal punctuation, collapse whitespace)
 *   2. exact match against any accepted variant -> CORRECT
 *   3. accent-insensitive match -> CORRECT_WITH_TYPO (a missing accent is never a failure)
 *   4. Damerau-Levenshtein (OSA) within a length-scaled threshold -> CORRECT_WITH_TYPO
 *   else WRONG.
 * Tiles / matching / multiple-choice are constrained-selection: graded by exact equality.
 */
object AnswerChecker {

    private const val PUNCT = "¿¡.?!,;:\"'()«»…"

    /** Normalize a free-text answer for comparison. */
    fun normalize(input: String): String {
        val nfc = Normalizer.normalize(input, Normalizer.Form.NFC)
        val collapsed = nfc.lowercase().replace(WHITESPACE, " ")
        return collapsed.trim { it.isWhitespace() || it in PUNCT }
    }

    /** Strip combining diacritics so e.g. "tú"->"tu", "año"->"ano" (accent-insensitive form). */
    fun deaccent(normalized: String): String {
        val nfd = Normalizer.normalize(normalized, Normalizer.Form.NFD)
        return nfd.replace(COMBINING_MARKS, "")
    }

    /**
     * Optimal String Alignment (restricted Damerau-Levenshtein) distance: insertion,
     * deletion, substitution, and adjacent transposition — covers the bulk of human typos.
     */
    fun damerauLevenshtein(a: String, b: String): Int {
        val n = a.length
        val m = b.length
        if (n == 0) return m
        if (m == 0) return n
        val d = Array(n + 1) { IntArray(m + 1) }
        for (i in 0..n) d[i][0] = i
        for (j in 0..m) d[0][j] = j
        for (i in 1..n) {
            for (j in 1..m) {
                val cost = if (a[i - 1] == b[j - 1]) 0 else 1
                var best = minOf(
                    d[i - 1][j] + 1, // deletion
                    d[i][j - 1] + 1, // insertion
                    d[i - 1][j - 1] + cost, // substitution
                )
                if (i > 1 && j > 1 && a[i - 1] == b[j - 2] && a[i - 2] == b[j - 1]) {
                    best = minOf(best, d[i - 2][j - 2] + 1) // adjacent transposition
                }
                d[i][j] = best
            }
        }
        return d[n][m]
    }

    /** Max edit distance tolerated for a typo, scaled to answer length. */
    fun typoThreshold(length: Int): Int = if (length <= 4) 1 else 2

    /** Grade a free-text answer against the curated accepted-answer set (SPEC §5.5). */
    fun checkFreeText(input: String, accepted: Collection<String>): GradeResult {
        if (accepted.isEmpty()) return GradeResult(GradeVerdict.WRONG)
        val n = normalize(input)
        val acc = accepted.map { normalize(it) }
        if (acc.any { it == n }) return GradeResult(GradeVerdict.CORRECT)

        val nd = deaccent(n)
        if (acc.any { deaccent(it) == nd }) return GradeResult(GradeVerdict.CORRECT_WITH_TYPO)

        val threshold = typoThreshold(nd.length)
        if (acc.any { damerauLevenshtein(deaccent(it), nd) <= threshold }) {
            return GradeResult(GradeVerdict.CORRECT_WITH_TYPO)
        }
        return GradeResult(GradeVerdict.WRONG)
    }

    /** Grade word-bank / arrange-the-words / matching: exact token-sequence equality. */
    fun checkTokens(input: List<String>, acceptedOrderings: Collection<List<String>>): GradeResult =
        if (acceptedOrderings.any { it == input }) GradeResult(GradeVerdict.CORRECT) else GradeResult(GradeVerdict.WRONG)

    /** Grade multiple-choice / select-the-missing-word: selected index equals the correct index. */
    fun checkChoice(selectedIndex: Int, correctIndex: Int): GradeResult =
        if (selectedIndex == correctIndex) GradeResult(GradeVerdict.CORRECT) else GradeResult(GradeVerdict.WRONG)

    private val WHITESPACE = Regex("\\s+")
    private val COMBINING_MARKS = Regex("\\p{Mn}+")
}

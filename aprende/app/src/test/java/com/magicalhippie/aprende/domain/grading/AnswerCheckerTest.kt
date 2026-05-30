package com.magicalhippie.aprende.domain.grading

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Deterministic answer-checking (SPEC §5.5). Cases verified against an independent
 * reference implementation. Covers AC2 (accent/typo leniency, wrong word rejected) and
 * AC3 (any accepted-set member passes).
 */
class AnswerCheckerTest {

    private fun verdict(input: String, vararg accepted: String): GradeVerdict =
        AnswerChecker.checkFreeText(input, accepted.toList()).verdict

    @Test
    fun `AC2 - a missing accent is accepted as a forgiven typo, not a failure`() {
        val result = AnswerChecker.checkFreeText("tu", listOf("tú"))
        assertEquals(GradeVerdict.CORRECT_WITH_TYPO, result.verdict)
        assertTrue(result.correct)
        assertTrue(result.forgivenTypo)
    }

    @Test
    fun `case and terminal punctuation are normalized away (clean correct)`() {
        val result = AnswerChecker.checkFreeText("Tú.", listOf("tú"))
        assertEquals(GradeVerdict.CORRECT, result.verdict)
        assertFalse(result.forgivenTypo)
    }

    @Test
    fun `AC2 - a single-character typo within threshold is accepted`() {
        assertEquals(GradeVerdict.CORRECT_WITH_TYPO, verdict("watre", "water")) // transposition
        assertEquals(GradeVerdict.CORRECT_WITH_TYPO, verdict("watter", "water")) // insertion
    }

    @Test
    fun `AC2 - a genuinely wrong word is rejected`() {
        assertEquals(GradeVerdict.WRONG, verdict("house", "water"))
        assertEquals(GradeVerdict.WRONG, verdict("gato", "perro"))
    }

    @Test
    fun `a missing word is rejected (distance exceeds the typo threshold)`() {
        assertEquals(GradeVerdict.WRONG, verdict("perro", "el perro"))
    }

    @Test
    fun `AC3 - any member of the accepted-answer set is correct`() {
        val accepted = listOf("the water's cold", "the water is cold")
        assertEquals(GradeVerdict.CORRECT, AnswerChecker.checkFreeText("the water is cold", accepted).verdict)
        assertEquals(GradeVerdict.CORRECT, AnswerChecker.checkFreeText("The water's cold!", accepted).verdict)
    }

    @Test
    fun `empty accepted set is always wrong`() {
        assertEquals(GradeVerdict.WRONG, AnswerChecker.checkFreeText("anything", emptyList()).verdict)
    }

    @Test
    fun `Damerau-Levenshtein counts an adjacent transposition as distance one`() {
        assertEquals(1, AnswerChecker.damerauLevenshtein("water", "watre"))
        assertEquals(0, AnswerChecker.damerauLevenshtein("perro", "perro"))
        assertEquals(5, AnswerChecker.damerauLevenshtein("water", "house"))
    }

    @Test
    fun `tokens are graded by exact ordering`() {
        val accepted = listOf(listOf("yo", "tengo", "un", "perro"))
        assertEquals(GradeVerdict.CORRECT, AnswerChecker.checkTokens(listOf("yo", "tengo", "un", "perro"), accepted).verdict)
        assertEquals(GradeVerdict.WRONG, AnswerChecker.checkTokens(listOf("tengo", "yo", "un", "perro"), accepted).verdict)
    }

    @Test
    fun `multiple choice is graded by selected index`() {
        assertEquals(GradeVerdict.CORRECT, AnswerChecker.checkChoice(selectedIndex = 2, correctIndex = 2).verdict)
        assertEquals(GradeVerdict.WRONG, AnswerChecker.checkChoice(selectedIndex = 0, correctIndex = 2).verdict)
    }
}

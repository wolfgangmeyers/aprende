package com.magicalhippie.aprende.domain.grading

import javax.inject.Inject

/**
 * Grades a single exercise answer using the deterministic [AnswerChecker] (SPEC §5.5).
 * This is the domain seam the lesson/review flow calls; the [GradeResult]'s `correct` and
 * `forgivenTypo` feed the SRS grade derivation (SPEC §6.4 via ScheduleReviewUseCase).
 *
 * The accepted-answer set for free text comes from vetted content (content.db
 * `accepted_answer`, C5/§4.6) — passed in by the caller, never invented here.
 */
class GradeAnswerUseCase @Inject constructor() {

    fun gradeFreeText(input: String, acceptedAnswers: Collection<String>): GradeResult =
        AnswerChecker.checkFreeText(input, acceptedAnswers)

    fun gradeTokens(input: List<String>, acceptedOrderings: Collection<List<String>>): GradeResult =
        AnswerChecker.checkTokens(input, acceptedOrderings)

    fun gradeChoice(selectedIndex: Int, correctIndex: Int): GradeResult =
        AnswerChecker.checkChoice(selectedIndex, correctIndex)
}

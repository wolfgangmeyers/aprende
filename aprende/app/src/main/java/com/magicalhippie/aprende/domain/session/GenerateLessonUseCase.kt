package com.magicalhippie.aprende.domain.session

import com.magicalhippie.aprende.domain.model.Exercise
import com.magicalhippie.aprende.domain.model.ItemType
import com.magicalhippie.aprende.domain.repository.ContentRepository
import com.magicalhippie.aprende.domain.repository.ProgressRepository
import javax.inject.Inject

/**
 * Builds a lesson [LessonPlan] for a Path node (SPEC §7 step 1–3): pull the node's exercise
 * pool, classify each as **new** (its target item has no SRS row yet) or **review** (it does),
 * then interleave new and review up to a target length, introducing new items early.
 *
 * Exercise-type mixing per §7.3 is driven by the exercise's own `type` (authored in content);
 * this use-case decides *which* exercises and *in what order*, not the rendering.
 */
class GenerateLessonUseCase @Inject constructor(
    private val content: ContentRepository,
    private val progress: ProgressRepository,
) {
    suspend fun generate(nodeId: Long, targetLength: Int = DEFAULT_TARGET_LENGTH): LessonPlan {
        val pool = content.exercisesForNode(nodeId)
        val newOnes = mutableListOf<Exercise>()
        val reviewOnes = mutableListOf<Exercise>()
        for (ex in pool) {
            val seen = progress.getSrsItem(ex.targetItemId, ItemType.valueOf(ex.targetItemType)) != null
            (if (seen) reviewOnes else newOnes).add(ex)
        }
        val newIds = newOnes.mapTo(HashSet()) { it.exerciseId }
        val ordered = includeMultipleChoiceIfAvailable(
            ordered = interleave(newOnes, reviewOnes, targetLength),
            pool = pool,
            cap = targetLength,
            newExerciseIds = newIds,
        )
        return LessonPlan(
            exercises = ordered,
            newExerciseIds = ordered.mapNotNull { it.exerciseId.takeIf { id -> id in newIds } }.toSet(),
        )
    }

    suspend fun generateReplayFromBeginning(nodeId: Long, targetLength: Int = DEFAULT_TARGET_LENGTH): LessonPlan {
        val ordered = content.exercisesForNode(nodeId).take(targetLength)
        val newIds = ordered
            .filter { progress.getSrsItem(it.targetItemId, ItemType.valueOf(it.targetItemType)) == null }
            .mapTo(HashSet()) { it.exerciseId }
        return LessonPlan(exercises = ordered, newExerciseIds = newIds)
    }

    /** Interleave new and review (new-first) up to [cap], so new material is introduced early. */
    private fun interleave(new: List<Exercise>, review: List<Exercise>, cap: Int): List<Exercise> {
        val result = ArrayList<Exercise>(minOf(cap, new.size + review.size))
        var i = 0
        var j = 0
        while (result.size < cap && (i < new.size || j < review.size)) {
            if (i < new.size) {
                result.add(new[i]); i++
                if (result.size >= cap) break
            }
            if (j < review.size) {
                result.add(review[j]); j++
            }
        }
        return result
    }

    private fun includeMultipleChoiceIfAvailable(
        ordered: List<Exercise>,
        pool: List<Exercise>,
        cap: Int,
        newExerciseIds: Set<Long>,
    ): List<Exercise> {
        if (ordered.any { it.type == "MULTIPLE_CHOICE" }) return ordered
        val multipleChoice = pool.filter { it.type == "MULTIPLE_CHOICE" }.minWithOrNull(scaffoldedFirst) ?: return ordered
        if (ordered.size < cap) return ordered + multipleChoice
        if (ordered.isEmpty()) return listOf(multipleChoice)
        val replacementSlot = ordered.last()
        val replacementIsNew = replacementSlot.exerciseId in newExerciseIds
        val replacement = pool
            .filter { it.type == "MULTIPLE_CHOICE" }
            .filter { (it.exerciseId in newExerciseIds) == replacementIsNew }
            .filter { scaffoldPriority(it) <= scaffoldPriority(replacementSlot) }
            .minWithOrNull(scaffoldedFirst)
            ?: return ordered
        return ordered.dropLast(1) + replacement
    }

    companion object {
        const val DEFAULT_TARGET_LENGTH = 16

        private val scaffoldedFirst = compareBy<Exercise>(
            { scaffoldPriority(it) },
            { it.exerciseId },
        )

        private fun scaffoldPriority(exercise: Exercise): Int = when {
            exercise.type == "MULTIPLE_CHOICE" && exercise.direction == "EN_TO_ES" -> 0
            exercise.direction == "EN_TO_ES" -> 1
            exercise.type == "MULTIPLE_CHOICE" -> 2
            exercise.type == "WORD_BANK" -> 3
            else -> 4
        }
    }
}

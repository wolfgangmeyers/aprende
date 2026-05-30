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
        val ordered = interleave(newOnes, reviewOnes, targetLength)
        val newIds = newOnes.mapTo(HashSet()) { it.exerciseId }
        return LessonPlan(
            exercises = ordered,
            newExerciseIds = ordered.mapNotNull { it.exerciseId.takeIf { id -> id in newIds } }.toSet(),
        )
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

    companion object {
        const val DEFAULT_TARGET_LENGTH = 16
    }
}

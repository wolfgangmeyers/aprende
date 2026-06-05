package com.magicalhippie.aprende.domain.session

import com.magicalhippie.aprende.domain.FakeContentRepository
import com.magicalhippie.aprende.domain.FakeProgressRepository
import com.magicalhippie.aprende.domain.exercise
import com.magicalhippie.aprende.domain.model.ItemType
import com.magicalhippie.aprende.domain.model.SrsItem
import com.magicalhippie.aprende.domain.model.SrsState
import com.magicalhippie.aprende.domain.srs.SrsItemState
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class GenerateLessonUseCaseTest {

    private val node = 1L
    private val pool = listOf(
        exercise(id = 10, targetItemId = 1),
        exercise(id = 20, targetItemId = 2),
        exercise(id = 30, targetItemId = 3),
    )
    private val content = FakeContentRepository(exercisesByNode = mapOf(node to pool))

    private fun seenItem(itemId: Long) = SrsItem(
        itemId = itemId, itemType = ItemType.LEXEME,
        state = SrsItemState(5.0, 2.0, 0L, 1L),
        lifecycle = SrsState.REVIEW, timesSeen = 1, timesCorrect = 1, timesWrong = 0,
    )

    @Test
    fun `with nothing seen, every exercise is new`() = runTest {
        val plan = GenerateLessonUseCase(content, FakeProgressRepository()).generate(node)
        assertEquals(3, plan.size)
        assertEquals(setOf(10L, 20L, 30L), plan.newExerciseIds)
    }

    @Test
    fun `a previously-seen target item is classified as review, not new`() = runTest {
        val progress = FakeProgressRepository()
        progress.upsertSrsItem(seenItem(2)) // item 2 already seen
        val plan = GenerateLessonUseCase(content, progress).generate(node)
        assertEquals(3, plan.size)
        assertTrue("exercise 20 (item 2) is review, not new", 20L !in plan.newExerciseIds)
        assertEquals(setOf(10L, 30L), plan.newExerciseIds)
    }

    @Test
    fun `target length caps the plan size`() = runTest {
        val plan = GenerateLessonUseCase(content, FakeProgressRepository()).generate(node, targetLength = 2)
        assertEquals(2, plan.size)
    }

    @Test
    fun `cold start preserves generated scaffold-first early progression`() = runTest {
        val scaffolded = (1L..8L).map { index ->
            exercise(
                id = index * 10,
                targetItemId = index,
                type = "MULTIPLE_CHOICE",
                direction = "EN_TO_ES",
            )
        }
        val typed = (9L..12L).map { index ->
            exercise(
                id = index * 10,
                targetItemId = index,
                type = "TYPED_TRANSLATION",
                direction = "ES_TO_EN",
            )
        }
        val coldStartPool = scaffolded + typed
        val plan = GenerateLessonUseCase(
            FakeContentRepository(exercisesByNode = mapOf(node to coldStartPool)),
            FakeProgressRepository(),
        ).generate(node)

        assertEquals(scaffolded.map { it.exerciseId }, plan.exercises.take(8).map { it.exerciseId })
        assertTrue(plan.exercises.take(8).all { it.type == "MULTIPLE_CHOICE" && it.direction == "EN_TO_ES" })
    }

    @Test
    fun `multiple choice is included when available past the target length cap`() = runTest {
        val cappedPool = listOf(
            exercise(id = 10, targetItemId = 1, type = "TYPED_TRANSLATION"),
            exercise(id = 20, targetItemId = 2, type = "TYPED_TRANSLATION"),
            exercise(id = 30, targetItemId = 3, type = "MULTIPLE_CHOICE"),
        )
        val plan = GenerateLessonUseCase(
            FakeContentRepository(exercisesByNode = mapOf(node to cappedPool)),
            FakeProgressRepository(),
        ).generate(node, targetLength = 2)

        assertEquals(2, plan.size)
        assertEquals(listOf(10L, 30L), plan.exercises.map { it.exerciseId })
    }

    @Test
    fun `multiple choice cap fallback prefers English prompt scaffold`() = runTest {
        val cappedPool = listOf(
            exercise(id = 10, targetItemId = 1, type = "TYPED_TRANSLATION", direction = "ES_TO_EN"),
            exercise(id = 30, targetItemId = 3, type = "MULTIPLE_CHOICE", direction = "ES_TO_EN"),
            exercise(id = 40, targetItemId = 4, type = "MULTIPLE_CHOICE", direction = "EN_TO_ES"),
        )
        val progress = FakeProgressRepository()
        progress.upsertSrsItem(seenItem(1))
        progress.upsertSrsItem(seenItem(3))
        progress.upsertSrsItem(seenItem(4))

        val plan = GenerateLessonUseCase(
            FakeContentRepository(exercisesByNode = mapOf(node to cappedPool)),
            progress,
        ).generate(node, targetLength = 1)

        assertEquals(listOf(40L), plan.exercises.map { it.exerciseId })
    }

    @Test
    fun `multiple choice cap fallback does not replace a new scaffold with review prompt`() = runTest {
        val cappedPool = listOf(
            exercise(id = 10, targetItemId = 1, type = "TYPED_TRANSLATION", direction = "EN_TO_ES"),
            exercise(id = 30, targetItemId = 3, type = "MULTIPLE_CHOICE", direction = "ES_TO_EN"),
        )
        val progress = FakeProgressRepository()
        progress.upsertSrsItem(seenItem(3))

        val plan = GenerateLessonUseCase(
            FakeContentRepository(exercisesByNode = mapOf(node to cappedPool)),
            progress,
        ).generate(node, targetLength = 1)

        assertEquals(listOf(10L), plan.exercises.map { it.exerciseId })
    }
}

package com.magicalhippie.aprende.domain.session

import com.magicalhippie.aprende.domain.FakeProgressRepository
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset

/** Completing a node writes node_progress (the §7-step-6 progress write). */
class CompleteNodeUseCaseTest {

    private val now = Instant.parse("2026-01-01T12:00:00Z")
    private val clock = Clock.fixed(now, ZoneOffset.UTC)

    @Test
    fun `first completion writes level 1 with a completion timestamp`() = runTest {
        val repo = FakeProgressRepository()
        val useCase = CompleteNodeUseCase(repo, clock)

        val result = useCase.complete(nodeId = 1)

        assertEquals(1, result.level)
        assertEquals(now.toEpochMilli(), result.completedAtMillis)
        val persisted = repo.getNodeProgress(1)
        assertNotNull("node_progress is persisted", persisted)
        assertEquals(1, persisted!!.level)
    }

    @Test
    fun `re-completing a node raises its crown level, never resets it`() = runTest {
        val repo = FakeProgressRepository()
        val useCase = CompleteNodeUseCase(repo, clock)

        useCase.complete(1)
        val second = useCase.complete(1)

        assertEquals(2, second.level)
        assertEquals(2, repo.getNodeProgress(1)!!.level)
    }
}

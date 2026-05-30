package com.magicalhippie.aprende.domain.session

import com.magicalhippie.aprende.domain.model.NodeProgress
import com.magicalhippie.aprende.domain.repository.ProgressRepository
import java.time.Clock
import javax.inject.Inject

/**
 * Records that a Path node's lesson was completed (SPEC §7 step 6, §10.2). Each completion
 * bumps the node's crown [NodeProgress.level] by one (level ≥ 1 means "complete", which drives
 * positional unlock — §4.4 / [PathUnlock]) and stamps `completedAtMillis` from the injected
 * [Clock]. Idempotent in shape: re-completing a node raises its crown level, never resets it.
 */
class CompleteNodeUseCase @Inject constructor(
    private val progress: ProgressRepository,
    private val clock: Clock,
) {
    suspend fun complete(nodeId: Long): NodeProgress {
        val existing = progress.getNodeProgress(nodeId)
        val updated = NodeProgress(
            nodeId = nodeId,
            level = (existing?.level ?: 0) + 1,
            legendary = existing?.legendary ?: false,
            completedAtMillis = clock.millis(),
        )
        progress.upsertNodeProgress(updated)
        return updated
    }
}

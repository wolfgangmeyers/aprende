package com.magicalhippie.aprende.domain.gamification

import com.magicalhippie.aprende.domain.model.UserStats

/** Starting stats for a brand-new learner (SPEC §9): full hearts, no XP/streak/gems. */
val NEW_USER_STATS = UserStats(
    totalXp = 0,
    gems = 0,
    hearts = Hearts.MAX,
    heartsLostAtMillis = null,
    streakLength = 0,
    streakFreezes = 0,
    wordsLearned = 0,
    lastActiveLocalDate = null,
)

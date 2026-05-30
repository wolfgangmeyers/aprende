package com.magicalhippie.aprende.domain

import java.time.Clock
import java.time.Instant
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.temporal.ChronoUnit

/** A [Clock] whose instant can be advanced, for testing time-dependent logic deterministically. */
class MutableClock(
    var instant: Instant = Instant.parse("2026-01-01T12:00:00Z"),
    private val zone: ZoneId = ZoneOffset.UTC,
) : Clock() {
    override fun instant(): Instant = instant
    override fun getZone(): ZoneId = zone
    override fun withZone(z: ZoneId): Clock = MutableClock(instant, z)
    fun advanceMillis(ms: Long) { instant = instant.plusMillis(ms) }
    fun advanceDays(days: Long) { instant = instant.plus(days, ChronoUnit.DAYS) }
}

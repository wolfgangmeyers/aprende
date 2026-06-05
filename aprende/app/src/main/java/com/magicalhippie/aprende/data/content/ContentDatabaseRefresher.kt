package com.magicalhippie.aprende.data.content

import android.content.Context
import java.security.MessageDigest

/**
 * Replaces Room's copied prepackaged content DB when the bundled asset changes without a
 * schema-version bump. The curriculum DB is read-only and replaceable; learner state lives in
 * progress.db and is deliberately outside this refresh path.
 */
object ContentDatabaseRefresher {
    private const val ASSET_PATH = "database/content.db"
    private const val PREFS_NAME = "content_database_asset"
    private const val PREF_ASSET_SHA = "asset_sha256"

    fun refreshIfBundledAssetChanged(
        context: Context,
        databaseName: String = ContentDatabase.DATABASE_NAME,
        assetPath: String = ASSET_PATH,
    ): RefreshResult {
        val assetHash = context.assets.open(assetPath).use { it.sha256() }
        val databaseFile = context.getDatabasePath(databaseName)
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

        if (!databaseFile.exists()) {
            prefs.edit().putString(PREF_ASSET_SHA, assetHash).apply()
            return RefreshResult(refreshed = false, reason = RefreshReason.NO_INSTALLED_DATABASE)
        }

        val installedHash = databaseFile.inputStream().use { it.sha256() }
        if (installedHash == assetHash) {
            prefs.edit().putString(PREF_ASSET_SHA, assetHash).apply()
            return RefreshResult(refreshed = false, reason = RefreshReason.INSTALLED_DATABASE_CURRENT)
        }

        val deleted = context.deleteDatabase(databaseName)
        if (!deleted && databaseFile.exists()) {
            throw IllegalStateException("Unable to replace stale bundled content database")
        }
        prefs.edit().putString(PREF_ASSET_SHA, assetHash).apply()
        return RefreshResult(refreshed = true, reason = RefreshReason.INSTALLED_DATABASE_STALE)
    }

    private fun java.io.InputStream.sha256(): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
        while (true) {
            val read = read(buffer)
            if (read < 0) break
            digest.update(buffer, 0, read)
        }
        return digest.digest().joinToString(separator = "") { "%02x".format(it) }
    }
}

data class RefreshResult(
    val refreshed: Boolean,
    val reason: RefreshReason,
)

enum class RefreshReason {
    NO_INSTALLED_DATABASE,
    INSTALLED_DATABASE_CURRENT,
    INSTALLED_DATABASE_STALE,
}

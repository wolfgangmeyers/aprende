package com.magicalhippie.aprende.data.content

import android.database.sqlite.SQLiteDatabase
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import org.junit.Before
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ContentDatabaseRefresherTest {
    private val context get() = ApplicationProvider.getApplicationContext<android.content.Context>()

    @Before
    fun setUp() {
        cleanState()
    }

    @After
    fun tearDown() {
        cleanState()
    }

    private fun cleanState() {
        context.deleteDatabase(ContentDatabase.DATABASE_NAME)
        context.deleteDatabase("progress.db")
        context.getSharedPreferences("content_database_asset", android.content.Context.MODE_PRIVATE)
            .edit()
            .clear()
            .commit()
    }

    @Test
    fun `stale installed content db is refreshed from bundled asset while progress db remains`() {
        val contentFile = context.getDatabasePath(ContentDatabase.DATABASE_NAME)
        contentFile.parentFile!!.mkdirs()
        contentFile.writeText("stale copied content db from prior install")

        val progressFile = context.getDatabasePath("progress.db")
        progressFile.writeText("learner progress must not be touched")

        val refresh = ContentDatabaseRefresher.refreshIfBundledAssetChanged(context)

        assertTrue(refresh.refreshed)
        assertEquals(RefreshReason.INSTALLED_DATABASE_STALE, refresh.reason)
        assertFalse(contentFile.exists())
        assertTrue(progressFile.exists())
        assertEquals("learner progress must not be touched", progressFile.readText())

        val db = Room.databaseBuilder(
            context,
            ContentDatabase::class.java,
            ContentDatabase.DATABASE_NAME,
        )
            .createFromAsset("database/content.db")
            .allowMainThreadQueries()
            .build()

        try {
            assertEquals(6_225L, db.scalarLong("SELECT COUNT(*) FROM exercise"))
            assertEquals(
                "MULTIPLE_CHOICE|EN_TO_ES|Hi, how are you?",
                db.scalarString(
                    """
                    SELECT e.type || '|' || e.direction || '|' || s.englishText
                    FROM node n
                    JOIN exercise e ON e.nodeId = n.nodeId
                    JOIN sentence s ON s.sentenceId = e.sentenceId
                    WHERE n.title = 'A1 Unit 1.1'
                    ORDER BY e.exerciseId ASC
                    LIMIT 1
                    """.trimIndent(),
                ),
            )
        } finally {
            db.close()
        }
    }

    @Test
    fun `stale installed content db is refreshed even when asset marker was already current`() {
        val firstLaunch = ContentDatabaseRefresher.refreshIfBundledAssetChanged(context)
        assertFalse(firstLaunch.refreshed)
        assertEquals(RefreshReason.NO_INSTALLED_DATABASE, firstLaunch.reason)

        val contentFile = context.getDatabasePath(ContentDatabase.DATABASE_NAME)
        contentFile.parentFile!!.mkdirs()
        SQLiteDatabase.openOrCreateDatabase(contentFile, null).use { db ->
            db.execSQL("PRAGMA user_version = 2")
            db.execSQL("CREATE TABLE node (nodeId INTEGER PRIMARY KEY, title TEXT, displayOrder INTEGER)")
            db.execSQL(
                "CREATE TABLE sentence (sentenceId INTEGER PRIMARY KEY, spanishText TEXT, englishText TEXT)",
            )
            db.execSQL(
                """
                CREATE TABLE exercise (
                    exerciseId INTEGER PRIMARY KEY,
                    nodeId INTEGER,
                    sentenceId INTEGER,
                    type TEXT,
                    direction TEXT,
                    targetItemId INTEGER,
                    targetItemType TEXT,
                    promptHint TEXT
                )
                """.trimIndent(),
            )
            db.execSQL("INSERT INTO node VALUES (1, 'A1 Unit 1.1', 1)")
            db.execSQL("INSERT INTO sentence VALUES (1, 'Hola, ¿cómo estás?', 'Hi, how are you?')")
            db.execSQL(
                "INSERT INTO exercise VALUES (1, 1, 1, 'TYPED_TRANSLATION', 'ES_TO_EN', 1, 'LEXEME', NULL)",
            )
        }

        val refresh = ContentDatabaseRefresher.refreshIfBundledAssetChanged(context)

        assertTrue(refresh.refreshed)
        assertEquals(RefreshReason.INSTALLED_DATABASE_STALE, refresh.reason)

        val db = Room.databaseBuilder(
            context,
            ContentDatabase::class.java,
            ContentDatabase.DATABASE_NAME,
        )
            .createFromAsset("database/content.db")
            .allowMainThreadQueries()
            .build()

        try {
            assertEquals(6_225L, db.scalarLong("SELECT COUNT(*) FROM exercise"))
        } finally {
            db.close()
        }
    }

    @Test
    fun `byte-identical installed content db is kept`() {
        val contentFile = context.getDatabasePath(ContentDatabase.DATABASE_NAME)
        contentFile.parentFile!!.mkdirs()
        context.assets.open("database/content.db").use { input ->
            contentFile.outputStream().use { output -> input.copyTo(output) }
        }
        assertTrue(contentFile.exists())

        val refresh = ContentDatabaseRefresher.refreshIfBundledAssetChanged(context)

        assertFalse(refresh.refreshed)
        assertEquals(RefreshReason.INSTALLED_DATABASE_CURRENT, refresh.reason)
        assertTrue(contentFile.exists())
    }

    private fun ContentDatabase.scalarLong(sql: String): Long {
        val cursor = openHelper.readableDatabase.query(sql)
        cursor.use {
            assertTrue(it.moveToFirst())
            return it.getLong(0)
        }
    }

    private fun ContentDatabase.scalarString(sql: String): String {
        val cursor = openHelper.readableDatabase.query(sql)
        cursor.use {
            assertTrue(it.moveToFirst())
            return it.getString(0)
        }
    }
}

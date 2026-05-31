package com.magicalhippie.aprende.data.content

import androidx.room.Entity
import androidx.room.Fts4
import androidx.room.PrimaryKey

/**
 * Room entities for the read-only `content.db` curriculum asset (SPEC §10.1, D2).
 *
 * These classes are the **schema contract**: the Python content pipeline
 * (`tools/content-pipeline/build_content_db.py` → `SCHEMA_DDL`) builds `content.db`
 * to match the schema Room exports from these entities. Room validates the bundled
 * asset against this exported schema on `createFromAsset`, and **fails prepopulation
 * on any mismatch** — so table names, column names, nullability, and type affinity
 * here MUST mirror the DDL exactly.
 *
 * Property names are chosen to equal the SQLite column names, so no `@ColumnInfo`
 * renaming is needed. Provenance columns (`source`, `sourceId`, `license`,
 * `vettingStatus`, `reviewedBy`, `reviewedAt`) implement the C5 / §4.6 vetting trail.
 *
 * SQLite/Room type-affinity mapping used here:
 *   - `INTEGER`  ↔ Kotlin `Long`  (PKs and id columns)
 *   - `INTEGER`  ↔ Kotlin `Int`   (small counts/ranks — still INTEGER affinity)
 *   - `REAL`     ↔ Kotlin `Double`
 *   - `TEXT`     ↔ Kotlin `String` / `String?`
 *   - nullable SQLite columns ↔ Kotlin nullable types
 */

// ---------------------------------------------------------------------------------------
// lexeme
// ---------------------------------------------------------------------------------------
@Entity(tableName = "lexeme")
data class LexemeEntity(
    @PrimaryKey val lexemeId: Long,
    val lemma: String,
    val pos: String,
    val gender: String?,
    val englishGloss: String,
    val frequencyRank: Int,
    val cefrBand: String,
    val difficultyPrior: Double,
    // provenance (C5 / §4.6)
    val source: String,
    val sourceId: String,
    val license: String,
    val vettingStatus: String,
    val reviewedBy: String?,
    val reviewedAt: Long?,
)

// ---------------------------------------------------------------------------------------
// sentence
// ---------------------------------------------------------------------------------------
@Entity(tableName = "sentence")
data class SentenceEntity(
    @PrimaryKey val sentenceId: Long,
    val spanishText: String,
    val englishText: String,
    // provenance (C5 / §4.6)
    val source: String,
    val sourceId: String,
    val license: String,
    val vettingStatus: String,
    val reviewedBy: String?,
    val reviewedAt: Long?,
)

// ---------------------------------------------------------------------------------------
// sentence_fts — FTS4 external-content index over `sentence` (SPEC §10.1).
//
// `@Fts4(contentEntity = SentenceEntity::class)` makes Room declare the virtual table as
//   CREATE VIRTUAL TABLE sentence_fts USING fts4(spanishText, englishText, content="sentence")
// which is exactly the DDL the pipeline writes. Room owns the implicit `rowid` for FTS
// tables — do NOT add a @PrimaryKey here (a conflicting PK would change the generated
// schema and break asset validation). The pipeline back-fills the index with
// rowid = sentenceId so MATCH queries can map hits back to `sentence` rows.
// ---------------------------------------------------------------------------------------
@Fts4(contentEntity = SentenceEntity::class)
@Entity(tableName = "sentence_fts")
data class SentenceFts(
    val spanishText: String,
    val englishText: String,
)

// ---------------------------------------------------------------------------------------
// accepted_answer
// ---------------------------------------------------------------------------------------
@Entity(tableName = "accepted_answer")
data class AcceptedAnswerEntity(
    @PrimaryKey val acceptedAnswerId: Long,
    val sentenceId: Long,
    val direction: String,
    val answerText: String,
    // provenance (C5 / §4.6)
    val source: String,
    val sourceId: String,
    val license: String,
    val vettingStatus: String,
    val reviewedBy: String?,
    val reviewedAt: Long?,
)

// ---------------------------------------------------------------------------------------
// sentence_lexeme — many-to-many join (composite PK)
// ---------------------------------------------------------------------------------------
@Entity(tableName = "sentence_lexeme", primaryKeys = ["sentenceId", "lexemeId"])
data class SentenceLexemeEntity(
    val sentenceId: Long,
    val lexemeId: Long,
)

// ---------------------------------------------------------------------------------------
// conjugation_lemma_map — surface form → lemma (hot grading-path lookup, §12.4)
// ---------------------------------------------------------------------------------------
@Entity(tableName = "conjugation_lemma_map")
data class ConjugationLemmaMapEntity(
    @PrimaryKey val surfaceForm: String,
    val lemmaLexemeId: Long,
    val source: String,
    val license: String,
)

// ---------------------------------------------------------------------------------------
// node — a Path node (the unit a lesson is generated for; SPEC §10.1).
//
// Structural/curriculum row (no provenance columns — it carries no licensed text). Mirrors
// the pipeline DDL `CREATE TABLE node (nodeId INTEGER PRIMARY KEY, title TEXT, displayOrder
// INTEGER)` exactly so `createFromAsset` schema validation passes.
// ---------------------------------------------------------------------------------------
@Entity(tableName = "node")
data class NodeEntity(
    @PrimaryKey val nodeId: Long,
    val title: String,
    val displayOrder: Int,
)

// ---------------------------------------------------------------------------------------
// content_attribution — content-level credits not owned by a single text row.
// ---------------------------------------------------------------------------------------
@Entity(tableName = "content_attribution", primaryKeys = ["source", "license"])
data class ContentAttributionEntity(
    val source: String,
    val license: String,
)

// ---------------------------------------------------------------------------------------
// exercise
// ---------------------------------------------------------------------------------------
@Entity(tableName = "exercise")
data class ExerciseEntity(
    @PrimaryKey val exerciseId: Long,
    val nodeId: Long,
    val sentenceId: Long,
    val type: String,
    val direction: String,
    val targetItemId: Long,
    val targetItemType: String,
    val promptHint: String?,
)

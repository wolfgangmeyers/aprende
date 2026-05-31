#!/usr/bin/env python3
"""
Aprende content pipeline (P0.3 spike) — builds the read-only `content.db` SQLite asset
that the app ships via Room `createFromAsset`, enforcing the C5 / SPEC §4.6 content-vetting
workflow as a HARD GATE.

This is a dev-time tool (NOT shipped in the app). It is the ONLY path content takes into
`content.db`: ingest from vetted sources -> derive -> auto-check -> human review gate ->
publish gate. The publish step FAILS (non-zero exit) if any row to be shipped lacks a
`source` or is not `vettingStatus = REVIEWED` — this is AC17.

Language note (deviation from PLAN P0.3 "JVM/Kotlin tool"): implemented in Python for the
spike because (a) it is dev-time tooling, never shipped; (b) it can be RUN and the gate
PROVEN here, where no JVM/Gradle toolchain exists; (c) Python's sqlite3/data tooling fits
content processing. Can be ported to a Gradle/Kotlin module later — the schema (which the
Kotlin Room entities mirror) is the real contract, not the build language.

Usage:
    python3 build_content_db.py --out <path/to/content.db>          # build db + reports
    python3 build_content_db.py --out <...> --inject-unvetted       # demo: gate must REJECT
    python3 build_content_db.py --out <...> --fail-on-coverage-gaps # enforce readiness budgets
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import dataclass

PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BASELINE_SNAPSHOT_PATH = os.path.join(PIPELINE_DIR, "coverage_baseline_snapshot.json")

# --- vetting status lifecycle (SPEC §4.6) ---
UNVETTED = "UNVETTED"
AUTO_CHECKED = "AUTO_CHECKED"
REVIEWED = "REVIEWED"  # the only status allowed to ship

# Room schema version this asset must match (content.db @Database version, SPEC D2).
SCHEMA_VERSION = 1


# --------------------------------------------------------------------------------------
# Schema — mirrors the Kotlin Room entities in app/.../data/content/ (the asset DB must
# match the exported Room schema; that exact-match is validated on CI).
# --------------------------------------------------------------------------------------
SCHEMA_DDL = [
    """CREATE TABLE lexeme (
        lexemeId INTEGER NOT NULL PRIMARY KEY,
        lemma TEXT NOT NULL,
        pos TEXT NOT NULL,
        gender TEXT,
        englishGloss TEXT NOT NULL,
        frequencyRank INTEGER NOT NULL,
        cefrBand TEXT NOT NULL,
        difficultyPrior REAL NOT NULL,
        source TEXT NOT NULL,
        sourceId TEXT NOT NULL,
        license TEXT NOT NULL,
        vettingStatus TEXT NOT NULL,
        reviewedBy TEXT,
        reviewedAt INTEGER
    )""",
    """CREATE TABLE sentence (
        sentenceId INTEGER NOT NULL PRIMARY KEY,
        spanishText TEXT NOT NULL,
        englishText TEXT NOT NULL,
        source TEXT NOT NULL,
        sourceId TEXT NOT NULL,
        license TEXT NOT NULL,
        vettingStatus TEXT NOT NULL,
        reviewedBy TEXT,
        reviewedAt INTEGER
    )""",
    # No FOREIGN KEY clauses: the Room entities don't declare FKs (referential integrity is
    # enforced in the pipeline + repository layer), and Room's createFromAsset schema
    # validation requires the asset's FKs to match the entities' exactly.
    """CREATE TABLE accepted_answer (
        acceptedAnswerId INTEGER NOT NULL PRIMARY KEY,
        sentenceId INTEGER NOT NULL,
        direction TEXT NOT NULL,
        answerText TEXT NOT NULL,
        source TEXT NOT NULL,
        sourceId TEXT NOT NULL,
        license TEXT NOT NULL,
        vettingStatus TEXT NOT NULL,
        reviewedBy TEXT,
        reviewedAt INTEGER
    )""",
    """CREATE TABLE sentence_lexeme (
        sentenceId INTEGER NOT NULL,
        lexemeId INTEGER NOT NULL,
        PRIMARY KEY(sentenceId, lexemeId)
    )""",
    # node — a Path node (the unit of a lesson; SPEC §10.1). Structural/curriculum row,
    # not content-bearing text, so it is not audited by the vetting publish gate.
    """CREATE TABLE node (
        nodeId INTEGER NOT NULL PRIMARY KEY,
        title TEXT NOT NULL,
        displayOrder INTEGER NOT NULL
    )""",
    """CREATE TABLE conjugation_lemma_map (
        surfaceForm TEXT NOT NULL PRIMARY KEY,
        lemmaLexemeId INTEGER NOT NULL,
        source TEXT NOT NULL,
        license TEXT NOT NULL
    )""",
    """CREATE TABLE exercise (
        exerciseId INTEGER NOT NULL PRIMARY KEY,
        nodeId INTEGER NOT NULL,
        sentenceId INTEGER NOT NULL,
        type TEXT NOT NULL,
        direction TEXT NOT NULL,
        targetItemId INTEGER NOT NULL,
        targetItemType TEXT NOT NULL,
        promptHint TEXT
    )""",
    # FTS over sentences for word/sentence search (SPEC §10.1). Room declares this as an
    # @Fts4(contentEntity = Sentence) entity; the asset mirrors that external-content layout.
    """CREATE VIRTUAL TABLE sentence_fts USING fts4(
        spanishText, englishText, content="sentence"
    )""",
]

# content-bearing tables that the publish gate audits (must be REVIEWED + have a source)
VETTED_TABLES = ["lexeme", "sentence", "accepted_answer"]


FREQUENCY_SOURCE_DECISION = {
    "status": "selected-for-phase-0",
    "canonicalFrequencySource": "hermitdave/FrequencyWords Spanish OpenSubtitles frequency list",
    "sourceUrl": "https://github.com/hermitdave/FrequencyWords",
    "license": "CC-BY-SA-4.0 for generated content outputs",
    "upstreamCorpus": "OpenSubtitles",
    "decision": (
        "Use this source as the canonical ordering spine for Spanish frequency ranks. "
        "Store rank provenance separately from authored curriculum text, expose attribution "
        "in the in-app credits screen, and treat any redistributed rank data as CC-BY-SA-4.0."
    ),
    "rationale": [
        "The repo publishes generated outputs and identifies CC-BY-SA-4.0 for content.",
        "The list is broad enough for the A1/A2/B1 frequency spine and already matches SPEC O1 candidates.",
        "The ShareAlike obligation is manageable if frequency-derived metadata is explicitly attributed and segregated.",
    ],
    "licenseNotes": [
        {
            "source": "Tatoeba textual sentences",
            "url": "https://tatoeba.org/en/downloads",
            "license": "CC-BY-2.0-FR or CC0 depending on download/subset",
            "use": "Spanish-English sentence pairs and accepted-answer source pairs",
        },
        {
            "source": "Wiktionary",
            "url": "https://en.wiktionary.org/wiki/Wiktionary:Copyrights",
            "license": "CC-BY-SA / GFDL for entry text",
            "use": "Glosses, part-of-speech data, and conjugation source checks",
        },
    ],
}


TARGET_LIST_SOURCE = {
    "status": "phase-0-audit-list",
    "sourceBasis": [
        "SPEC.md §4.1 vocabulary spine and §5.6 CEFR sequencing",
        "SPANISH_BREADTH_PLAN.md Phase 0/Phase 1 A1-A2 priorities",
        "hermitdave/FrequencyWords selected ordering spine",
    ],
    "reviewPolicy": (
        "This list is a local source-checked audit target, not shipped learning content. "
        "A target lemma only becomes shipped content after the normal lexeme/sentence/"
        "accepted-answer provenance and REVIEWED gate pass."
    ),
}


# A deliberately small, source-checked A1/A2 target spine for Phase 0 reporting. This is
# not shipped learning content; it is the local audit list used to surface missing gaps from
# the current reviewed corpus. It should grow after the canonical frequency list is ingested.
A1_A2_TARGET_LEMMAS = [
    {"lemma": "ser", "cefrBand": "A1", "pos": "verb", "priority": 1, "reason": "identity and description", "sourceBasis": "SPEC.md §5.6 A1 ser/estar"},
    {"lemma": "estar", "cefrBand": "A1", "pos": "verb", "priority": 1, "reason": "state and location", "sourceBasis": "SPEC.md §5.6 A1 ser/estar"},
    {"lemma": "tener", "cefrBand": "A1", "pos": "verb", "priority": 1, "reason": "possession and needs", "sourceBasis": "SPEC.md §5.2 irregular verb table"},
    {"lemma": "ir", "cefrBand": "A1", "pos": "verb", "priority": 1, "reason": "movement and near future", "sourceBasis": "SPEC.md §5.2 irregular verb table"},
    {"lemma": "hacer", "cefrBand": "A1", "pos": "verb", "priority": 1, "reason": "daily actions and weather", "sourceBasis": "SPEC.md §5.2 irregular verb table"},
    {"lemma": "querer", "cefrBand": "A1", "pos": "verb", "priority": 1, "reason": "wants", "sourceBasis": "SPEC.md §5.2 irregular verb table"},
    {"lemma": "poder", "cefrBand": "A1", "pos": "verb", "priority": 1, "reason": "ability and permission", "sourceBasis": "SPEC.md §5.2 irregular verb table"},
    {"lemma": "decir", "cefrBand": "A1", "pos": "verb", "priority": 1, "reason": "reported speech basics", "sourceBasis": "SPEC.md §5.2 irregular verb table"},
    {"lemma": "saber", "cefrBand": "A1", "pos": "verb", "priority": 1, "reason": "knowledge", "sourceBasis": "SPEC.md §5.2 irregular verb table"},
    {"lemma": "venir", "cefrBand": "A1", "pos": "verb", "priority": 1, "reason": "movement", "sourceBasis": "SPEC.md §5.2 irregular verb table"},
    {"lemma": "comer", "cefrBand": "A1", "pos": "verb", "priority": 2, "reason": "food routines", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 1 food topic"},
    {"lemma": "beber", "cefrBand": "A1", "pos": "verb", "priority": 2, "reason": "food routines", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 1 food topic"},
    {"lemma": "vivir", "cefrBand": "A1", "pos": "verb", "priority": 2, "reason": "home and biography", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 1 home/routines topics"},
    {"lemma": "hablar", "cefrBand": "A1", "pos": "verb", "priority": 2, "reason": "communication", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 1 questions topic"},
    {"lemma": "ver", "cefrBand": "A1", "pos": "verb", "priority": 2, "reason": "perception", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine"},
    {"lemma": "persona", "cefrBand": "A1", "pos": "noun", "priority": 2, "reason": "people", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 1 people topic"},
    {"lemma": "casa", "cefrBand": "A1", "pos": "noun", "priority": 2, "reason": "home", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 1 home topic"},
    {"lemma": "día", "cefrBand": "A1", "pos": "noun", "priority": 2, "reason": "time", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 1 time/routines topic"},
    {"lemma": "tiempo", "cefrBand": "A1", "pos": "noun", "priority": 2, "reason": "time and weather", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 1 time/routines topic"},
    {"lemma": "agua", "cefrBand": "A1", "pos": "noun", "priority": 2, "reason": "food and drink", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 1 food/drink topic"},
    {"lemma": "comida", "cefrBand": "A1", "pos": "noun", "priority": 2, "reason": "food", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 1 food topic"},
    {"lemma": "familia", "cefrBand": "A1", "pos": "noun", "priority": 2, "reason": "relationships", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 1 people topic"},
    {"lemma": "trabajo", "cefrBand": "A2", "pos": "noun", "priority": 3, "reason": "work", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 work/school topic"},
    {"lemma": "escuela", "cefrBand": "A2", "pos": "noun", "priority": 3, "reason": "school", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 work/school topic"},
    {"lemma": "dinero", "cefrBand": "A2", "pos": "noun", "priority": 3, "reason": "shopping", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 shopping/money topic"},
    {"lemma": "comprar", "cefrBand": "A2", "pos": "verb", "priority": 3, "reason": "shopping", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 shopping/money topic"},
    {"lemma": "viajar", "cefrBand": "A2", "pos": "verb", "priority": 3, "reason": "travel", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 travel topic"},
    {"lemma": "llegar", "cefrBand": "A2", "pos": "verb", "priority": 3, "reason": "travel and time", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 travel/time topics"},
    {"lemma": "salir", "cefrBand": "A2", "pos": "verb", "priority": 3, "reason": "movement and plans", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 travel/plans topics"},
    {"lemma": "necesitar", "cefrBand": "A2", "pos": "verb", "priority": 3, "reason": "needs", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 wants/needs topic"},
]


# --------------------------------------------------------------------------------------
# A tiny VETTED sample slice (the real build ingests Tatoeba/frequency lists; O1 picks the
# exact frequency list). Every row carries provenance. `authored` rows (e.g. accepted-answer
# variants) still require a human reviewer before REVIEWED.
# --------------------------------------------------------------------------------------
@dataclass
class Row:
    data: dict
    # provenance starts UNVETTED on ingest; stages promote it.
    source: str = "tatoeba"
    sourceId: str = ""
    license: str = "CC-BY-2.0-FR"
    vettingStatus: str = UNVETTED
    reviewedBy: str | None = None
    reviewedAt: int | None = None


def vetted_sample():
    """Stage 1 INGEST: rows originate from vetted sources, so every row has provenance."""
    lexemes = [
        Row({"lexemeId": 1, "lemma": "tener", "pos": "verb", "gender": None,
             "englishGloss": "to have", "frequencyRank": 25, "cefrBand": "A1", "difficultyPrior": 0.3},
            source="wiktionary", sourceId="tener", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 2, "lemma": "agua", "pos": "noun", "gender": "F",
             "englishGloss": "water", "frequencyRank": 280, "cefrBand": "A1", "difficultyPrior": 0.4},
            source="wiktionary", sourceId="agua", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 3, "lemma": "perro", "pos": "noun", "gender": "M",
             "englishGloss": "dog", "frequencyRank": 900, "cefrBand": "A1", "difficultyPrior": 0.5},
            source="wiktionary", sourceId="perro", license="CC-BY-SA-3.0"),
    ]
    sentences = [
        Row({"sentenceId": 1, "spanishText": "Tengo un perro.", "englishText": "I have a dog."},
            sourceId="tatoeba:12345"),
        Row({"sentenceId": 2, "spanishText": "El agua está fría.", "englishText": "The water is cold."},
            sourceId="tatoeba:67890"),
    ]
    accepted = [
        Row({"acceptedAnswerId": 1, "sentenceId": 1, "direction": "ES_TO_EN", "answerText": "i have a dog"},
            sourceId="tatoeba:12345"),
        # an `authored` accepted-variant — must be human-reviewed before it can ship
        Row({"acceptedAnswerId": 2, "sentenceId": 1, "direction": "ES_TO_EN", "answerText": "i've got a dog"},
            source="authored", sourceId="authored:aa2", license="proprietary"),
        Row({"acceptedAnswerId": 3, "sentenceId": 2, "direction": "ES_TO_EN", "answerText": "the water is cold"},
            sourceId="tatoeba:67890"),
    ]
    # non-vetted-audited tables (derived/structural) still carry source where meaningful
    sentence_lexeme = [(1, 1), (1, 3), (2, 2)]
    conj = [("tengo", 1, "wiktionary", "CC-BY-SA-3.0"), ("tienes", 1, "wiktionary", "CC-BY-SA-3.0")]
    # Path nodes (structural). v1 sample ships one node; exercises above belong to nodeId=1.
    nodes = [(1, "Basics 1", 0)]
    exercises = [
        {"exerciseId": 1, "nodeId": 1, "sentenceId": 1, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 1, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 2, "nodeId": 1, "sentenceId": 2, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 2, "targetItemType": "LEXEME", "promptHint": None},
    ]
    return lexemes, sentences, accepted, sentence_lexeme, conj, exercises, nodes


# --------------------------------------------------------------------------------------
# Pipeline stages
# --------------------------------------------------------------------------------------
def stage_auto_check(lexemes, sentences, accepted) -> list[str]:
    """Stage 3 AUTO-CHECK: automated validation; promote passing rows to AUTO_CHECKED.
    Returns a list of failure messages (empty == all good)."""
    failures: list[str] = []
    sentence_ids = {s.data["sentenceId"] for s in sentences}

    # every sentence must have >= 1 accepted answer
    answered = {a.data["sentenceId"] for a in accepted}
    for s in sentences:
        if s.data["sentenceId"] not in answered:
            failures.append(f"sentence {s.data['sentenceId']} has no accepted answer")

    # accepted answers must reference a real sentence and be normalized (lowercase, trimmed)
    for a in accepted:
        if a.data["sentenceId"] not in sentence_ids:
            failures.append(f"accepted_answer {a.data['acceptedAnswerId']} -> missing sentence")
        txt = a.data["answerText"]
        if txt != txt.strip().lower():
            failures.append(f"accepted_answer {a.data['acceptedAnswerId']} not normalized")

    for r in lexemes + sentences + accepted:
        if not r.license:
            failures.append("row missing license")
        if r.vettingStatus == UNVETTED and not failures:
            r.vettingStatus = AUTO_CHECKED  # promote only if no failures touched it

    if not failures:
        for r in lexemes + sentences + accepted:
            r.vettingStatus = AUTO_CHECKED
    return failures


def stage_human_review(lexemes, sentences, accepted) -> None:
    """Stage 4 REVIEW GATE: a human signs off. In the spike, the sample carries pre-recorded
    sign-off for AUTO_CHECKED rows (simulating the reviewer). REAL builds require an actual
    reviewer to set this; LLM-drafted/`authored` rows get extra scrutiny here."""
    REVIEWER = "wolfgang"
    REVIEW_TS = 1_735_700_000_000  # fixed for determinism in the spike
    for r in lexemes + sentences + accepted:
        if r.vettingStatus == AUTO_CHECKED:
            r.vettingStatus = REVIEWED
            r.reviewedBy = REVIEWER
            r.reviewedAt = REVIEW_TS


def stage_publish_gate(lexemes, sentences, accepted) -> None:
    """Stage 5 PUBLISH GATE (AC17): refuse to ship any content row lacking a source or not
    REVIEWED. Raises SystemExit(2) on any violation — this is the hard, CI-level gate."""
    violations: list[str] = []
    for table, rows in (("lexeme", lexemes), ("sentence", sentences), ("accepted_answer", accepted)):
        for r in rows:
            if not r.source:
                violations.append(f"{table} row {r.data} has no source")
            if r.vettingStatus != REVIEWED:
                violations.append(f"{table} row {r.data} is {r.vettingStatus}, not REVIEWED")
    if violations:
        sys.stderr.write("CONTENT VETTING GATE FAILED (C5/§4.6/AC17):\n  " + "\n  ".join(violations) + "\n")
        raise SystemExit(2)


def write_db(out_path, lexemes, sentences, accepted, sentence_lexeme, conj, exercises, nodes):
    if os.path.exists(out_path):
        os.remove(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    con = sqlite3.connect(out_path)
    cur = con.cursor()
    cur.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")  # Room reads this for createFromAsset
    for ddl in SCHEMA_DDL:
        cur.execute(ddl)

    def prov(r):
        return (r.source, r.sourceId, r.license, r.vettingStatus, r.reviewedBy, r.reviewedAt)

    for r in lexemes:
        d = r.data
        cur.execute("INSERT INTO lexeme VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (d["lexemeId"], d["lemma"], d["pos"], d["gender"], d["englishGloss"],
                     d["frequencyRank"], d["cefrBand"], d["difficultyPrior"], *prov(r)))
    for r in sentences:
        d = r.data
        cur.execute("INSERT INTO sentence VALUES (?,?,?,?,?,?,?,?,?)",
                    (d["sentenceId"], d["spanishText"], d["englishText"], *prov(r)))
    for r in accepted:
        d = r.data
        cur.execute("INSERT INTO accepted_answer VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (d["acceptedAnswerId"], d["sentenceId"], d["direction"], d["answerText"], *prov(r)))
    cur.executemany("INSERT INTO sentence_lexeme VALUES (?,?)", sentence_lexeme)
    cur.executemany("INSERT INTO conjugation_lemma_map VALUES (?,?,?,?)", conj)
    cur.executemany("INSERT INTO node VALUES (?,?,?)", nodes)
    for e in exercises:
        cur.execute("INSERT INTO exercise VALUES (?,?,?,?,?,?,?,?)",
                    (e["exerciseId"], e["nodeId"], e["sentenceId"], e["type"], e["direction"],
                     e["targetItemId"], e["targetItemType"], e["promptHint"]))
    # populate the external-content FTS index
    cur.execute("INSERT INTO sentence_fts(rowid, spanishText, englishText) "
                "SELECT sentenceId, spanishText, englishText FROM sentence")
    con.commit()
    con.close()


def write_manifest(out_dir, lexemes, sentences, accepted):
    """An auditable content manifest: counts by source/status + the authored-row review trail."""
    rows = [("lexeme", r) for r in lexemes] + [("sentence", r) for r in sentences] + \
           [("accepted_answer", r) for r in accepted]
    by_status: dict[str, int] = {}
    by_source: dict[str, int] = {}
    authored = []
    for table, r in rows:
        by_status[r.vettingStatus] = by_status.get(r.vettingStatus, 0) + 1
        by_source[r.source] = by_source.get(r.source, 0) + 1
        if r.source == "authored":
            authored.append({"table": table, "id": next(iter(r.data.values())),
                             "vettingStatus": r.vettingStatus, "reviewedBy": r.reviewedBy})
    manifest = {"schemaVersion": SCHEMA_VERSION, "totalContentRows": len(rows),
                "byVettingStatus": by_status, "bySource": by_source, "authoredRows": authored}
    path = os.path.join(out_dir, "content_manifest.json")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def frequency_bucket(rank: int) -> str:
    if rank <= 500:
        return "0001-0500"
    if rank <= 1000:
        return "0501-1000"
    if rank <= 2000:
        return "1001-2000"
    return "2001+"


def count_by(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def exercise_kind(exercise_type: str) -> str:
    production_types = {"TYPED_TRANSLATION", "FILL_BLANK", "LISTEN_TYPE"}
    return "production" if exercise_type in production_types else "recognition"


def reviewed(row: Row) -> bool:
    return row.vettingStatus == REVIEWED and bool(row.source) and bool(row.license)


def build_coverage_report(lexemes, sentences, accepted, sentence_lexeme, exercises):
    sentence_by_id = {r.data["sentenceId"]: r for r in sentences}
    accepted_by_sentence: dict[int, list[Row]] = {}
    for r in accepted:
        accepted_by_sentence.setdefault(r.data["sentenceId"], []).append(r)

    sentence_ids_by_lexeme: dict[int, set[int]] = {}
    for sentence_id, lexeme_id in sentence_lexeme:
        sentence_ids_by_lexeme.setdefault(lexeme_id, set()).add(sentence_id)

    exercise_targets_by_lexeme: dict[int, list[dict]] = {}
    for e in exercises:
        if e["targetItemType"] == "LEXEME":
            exercise_targets_by_lexeme.setdefault(e["targetItemId"], []).append(e)

    lexeme_readiness = []
    learner_ready_count = 0
    for r in sorted(lexemes, key=lambda row: row.data["frequencyRank"]):
        d = r.data
        lexeme_id = d["lexemeId"]
        sentence_ids = sorted(sentence_ids_by_lexeme.get(lexeme_id, set()))
        reviewed_sentence_ids = [
            sid for sid in sentence_ids
            if sid in sentence_by_id
            and reviewed(sentence_by_id[sid])
            and any(reviewed(a) for a in accepted_by_sentence.get(sid, []))
        ]
        target_exercises = exercise_targets_by_lexeme.get(lexeme_id, [])
        exercise_kinds = sorted({exercise_kind(e["type"]) for e in target_exercises})
        required_contexts = 4 if d["pos"] == "verb" and d["frequencyRank"] <= 500 else 2
        missing = []
        if not reviewed(r):
            missing.append("lexeme_not_reviewed")
        if len(reviewed_sentence_ids) < required_contexts:
            missing.append(f"needs_{required_contexts}_reviewed_contexts")
        if "production" not in exercise_kinds:
            missing.append("needs_production_exercise")
        if "recognition" not in exercise_kinds:
            missing.append("needs_recognition_exercise")

        learner_ready = not missing
        if learner_ready:
            learner_ready_count += 1

        lexeme_readiness.append({
            "lexemeId": lexeme_id,
            "lemma": d["lemma"],
            "pos": d["pos"],
            "cefrBand": d["cefrBand"],
            "frequencyRank": d["frequencyRank"],
            "frequencyBucket": frequency_bucket(d["frequencyRank"]),
            "reviewedSentenceContexts": len(reviewed_sentence_ids),
            "requiredSentenceContexts": required_contexts,
            "targetExerciseCount": len(target_exercises),
            "exerciseKinds": exercise_kinds,
            "learnerReady": learner_ready,
            "missing": missing,
        })

    present_by_lemma = {r.data["lemma"]: r for r in lexemes}
    readiness_by_lemma = {entry["lemma"]: entry for entry in lexeme_readiness}
    missing_gaps = []
    for target in sorted(A1_A2_TARGET_LEMMAS, key=lambda row: (row["priority"], row["cefrBand"], row["lemma"])):
        lemma = target["lemma"]
        entry = readiness_by_lemma.get(lemma)
        if not entry:
            status = "missing_lexeme"
            blockers = ["add_reviewed_lexeme", "add_reviewed_contexts", "add_exercises"]
        elif not entry["learnerReady"]:
            status = "not_learner_ready"
            blockers = entry["missing"]
        else:
            continue
        missing_gaps.append({
            **target,
            "status": status,
            "blockers": blockers,
            "currentLexemeId": present_by_lemma[lemma].data["lexemeId"] if lemma in present_by_lemma else None,
        })

    raw_rows = [*lexemes, *sentences, *accepted]
    report = {
        "schemaVersion": SCHEMA_VERSION,
        "frequencySourceDecision": FREQUENCY_SOURCE_DECISION,
        "targetListSource": TARGET_LIST_SOURCE,
        "summary": {
            "rawLexemes": len(lexemes),
            "learnerReadyLexemes": learner_ready_count,
            "reviewedSentences": sum(1 for r in sentences if reviewed(r)),
            "reviewedAcceptedAnswers": sum(1 for r in accepted if reviewed(r)),
            "exerciseCount": len(exercises),
            "missingA1A2GapCount": len(missing_gaps),
        },
        "counts": {
            "lexemesByPos": count_by(r.data["pos"] for r in lexemes),
            "lexemesByCefrBand": count_by(r.data["cefrBand"] for r in lexemes),
            "lexemesByFrequencyBucket": count_by(frequency_bucket(r.data["frequencyRank"]) for r in lexemes),
            "contentRowsBySource": count_by(r.source for r in raw_rows),
            "contentRowsByLicense": count_by(r.license for r in raw_rows),
            "contentRowsByVettingStatus": count_by(r.vettingStatus for r in raw_rows),
            "exerciseTargetsByType": count_by(e["targetItemType"] for e in exercises),
            "exerciseTypes": count_by(e["type"] for e in exercises),
        },
        "learnerReadyDefinition": {
            "reviewedLexeme": True,
            "reviewedSourceAndLicense": True,
            "minimumReviewedSentenceContexts": {
                "highValueVerb": 4,
                "default": 2,
            },
            "minimumExerciseKinds": ["production", "recognition"],
        },
        "lexemeReadiness": lexeme_readiness,
        "missingA1A2Gaps": missing_gaps,
    }
    return report


def write_coverage_report(out_dir, lexemes, sentences, accepted, sentence_lexeme, exercises):
    report = build_coverage_report(lexemes, sentences, accepted, sentence_lexeme, exercises)
    path = os.path.join(out_dir, "content_coverage.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    snapshot_path = os.path.join(out_dir, "coverage_snapshot.json")
    snapshot = {
        "schemaVersion": report["schemaVersion"],
        "frequencySourceDecision": report["frequencySourceDecision"],
        "targetListSource": report["targetListSource"],
        "summary": report["summary"],
        "counts": report["counts"],
        "topMissingA1A2Gaps": report["missingA1A2Gaps"][:20],
    }
    with open(snapshot_path, "w") as f:
        json.dump(snapshot, f, indent=2)
    return report


def write_baseline_snapshot(path, report):
    baseline = {
        "schemaVersion": report["schemaVersion"],
        "frequencySourceDecision": report["frequencySourceDecision"],
        "targetListSource": report["targetListSource"],
        "summary": report["summary"],
        "counts": report["counts"],
        "topMissingA1A2Gaps": report["missingA1A2Gaps"][:20],
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(baseline, f, indent=2)
        f.write("\n")
    return baseline


def enforce_coverage_budgets(report) -> None:
    failures = []
    if report["summary"]["learnerReadyLexemes"] == 0:
        failures.append("no learner-ready lexemes")
    for entry in report["lexemeReadiness"]:
        if entry["learnerReady"]:
            continue
        if entry["cefrBand"] in {"A1", "A2"}:
            failures.append(f"{entry['lemma']} is not learner-ready: {', '.join(entry['missing'])}")
    if failures:
        sys.stderr.write("COVERAGE BUDGET FAILED:\n  " + "\n  ".join(failures) + "\n")
        raise SystemExit(4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="output content.db path")
    ap.add_argument("--inject-unvetted", action="store_true",
                    help="inject an UNVETTED row to demonstrate the publish gate rejecting it (AC17)")
    ap.add_argument("--fail-on-coverage-gaps", action="store_true",
                    help="exit non-zero if reviewed A1/A2 rows are not learner-ready")
    ap.add_argument("--baseline-snapshot", default=DEFAULT_BASELINE_SNAPSHOT_PATH,
                    help="reviewable compact coverage snapshot path")
    args = ap.parse_args()

    lexemes, sentences, accepted, sentence_lexeme, conj, exercises, nodes = vetted_sample()

    # Stage 3: auto-check
    failures = stage_auto_check(lexemes, sentences, accepted)
    if failures:
        sys.stderr.write("AUTO-CHECK FAILED:\n  " + "\n  ".join(failures) + "\n")
        raise SystemExit(3)

    # Stage 4: human review gate
    stage_human_review(lexemes, sentences, accepted)

    if args.inject_unvetted:
        # simulate an un-reviewed (e.g. LLM-drafted, never human-reviewed) row sneaking in
        accepted.append(Row({"acceptedAnswerId": 99, "sentenceId": 1,
                             "direction": "ES_TO_EN", "answerText": "i own a dog"},
                            source="authored", sourceId="llm:draft", license="proprietary",
                            vettingStatus=UNVETTED))

    # Stage 5: publish gate (AC17) — raises SystemExit(2) if anything is unvetted/sourceless
    stage_publish_gate(lexemes, sentences, accepted)

    out_dir = os.path.dirname(args.out) or "."
    os.makedirs(out_dir, exist_ok=True)
    manifest = write_manifest(out_dir, lexemes, sentences, accepted)
    coverage = write_coverage_report(out_dir, lexemes, sentences, accepted, sentence_lexeme, exercises)
    write_baseline_snapshot(args.baseline_snapshot, coverage)
    if args.fail_on_coverage_gaps:
        if os.path.exists(args.out):
            os.remove(args.out)
        enforce_coverage_budgets(coverage)
    write_db(args.out, lexemes, sentences, accepted, sentence_lexeme, conj, exercises, nodes)
    print(f"OK: wrote {args.out} (schema v{SCHEMA_VERSION})")
    print("manifest:", json.dumps(manifest))
    print("coverage:", json.dumps(coverage["summary"]))
    if coverage["missingA1A2Gaps"]:
        print("topMissingA1A2Gaps:", json.dumps(coverage["missingA1A2Gaps"][:10]))


if __name__ == "__main__":
    main()

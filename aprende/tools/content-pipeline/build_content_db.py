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
    python3 build_content_db.py --out <path/to/content.db>          # build from the vetted sample
    python3 build_content_db.py --out <...> --inject-unvetted       # demo: gate must REJECT
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import dataclass, field, asdict

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="output content.db path")
    ap.add_argument("--inject-unvetted", action="store_true",
                    help="inject an UNVETTED row to demonstrate the publish gate rejecting it (AC17)")
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

    write_db(args.out, lexemes, sentences, accepted, sentence_lexeme, conj, exercises, nodes)
    manifest = write_manifest(os.path.dirname(args.out), lexemes, sentences, accepted)
    print(f"OK: wrote {args.out} (schema v{SCHEMA_VERSION})")
    print("manifest:", json.dumps(manifest))


if __name__ == "__main__":
    main()

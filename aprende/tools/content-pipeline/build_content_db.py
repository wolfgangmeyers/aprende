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
        Row({"lexemeId": 4, "lemma": "ser", "pos": "verb", "gender": None,
             "englishGloss": "to be", "frequencyRank": 63, "cefrBand": "A1", "difficultyPrior": 0.3},
            source="wiktionary", sourceId="ser", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 5, "lemma": "estar", "pos": "verb", "gender": None,
             "englishGloss": "to be", "frequencyRank": 131, "cefrBand": "A1", "difficultyPrior": 0.3},
            source="wiktionary", sourceId="estar", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 6, "lemma": "ir", "pos": "verb", "gender": None,
             "englishGloss": "to go", "frequencyRank": 128, "cefrBand": "A1", "difficultyPrior": 0.3},
            source="wiktionary", sourceId="ir", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 7, "lemma": "querer", "pos": "verb", "gender": None,
             "englishGloss": "to want", "frequencyRank": 1557, "cefrBand": "A1", "difficultyPrior": 0.6},
            source="wiktionary", sourceId="querer", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 8, "lemma": "poder", "pos": "verb", "gender": None,
             "englishGloss": "to be able to", "frequencyRank": 362, "cefrBand": "A1", "difficultyPrior": 0.4},
            source="wiktionary", sourceId="poder", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 9, "lemma": "saber", "pos": "verb", "gender": None,
             "englishGloss": "to know", "frequencyRank": 236, "cefrBand": "A1", "difficultyPrior": 0.4},
            source="wiktionary", sourceId="saber", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 10, "lemma": "venir", "pos": "verb", "gender": None,
             "englishGloss": "to come", "frequencyRank": 339, "cefrBand": "A1", "difficultyPrior": 0.4},
            source="wiktionary", sourceId="venir", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 11, "lemma": "hacer", "pos": "verb", "gender": None,
             "englishGloss": "to do; to make", "frequencyRank": 68, "cefrBand": "A1", "difficultyPrior": 0.3},
            source="wiktionary", sourceId="hacer", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 12, "lemma": "decir", "pos": "verb", "gender": None,
             "englishGloss": "to say; to tell", "frequencyRank": 111, "cefrBand": "A1", "difficultyPrior": 0.3},
            source="wiktionary", sourceId="decir", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 13, "lemma": "casa", "pos": "noun", "gender": "F",
             "englishGloss": "house; home", "frequencyRank": 91, "cefrBand": "A1", "difficultyPrior": 0.3},
            source="wiktionary", sourceId="casa", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 14, "lemma": "comida", "pos": "noun", "gender": "F",
             "englishGloss": "food; meal", "frequencyRank": 483, "cefrBand": "A1", "difficultyPrior": 0.4},
            source="wiktionary", sourceId="comida", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 15, "lemma": "comer", "pos": "verb", "gender": None,
             "englishGloss": "to eat", "frequencyRank": 488, "cefrBand": "A1", "difficultyPrior": 0.4},
            source="wiktionary", sourceId="comer", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 16, "lemma": "beber", "pos": "verb", "gender": None,
             "englishGloss": "to drink", "frequencyRank": 1053, "cefrBand": "A1", "difficultyPrior": 0.5},
            source="wiktionary", sourceId="beber", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 17, "lemma": "familia", "pos": "noun", "gender": "F",
             "englishGloss": "family", "frequencyRank": 254, "cefrBand": "A1", "difficultyPrior": 0.3},
            source="wiktionary", sourceId="familia", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 18, "lemma": "día", "pos": "noun", "gender": "M",
             "englishGloss": "day", "frequencyRank": 134, "cefrBand": "A1", "difficultyPrior": 0.3},
            source="wiktionary", sourceId="día", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 19, "lemma": "hablar", "pos": "verb", "gender": None,
             "englishGloss": "to speak; to talk", "frequencyRank": 154, "cefrBand": "A1", "difficultyPrior": 0.3},
            source="wiktionary", sourceId="hablar", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 20, "lemma": "persona", "pos": "noun", "gender": "F",
             "englishGloss": "person", "frequencyRank": 310, "cefrBand": "A1", "difficultyPrior": 0.3},
            source="wiktionary", sourceId="persona", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 21, "lemma": "tiempo", "pos": "noun", "gender": "M",
             "englishGloss": "time; weather", "frequencyRank": 95, "cefrBand": "A1", "difficultyPrior": 0.3},
            source="wiktionary", sourceId="tiempo", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 22, "lemma": "ver", "pos": "verb", "gender": None,
             "englishGloss": "to see", "frequencyRank": 120, "cefrBand": "A1", "difficultyPrior": 0.3},
            source="wiktionary", sourceId="ver", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 23, "lemma": "vivir", "pos": "verb", "gender": None,
             "englishGloss": "to live", "frequencyRank": 454, "cefrBand": "A1", "difficultyPrior": 0.4},
            source="wiktionary", sourceId="vivir", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 24, "lemma": "comprar", "pos": "verb", "gender": None,
             "englishGloss": "to buy", "frequencyRank": 818, "cefrBand": "A2", "difficultyPrior": 0.5},
            source="wiktionary", sourceId="comprar", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 25, "lemma": "dinero", "pos": "noun", "gender": "M",
             "englishGloss": "money", "frequencyRank": 164, "cefrBand": "A2", "difficultyPrior": 0.3},
            source="wiktionary", sourceId="dinero", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 26, "lemma": "escuela", "pos": "noun", "gender": "F",
             "englishGloss": "school", "frequencyRank": 463, "cefrBand": "A2", "difficultyPrior": 0.4},
            source="wiktionary", sourceId="escuela", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 27, "lemma": "llegar", "pos": "verb", "gender": None,
             "englishGloss": "to arrive", "frequencyRank": 400, "cefrBand": "A2", "difficultyPrior": 0.4},
            source="wiktionary", sourceId="llegar", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 28, "lemma": "necesitar", "pos": "verb", "gender": None,
             "englishGloss": "to need", "frequencyRank": 1692, "cefrBand": "A2", "difficultyPrior": 0.6},
            source="wiktionary", sourceId="necesitar", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 29, "lemma": "salir", "pos": "verb", "gender": None,
             "englishGloss": "to leave; to go out", "frequencyRank": 265, "cefrBand": "A2", "difficultyPrior": 0.4},
            source="wiktionary", sourceId="salir", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 30, "lemma": "trabajo", "pos": "noun", "gender": "M",
             "englishGloss": "work; job", "frequencyRank": 142, "cefrBand": "A2", "difficultyPrior": 0.3},
            source="wiktionary", sourceId="trabajo", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 31, "lemma": "viajar", "pos": "verb", "gender": None,
             "englishGloss": "to travel", "frequencyRank": 2530, "cefrBand": "A2", "difficultyPrior": 0.6},
            source="wiktionary", sourceId="viajar", license="CC-BY-SA-3.0"),
    ]
    sentences = [
        Row({"sentenceId": 1, "spanishText": "Tengo un perro.", "englishText": "I have a dog."},
            sourceId="tatoeba:755342"),
        Row({"sentenceId": 2, "spanishText": "El agua está fría.", "englishText": "The water is cold."},
            sourceId="tatoeba:1987699"),
        Row({"sentenceId": 3, "spanishText": "¿Tienes un perro?", "englishText": "Do you have a dog?"},
            sourceId="tatoeba:1195274"),
        Row({"sentenceId": 4, "spanishText": "Tiene un perro.", "englishText": "He has a dog."},
            sourceId="tatoeba:5051233"),
        Row({"sentenceId": 5, "spanishText": "Tengo el agua.", "englishText": "I have the water."},
            sourceId="tatoeba:3515639"),
        Row({"sentenceId": 6, "spanishText": "Soy estudiante.", "englishText": "I'm a student."},
            sourceId="tatoeba:574254"),
        Row({"sentenceId": 7, "spanishText": "Eres mi amigo.", "englishText": "You are my friend."},
            sourceId="tatoeba:585066"),
        Row({"sentenceId": 8, "spanishText": "Esta es mi casa.", "englishText": "This is my house."},
            sourceId="tatoeba:955676"),
        Row({"sentenceId": 9, "spanishText": "Soy feliz.", "englishText": "I'm happy."},
            sourceId="tatoeba:627075"),
        Row({"sentenceId": 10, "spanishText": "Estoy en casa.", "englishText": "I'm at home."},
            sourceId="tatoeba:1013884"),
        Row({"sentenceId": 11, "spanishText": "Ella está en casa.", "englishText": "She is at home."},
            sourceId="tatoeba:4848556"),
        Row({"sentenceId": 12, "spanishText": "Estoy bien.", "englishText": "I'm fine."},
            sourceId="tatoeba:455952"),
        Row({"sentenceId": 13, "spanishText": "Está aquí.", "englishText": "It's here."},
            sourceId="tatoeba:2532719"),
        Row({"sentenceId": 14, "spanishText": "Vamos a casa.", "englishText": "We're going home."},
            sourceId="tatoeba:748478"),
        Row({"sentenceId": 15, "spanishText": "Voy contigo.", "englishText": "I am going with you."},
            sourceId="tatoeba:1050137"),
        Row({"sentenceId": 16, "spanishText": "Voy al parque.", "englishText": "I go to the park."},
            sourceId="tatoeba:450251"),
        Row({"sentenceId": 17, "spanishText": "Voy a la escuela.", "englishText": "I go to school."},
            sourceId="tatoeba:473450"),
        Row({"sentenceId": 18, "spanishText": "Quiero agua.", "englishText": "I want water."},
            sourceId="tatoeba:584596"),
        Row({"sentenceId": 19, "spanishText": "¿Quieres agua?", "englishText": "Do you want water?"},
            sourceId="tatoeba:12291005"),
        Row({"sentenceId": 20, "spanishText": "Puedo ir.", "englishText": "I can go."},
            sourceId="tatoeba:4521968"),
        Row({"sentenceId": 21, "spanishText": "Puedo hacerlo.", "englishText": "I can do it."},
            sourceId="tatoeba:1686297"),
        Row({"sentenceId": 22, "spanishText": "Puedo venir.", "englishText": "I can come."},
            sourceId="tatoeba:10128973"),
        Row({"sentenceId": 23, "spanishText": "Podemos ir.", "englishText": "We can go."},
            sourceId="tatoeba:6811033"),
        Row({"sentenceId": 24, "spanishText": "Lo sé.", "englishText": "I know."},
            sourceId="tatoeba:435153"),
        Row({"sentenceId": 25, "spanishText": "No sé.", "englishText": "I don't know."},
            sourceId="tatoeba:376608"),
        Row({"sentenceId": 26, "spanishText": "Quiero saberlo.", "englishText": "I want to know."},
            sourceId="tatoeba:961279"),
        Row({"sentenceId": 27, "spanishText": "Sabemos.", "englishText": "We know."},
            sourceId="tatoeba:5265434"),
        Row({"sentenceId": 28, "spanishText": "Ven aquí.", "englishText": "Come here."},
            sourceId="tatoeba:374136"),
        Row({"sentenceId": 29, "spanishText": "¿Vienes?", "englishText": "Are you coming?"},
            sourceId="tatoeba:2194085"),
        Row({"sentenceId": 30, "spanishText": "Vienen.", "englishText": "They're coming."},
            sourceId="tatoeba:2008142"),
        Row({"sentenceId": 31, "spanishText": "Ven a casa.", "englishText": "Come home."},
            sourceId="tatoeba:3873833"),
        Row({"sentenceId": 32, "spanishText": "¿Qué haces?", "englishText": "What are you doing?"},
            sourceId="tatoeba:4052592"),
        Row({"sentenceId": 33, "spanishText": "Puedo hacerlo.", "englishText": "I can do it."},
            sourceId="tatoeba:1686297"),
        Row({"sentenceId": 34, "spanishText": "Hace frío.", "englishText": "It's cold."},
            sourceId="tatoeba:2926"),
        Row({"sentenceId": 35, "spanishText": "Hace calor.", "englishText": "It's hot."},
            sourceId="tatoeba:456142"),
        Row({"sentenceId": 36, "spanishText": "Dime.", "englishText": "Tell me."},
            sourceId="tatoeba:5044120"),
        Row({"sentenceId": 37, "spanishText": "Dime todo.", "englishText": "Tell me everything."},
            sourceId="tatoeba:1216387"),
        Row({"sentenceId": 38, "spanishText": "¿Qué dices?", "englishText": "What do you say?"},
            sourceId="tatoeba:941802"),
        Row({"sentenceId": 39, "spanishText": "Dígame la verdad.", "englishText": "Tell me the truth."},
            sourceId="tatoeba:571886"),
        Row({"sentenceId": 40, "spanishText": "La comida está buena.", "englishText": "The food is good."},
            sourceId="tatoeba:2002676"),
        Row({"sentenceId": 41, "spanishText": "No tengo comida.", "englishText": "I have no food."},
            sourceId="tatoeba:3600572"),
        Row({"sentenceId": 42, "spanishText": "Come.", "englishText": "He eats."},
            sourceId="tatoeba:6702001"),
        Row({"sentenceId": 43, "spanishText": "Comemos.", "englishText": "We eat."},
            sourceId="tatoeba:6702002"),
        Row({"sentenceId": 44, "spanishText": "Comen.", "englishText": "They eat."},
            sourceId="tatoeba:6702004"),
        Row({"sentenceId": 45, "spanishText": "¿Quieres comer?", "englishText": "Do you want to eat?"},
            sourceId="tatoeba:1493376"),
        Row({"sentenceId": 46, "spanishText": "Bebo agua.", "englishText": "I drink water."},
            sourceId="tatoeba:5745781"),
        Row({"sentenceId": 47, "spanishText": "Bebemos agua.", "englishText": "We drink water."},
            sourceId="tatoeba:4386719"),
        Row({"sentenceId": 48, "spanishText": "Bebes agua.", "englishText": "You drink water."},
            sourceId="tatoeba:10496384"),
        Row({"sentenceId": 49, "spanishText": "Bebe agua.", "englishText": "He drinks water."},
            sourceId="tatoeba:7562545"),
        Row({"sentenceId": 50, "spanishText": "Son familia.", "englishText": "They're family."},
            sourceId="tatoeba:6600079"),
        Row({"sentenceId": 51, "spanishText": "¿Tienes familia?", "englishText": "Do you have a family?"},
            sourceId="tatoeba:730296"),
        Row({"sentenceId": 52, "spanishText": "¡Buen día!", "englishText": "Good day!"},
            sourceId="tatoeba:855394"),
        Row({"sentenceId": 53, "spanishText": "Buenos días.", "englishText": "Good morning."},
            sourceId="tatoeba:2258235"),
        Row({"sentenceId": 54, "spanishText": "Hablo español.", "englishText": "I speak Spanish."},
            sourceId="tatoeba:2011085"),
        Row({"sentenceId": 55, "spanishText": "¿Hablas español?", "englishText": "Do you speak Spanish?"},
            sourceId="tatoeba:1550980"),
        Row({"sentenceId": 56, "spanishText": "Todos hablamos español.", "englishText": "We all speak Spanish."},
            sourceId="tatoeba:6003088"),
        Row({"sentenceId": 57, "spanishText": "¿Cuántas personas?", "englishText": "How many people?"},
            sourceId="tatoeba:3582800"),
        Row({"sentenceId": 58, "spanishText": "Somos personas.", "englishText": "We are people."},
            sourceId="tatoeba:1408294"),
        Row({"sentenceId": 59, "spanishText": "Eres buena persona.", "englishText": "You're a good person."},
            sourceId="tatoeba:4958553"),
        Row({"sentenceId": 60, "spanishText": "Hace buen tiempo.", "englishText": "The weather is good."},
            sourceId="tatoeba:1215730"),
        Row({"sentenceId": 61, "spanishText": "Tengo tiempo.", "englishText": "I have time."},
            sourceId="tatoeba:4859590"),
        Row({"sentenceId": 62, "spanishText": "Necesitamos tiempo.", "englishText": "We need time."},
            sourceId="tatoeba:9706925"),
        Row({"sentenceId": 63, "spanishText": "Veo algo.", "englishText": "I see something."},
            sourceId="tatoeba:9706879"),
        Row({"sentenceId": 64, "spanishText": "Veo esto.", "englishText": "I see this."},
            sourceId="tatoeba:1732156"),
        Row({"sentenceId": 65, "spanishText": "Quiero ver tu casa.", "englishText": "I want to see your house."},
            sourceId="tatoeba:9884000"),
        Row({"sentenceId": 66, "spanishText": "¿Puedes ver?", "englishText": "Can you see?"},
            sourceId="tatoeba:1748229"),
        Row({"sentenceId": 67, "spanishText": "Vivo cerca.", "englishText": "I live nearby."},
            sourceId="tatoeba:11160801"),
        Row({"sentenceId": 68, "spanishText": "Vive aquí.", "englishText": "He lives here."},
            sourceId="tatoeba:11035294"),
        Row({"sentenceId": 69, "spanishText": "Vivimos aquí.", "englishText": "We live here."},
            sourceId="tatoeba:6694248"),
        Row({"sentenceId": 70, "spanishText": "¿Viven aquí?", "englishText": "Do you live here?"},
            sourceId="tatoeba:894294"),
        Row({"sentenceId": 71, "spanishText": "También hablo español.", "englishText": "I also speak Spanish."},
            sourceId="tatoeba:10480474"),
        Row({"sentenceId": 72, "spanishText": "Compramos.", "englishText": "We buy."},
            sourceId="tatoeba:7947364"),
        Row({"sentenceId": 73, "spanishText": "¡Compra!", "englishText": "Buy!"},
            sourceId="tatoeba:7936806"),
        Row({"sentenceId": 74, "spanishText": "Compraré comida.", "englishText": "I'll buy food."},
            sourceId="tatoeba:13917468"),
        Row({"sentenceId": 75, "spanishText": "Quiero comprar comida.", "englishText": "I want to buy food."},
            sourceId="tatoeba:2707615"),
        Row({"sentenceId": 76, "spanishText": "Tenemos dinero.", "englishText": "We have money."},
            sourceId="tatoeba:9943356"),
        Row({"sentenceId": 77, "spanishText": "Tienes dinero.", "englishText": "You have money."},
            sourceId="tatoeba:7931127"),
        Row({"sentenceId": 78, "spanishText": "Quiero dinero.", "englishText": "I want money."},
            sourceId="tatoeba:4456338"),
        Row({"sentenceId": 79, "spanishText": "Esta es mi escuela.", "englishText": "This is my school."},
            sourceId="tatoeba:1258453"),
        Row({"sentenceId": 80, "spanishText": "Odio la escuela.", "englishText": "I hate school."},
            sourceId="tatoeba:9443867"),
        Row({"sentenceId": 81, "spanishText": "Voy a la escuela.", "englishText": "I go to school."},
            sourceId="tatoeba:473450"),
        Row({"sentenceId": 82, "spanishText": "Llegaré.", "englishText": "I will arrive."},
            sourceId="tatoeba:9763982"),
        Row({"sentenceId": 83, "spanishText": "Llegué.", "englishText": "I've arrived."},
            sourceId="tatoeba:6161281"),
        Row({"sentenceId": 84, "spanishText": "Llegamos.", "englishText": "We've arrived."},
            sourceId="tatoeba:6063763"),
        Row({"sentenceId": 85, "spanishText": "Llegó.", "englishText": "She arrived."},
            sourceId="tatoeba:6063762"),
        Row({"sentenceId": 86, "spanishText": "Necesito miel.", "englishText": "I need honey."},
            sourceId="tatoeba:13665656"),
        Row({"sentenceId": 87, "spanishText": "Necesita practicar.", "englishText": "He needs to practice."},
            sourceId="tatoeba:13660778"),
        Row({"sentenceId": 88, "spanishText": "¿Necesitas descansar?", "englishText": "Do you need to rest?"},
            sourceId="tatoeba:13711743"),
        Row({"sentenceId": 89, "spanishText": "Necesitamos expertos.", "englishText": "We need experts."},
            sourceId="tatoeba:13789665"),
        Row({"sentenceId": 90, "spanishText": "Salgo.", "englishText": "I'm leaving."},
            sourceId="tatoeba:10262252"),
        Row({"sentenceId": 91, "spanishText": "Salgamos.", "englishText": "Let's go out."},
            sourceId="tatoeba:2008990"),
        Row({"sentenceId": 92, "spanishText": "Nunca salgo.", "englishText": "I never go out."},
            sourceId="tatoeba:7160137"),
        Row({"sentenceId": 93, "spanishText": "Salí.", "englishText": "I left."},
            sourceId="tatoeba:630772"),
        Row({"sentenceId": 94, "spanishText": "Odio mi trabajo.", "englishText": "I hate my job."},
            sourceId="tatoeba:858287"),
        Row({"sentenceId": 95, "spanishText": "Es mi trabajo.", "englishText": "It's my job."},
            sourceId="tatoeba:1306030"),
        Row({"sentenceId": 96, "spanishText": "Mi trabajo es seguro.", "englishText": "My job is safe."},
            sourceId="tatoeba:11405515"),
        Row({"sentenceId": 97, "spanishText": "Viajé.", "englishText": "I traveled."},
            sourceId="tatoeba:5028966"),
        Row({"sentenceId": 98, "spanishText": "¿Viajas mucho?", "englishText": "Do you travel a lot?"},
            sourceId="tatoeba:10459407"),
        Row({"sentenceId": 99, "spanishText": "Viajé a Boston.", "englishText": "I traveled to Boston."},
            sourceId="tatoeba:5752610"),
        Row({"sentenceId": 100, "spanishText": "Viajo a menudo.", "englishText": "I travel often."},
            sourceId="tatoeba:995130"),
    ]
    accepted = [
        Row({"acceptedAnswerId": 1, "sentenceId": 1, "direction": "ES_TO_EN", "answerText": "i have a dog"},
            sourceId="tatoeba:378502"),
        # an `authored` accepted-variant — must be human-reviewed before it can ship
        Row({"acceptedAnswerId": 2, "sentenceId": 1, "direction": "ES_TO_EN", "answerText": "i've got a dog"},
            source="authored", sourceId="authored:aa2", license="proprietary"),
        Row({"acceptedAnswerId": 3, "sentenceId": 2, "direction": "ES_TO_EN", "answerText": "the water's cold"},
            sourceId="tatoeba:3422364"),
        Row({"acceptedAnswerId": 8, "sentenceId": 2, "direction": "ES_TO_EN", "answerText": "the water is cold"},
            source="authored", sourceId="authored:aa8", license="proprietary"),
        Row({"acceptedAnswerId": 4, "sentenceId": 3, "direction": "ES_TO_EN", "answerText": "do you have a dog"},
            sourceId="tatoeba:1195261"),
        Row({"acceptedAnswerId": 5, "sentenceId": 4, "direction": "ES_TO_EN", "answerText": "he has a dog"},
            sourceId="tatoeba:288121"),
        Row({"acceptedAnswerId": 6, "sentenceId": 4, "direction": "ES_TO_EN", "answerText": "she has a dog"},
            sourceId="tatoeba:7425744"),
        Row({"acceptedAnswerId": 7, "sentenceId": 5, "direction": "ES_TO_EN", "answerText": "i have the water"},
            sourceId="tatoeba:12068868"),
        Row({"acceptedAnswerId": 9, "sentenceId": 6, "direction": "ES_TO_EN", "answerText": "i'm a student"},
            sourceId="tatoeba:567368"),
        Row({"acceptedAnswerId": 10, "sentenceId": 7, "direction": "ES_TO_EN", "answerText": "you are my friend"},
            sourceId="tatoeba:370562"),
        Row({"acceptedAnswerId": 11, "sentenceId": 8, "direction": "ES_TO_EN", "answerText": "this is my house"},
            sourceId="tatoeba:955157"),
        Row({"acceptedAnswerId": 12, "sentenceId": 9, "direction": "ES_TO_EN", "answerText": "i'm happy"},
            sourceId="tatoeba:1872056"),
        Row({"acceptedAnswerId": 13, "sentenceId": 10, "direction": "ES_TO_EN", "answerText": "i'm at home"},
            sourceId="tatoeba:404046"),
        Row({"acceptedAnswerId": 14, "sentenceId": 11, "direction": "ES_TO_EN", "answerText": "she is at home"},
            sourceId="tatoeba:4848413"),
        Row({"acceptedAnswerId": 15, "sentenceId": 12, "direction": "ES_TO_EN", "answerText": "i'm fine"},
            sourceId="tatoeba:257272"),
        Row({"acceptedAnswerId": 16, "sentenceId": 13, "direction": "ES_TO_EN", "answerText": "it's here"},
            sourceId="tatoeba:2123598"),
        Row({"acceptedAnswerId": 17, "sentenceId": 14, "direction": "ES_TO_EN", "answerText": "we're going home"},
            sourceId="tatoeba:430024"),
        Row({"acceptedAnswerId": 18, "sentenceId": 15, "direction": "ES_TO_EN", "answerText": "i am going with you"},
            sourceId="tatoeba:894729"),
        Row({"acceptedAnswerId": 19, "sentenceId": 16, "direction": "ES_TO_EN", "answerText": "i go to the park"},
            sourceId="tatoeba:257353"),
        Row({"acceptedAnswerId": 20, "sentenceId": 17, "direction": "ES_TO_EN", "answerText": "i go to school"},
            sourceId="tatoeba:472089"),
        Row({"acceptedAnswerId": 21, "sentenceId": 18, "direction": "ES_TO_EN", "answerText": "i want water"},
            sourceId="tatoeba:5085314"),
        Row({"acceptedAnswerId": 22, "sentenceId": 19, "direction": "ES_TO_EN", "answerText": "do you want water"},
            sourceId="tatoeba:13225760"),
        Row({"acceptedAnswerId": 23, "sentenceId": 20, "direction": "ES_TO_EN", "answerText": "i can go"},
            sourceId="tatoeba:3092548"),
        Row({"acceptedAnswerId": 24, "sentenceId": 21, "direction": "ES_TO_EN", "answerText": "i can do it"},
            sourceId="tatoeba:254742"),
        Row({"acceptedAnswerId": 25, "sentenceId": 22, "direction": "ES_TO_EN", "answerText": "i can come"},
            sourceId="tatoeba:2245638"),
        Row({"acceptedAnswerId": 26, "sentenceId": 23, "direction": "ES_TO_EN", "answerText": "we can go"},
            sourceId="tatoeba:2241036"),
        Row({"acceptedAnswerId": 27, "sentenceId": 24, "direction": "ES_TO_EN", "answerText": "i know"},
            sourceId="tatoeba:319990"),
        Row({"acceptedAnswerId": 28, "sentenceId": 25, "direction": "ES_TO_EN", "answerText": "i don't know"},
            sourceId="tatoeba:349064"),
        Row({"acceptedAnswerId": 29, "sentenceId": 26, "direction": "ES_TO_EN", "answerText": "i want to know"},
            sourceId="tatoeba:961147"),
        Row({"acceptedAnswerId": 30, "sentenceId": 27, "direction": "ES_TO_EN", "answerText": "we know"},
            sourceId="tatoeba:1556167"),
        Row({"acceptedAnswerId": 31, "sentenceId": 28, "direction": "ES_TO_EN", "answerText": "come here"},
            sourceId="tatoeba:39944"),
        Row({"acceptedAnswerId": 32, "sentenceId": 29, "direction": "ES_TO_EN", "answerText": "are you coming"},
            sourceId="tatoeba:1417464"),
        Row({"acceptedAnswerId": 33, "sentenceId": 30, "direction": "ES_TO_EN", "answerText": "they're coming"},
            sourceId="tatoeba:1898128"),
        Row({"acceptedAnswerId": 34, "sentenceId": 31, "direction": "ES_TO_EN", "answerText": "come home"},
            sourceId="tatoeba:413767"),
        Row({"acceptedAnswerId": 35, "sentenceId": 32, "direction": "ES_TO_EN", "answerText": "what are you doing"},
            sourceId="tatoeba:16492"),
        Row({"acceptedAnswerId": 36, "sentenceId": 33, "direction": "ES_TO_EN", "answerText": "i can do it"},
            sourceId="tatoeba:254742"),
        Row({"acceptedAnswerId": 37, "sentenceId": 34, "direction": "ES_TO_EN", "answerText": "it's cold"},
            sourceId="tatoeba:1813"),
        Row({"acceptedAnswerId": 38, "sentenceId": 35, "direction": "ES_TO_EN", "answerText": "it's hot"},
            sourceId="tatoeba:423405"),
        Row({"acceptedAnswerId": 39, "sentenceId": 36, "direction": "ES_TO_EN", "answerText": "tell me"},
            sourceId="tatoeba:1913090"),
        Row({"acceptedAnswerId": 40, "sentenceId": 37, "direction": "ES_TO_EN", "answerText": "tell me everything"},
            sourceId="tatoeba:1216330"),
        Row({"acceptedAnswerId": 41, "sentenceId": 38, "direction": "ES_TO_EN", "answerText": "what do you say"},
            sourceId="tatoeba:1174872"),
        Row({"acceptedAnswerId": 42, "sentenceId": 39, "direction": "ES_TO_EN", "answerText": "tell me the truth"},
            sourceId="tatoeba:321441"),
        Row({"acceptedAnswerId": 43, "sentenceId": 40, "direction": "ES_TO_EN", "answerText": "the food is good"},
            sourceId="tatoeba:2002528"),
        Row({"acceptedAnswerId": 44, "sentenceId": 41, "direction": "ES_TO_EN", "answerText": "i have no food"},
            sourceId="tatoeba:2549665"),
        Row({"acceptedAnswerId": 45, "sentenceId": 42, "direction": "ES_TO_EN", "answerText": "he eats"},
            sourceId="tatoeba:6702018"),
        Row({"acceptedAnswerId": 46, "sentenceId": 43, "direction": "ES_TO_EN", "answerText": "we eat"},
            sourceId="tatoeba:3845194"),
        Row({"acceptedAnswerId": 47, "sentenceId": 44, "direction": "ES_TO_EN", "answerText": "they eat"},
            sourceId="tatoeba:3845203"),
        Row({"acceptedAnswerId": 48, "sentenceId": 45, "direction": "ES_TO_EN", "answerText": "do you want to eat"},
            sourceId="tatoeba:773323"),
        Row({"acceptedAnswerId": 49, "sentenceId": 46, "direction": "ES_TO_EN", "answerText": "i drink water"},
            sourceId="tatoeba:7932256"),
        Row({"acceptedAnswerId": 50, "sentenceId": 47, "direction": "ES_TO_EN", "answerText": "we drink water"},
            sourceId="tatoeba:4385215"),
        Row({"acceptedAnswerId": 51, "sentenceId": 48, "direction": "ES_TO_EN", "answerText": "you drink water"},
            sourceId="tatoeba:7189457"),
        Row({"acceptedAnswerId": 52, "sentenceId": 49, "direction": "ES_TO_EN", "answerText": "he drinks water"},
            sourceId="tatoeba:4870686"),
        Row({"acceptedAnswerId": 53, "sentenceId": 50, "direction": "ES_TO_EN", "answerText": "they're family"},
            sourceId="tatoeba:2242977"),
        Row({"acceptedAnswerId": 54, "sentenceId": 51, "direction": "ES_TO_EN", "answerText": "do you have a family"},
            sourceId="tatoeba:54499"),
        Row({"acceptedAnswerId": 55, "sentenceId": 52, "direction": "ES_TO_EN", "answerText": "good day"},
            sourceId="tatoeba:855284"),
        Row({"acceptedAnswerId": 56, "sentenceId": 53, "direction": "ES_TO_EN", "answerText": "good morning"},
            sourceId="tatoeba:2258234"),
        Row({"acceptedAnswerId": 57, "sentenceId": 54, "direction": "ES_TO_EN", "answerText": "i speak spanish"},
            sourceId="tatoeba:1755331"),
        Row({"acceptedAnswerId": 58, "sentenceId": 55, "direction": "ES_TO_EN", "answerText": "do you speak spanish"},
            sourceId="tatoeba:719306"),
        Row({"acceptedAnswerId": 59, "sentenceId": 56, "direction": "ES_TO_EN", "answerText": "we all speak spanish"},
            sourceId="tatoeba:6003093"),
        Row({"acceptedAnswerId": 60, "sentenceId": 57, "direction": "ES_TO_EN", "answerText": "how many people"},
            sourceId="tatoeba:24515"),
        Row({"acceptedAnswerId": 61, "sentenceId": 58, "direction": "ES_TO_EN", "answerText": "we are people"},
            sourceId="tatoeba:671753"),
        Row({"acceptedAnswerId": 62, "sentenceId": 59, "direction": "ES_TO_EN", "answerText": "you're a good person"},
            sourceId="tatoeba:2547447"),
        Row({"acceptedAnswerId": 63, "sentenceId": 60, "direction": "ES_TO_EN", "answerText": "the weather is good"},
            sourceId="tatoeba:1766700"),
        Row({"acceptedAnswerId": 64, "sentenceId": 61, "direction": "ES_TO_EN", "answerText": "i have time"},
            sourceId="tatoeba:2245901"),
        Row({"acceptedAnswerId": 65, "sentenceId": 62, "direction": "ES_TO_EN", "answerText": "we need time"},
            sourceId="tatoeba:2241424"),
        Row({"acceptedAnswerId": 66, "sentenceId": 63, "direction": "ES_TO_EN", "answerText": "i see something"},
            sourceId="tatoeba:2247403"),
        Row({"acceptedAnswerId": 67, "sentenceId": 64, "direction": "ES_TO_EN", "answerText": "i see this"},
            sourceId="tatoeba:871792"),
        Row({"acceptedAnswerId": 68, "sentenceId": 65, "direction": "ES_TO_EN", "answerText": "i want to see your house"},
            sourceId="tatoeba:2396149"),
        Row({"acceptedAnswerId": 69, "sentenceId": 66, "direction": "ES_TO_EN", "answerText": "can you see"},
            sourceId="tatoeba:1553530"),
        Row({"acceptedAnswerId": 70, "sentenceId": 67, "direction": "ES_TO_EN", "answerText": "i live nearby"},
            sourceId="tatoeba:3565068"),
        Row({"acceptedAnswerId": 71, "sentenceId": 68, "direction": "ES_TO_EN", "answerText": "he lives here"},
            sourceId="tatoeba:5143986"),
        Row({"acceptedAnswerId": 72, "sentenceId": 69, "direction": "ES_TO_EN", "answerText": "we live here"},
            sourceId="tatoeba:2549740"),
        Row({"acceptedAnswerId": 73, "sentenceId": 70, "direction": "ES_TO_EN", "answerText": "do you live here"},
            sourceId="tatoeba:15882"),
        Row({"acceptedAnswerId": 74, "sentenceId": 71, "direction": "ES_TO_EN", "answerText": "i also speak spanish"},
            sourceId="tatoeba:10573599"),
        Row({"acceptedAnswerId": 75, "sentenceId": 72, "direction": "ES_TO_EN", "answerText": "we buy"},
            sourceId="tatoeba:5617573"),
        Row({"acceptedAnswerId": 76, "sentenceId": 73, "direction": "ES_TO_EN", "answerText": "buy"},
            sourceId="tatoeba:6046859"),
        Row({"acceptedAnswerId": 77, "sentenceId": 74, "direction": "ES_TO_EN", "answerText": "i'll buy food"},
            sourceId="tatoeba:8918033"),
        Row({"acceptedAnswerId": 78, "sentenceId": 75, "direction": "ES_TO_EN", "answerText": "i want to buy food"},
            sourceId="tatoeba:2669111"),
        Row({"acceptedAnswerId": 79, "sentenceId": 76, "direction": "ES_TO_EN", "answerText": "we have money"},
            sourceId="tatoeba:9943118"),
        Row({"acceptedAnswerId": 80, "sentenceId": 77, "direction": "ES_TO_EN", "answerText": "you have money"},
            sourceId="tatoeba:9311597"),
        Row({"acceptedAnswerId": 81, "sentenceId": 78, "direction": "ES_TO_EN", "answerText": "i want money"},
            sourceId="tatoeba:64620"),
        Row({"acceptedAnswerId": 82, "sentenceId": 79, "direction": "ES_TO_EN", "answerText": "this is my school"},
            sourceId="tatoeba:1255406"),
        Row({"acceptedAnswerId": 83, "sentenceId": 80, "direction": "ES_TO_EN", "answerText": "i hate school"},
            sourceId="tatoeba:4747564"),
        Row({"acceptedAnswerId": 84, "sentenceId": 81, "direction": "ES_TO_EN", "answerText": "i go to school"},
            sourceId="tatoeba:472089"),
        Row({"acceptedAnswerId": 85, "sentenceId": 82, "direction": "ES_TO_EN", "answerText": "i will arrive"},
            sourceId="tatoeba:12556195"),
        Row({"acceptedAnswerId": 86, "sentenceId": 83, "direction": "ES_TO_EN", "answerText": "i've arrived"},
            sourceId="tatoeba:4008734"),
        Row({"acceptedAnswerId": 87, "sentenceId": 84, "direction": "ES_TO_EN", "answerText": "we've arrived"},
            sourceId="tatoeba:410594"),
        Row({"acceptedAnswerId": 88, "sentenceId": 85, "direction": "ES_TO_EN", "answerText": "she arrived"},
            sourceId="tatoeba:6917619"),
        Row({"acceptedAnswerId": 89, "sentenceId": 86, "direction": "ES_TO_EN", "answerText": "i need honey"},
            sourceId="tatoeba:11900237"),
        Row({"acceptedAnswerId": 90, "sentenceId": 87, "direction": "ES_TO_EN", "answerText": "he needs to practice"},
            sourceId="tatoeba:9182157"),
        Row({"acceptedAnswerId": 91, "sentenceId": 88, "direction": "ES_TO_EN", "answerText": "do you need to rest"},
            sourceId="tatoeba:13711740"),
        Row({"acceptedAnswerId": 92, "sentenceId": 89, "direction": "ES_TO_EN", "answerText": "we need experts"},
            sourceId="tatoeba:2241414"),
        Row({"acceptedAnswerId": 93, "sentenceId": 90, "direction": "ES_TO_EN", "answerText": "i'm leaving"},
            sourceId="tatoeba:350133"),
        Row({"acceptedAnswerId": 94, "sentenceId": 91, "direction": "ES_TO_EN", "answerText": "let's go out"},
            sourceId="tatoeba:2007927"),
        Row({"acceptedAnswerId": 95, "sentenceId": 92, "direction": "ES_TO_EN", "answerText": "i never go out"},
            sourceId="tatoeba:3728879"),
        Row({"acceptedAnswerId": 96, "sentenceId": 93, "direction": "ES_TO_EN", "answerText": "i left"},
            sourceId="tatoeba:2307509"),
        Row({"acceptedAnswerId": 97, "sentenceId": 94, "direction": "ES_TO_EN", "answerText": "i hate my job"},
            sourceId="tatoeba:874052"),
        Row({"acceptedAnswerId": 98, "sentenceId": 95, "direction": "ES_TO_EN", "answerText": "it's my job"},
            sourceId="tatoeba:433521"),
        Row({"acceptedAnswerId": 99, "sentenceId": 96, "direction": "ES_TO_EN", "answerText": "my job is safe"},
            sourceId="tatoeba:3238932"),
        Row({"acceptedAnswerId": 100, "sentenceId": 97, "direction": "ES_TO_EN", "answerText": "i traveled"},
            sourceId="tatoeba:10954562"),
        Row({"acceptedAnswerId": 101, "sentenceId": 98, "direction": "ES_TO_EN", "answerText": "do you travel a lot"},
            sourceId="tatoeba:29911"),
        Row({"acceptedAnswerId": 102, "sentenceId": 99, "direction": "ES_TO_EN", "answerText": "i traveled to boston"},
            sourceId="tatoeba:2280316"),
        Row({"acceptedAnswerId": 103, "sentenceId": 100, "direction": "ES_TO_EN", "answerText": "i travel often"},
            sourceId="tatoeba:465459"),
    ]
    # non-vetted-audited tables (derived/structural) still carry source where meaningful
    sentence_lexeme = [
        (1, 1), (1, 3),
        (2, 2),
        (3, 1), (3, 3),
        (4, 1), (4, 3),
        (5, 1), (5, 2),
        (6, 4),
        (7, 4),
        (8, 4),
        (9, 4),
        (10, 5),
        (11, 5),
        (12, 5),
        (13, 5),
        (14, 6),
        (15, 6),
        (16, 6),
        (17, 6),
        (18, 7), (18, 2),
        (19, 7), (19, 2),
        (20, 8), (20, 6),
        (21, 8),
        (22, 8),
        (23, 8), (23, 6),
        (24, 9),
        (25, 9),
        (26, 9), (26, 7),
        (27, 9),
        (28, 10),
        (29, 10),
        (30, 10),
        (31, 10),
        (32, 11),
        (33, 11), (33, 8),
        (34, 11),
        (35, 11),
        (36, 12),
        (37, 12),
        (38, 12),
        (39, 12),
        (8, 13),
        (10, 13),
        (14, 13),
        (31, 13),
        (40, 14), (40, 5),
        (41, 14), (41, 1),
        (42, 15),
        (43, 15),
        (44, 15),
        (45, 15), (45, 7),
        (46, 16), (46, 2),
        (47, 16), (47, 2),
        (48, 16), (48, 2),
        (49, 16), (49, 2),
        (50, 17),
        (51, 17), (51, 1),
        (52, 18),
        (53, 18),
        (54, 19),
        (55, 19),
        (56, 19),
        (71, 19),
        (57, 20),
        (58, 20),
        (59, 20), (59, 4),
        (60, 21), (60, 11),
        (61, 21), (61, 1),
        (62, 21),
        (63, 22),
        (64, 22),
        (65, 22), (65, 7), (65, 13),
        (66, 22), (66, 8),
        (67, 23),
        (68, 23),
        (69, 23),
        (70, 23),
        (72, 24),
        (73, 24),
        (74, 24), (74, 14),
        (75, 24), (75, 7), (75, 14),
        (76, 25), (76, 1),
        (77, 25), (77, 1),
        (78, 25), (78, 7),
        (79, 26), (79, 4),
        (80, 26),
        (81, 26), (81, 6),
        (82, 27),
        (83, 27),
        (84, 27),
        (85, 27),
        (86, 28),
        (87, 28),
        (88, 28),
        (89, 28),
        (90, 29),
        (91, 29),
        (92, 29),
        (93, 29),
        (94, 30),
        (95, 30), (95, 4),
        (96, 30),
        (97, 31),
        (98, 31),
        (99, 31),
        (100, 31),
    ]
    conj = [("tengo", 1, "wiktionary", "CC-BY-SA-3.0"), ("tienes", 1, "wiktionary", "CC-BY-SA-3.0")]
    # Path nodes (structural). v1 sample ships one node; exercises above belong to nodeId=1.
    nodes = [(1, "Basics 1", 0)]
    exercises = [
        {"exerciseId": 1, "nodeId": 1, "sentenceId": 1, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 1, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 2, "nodeId": 1, "sentenceId": 2, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 2, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 3, "nodeId": 1, "sentenceId": 4, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 1, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 4, "nodeId": 1, "sentenceId": 5, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 2, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 5, "nodeId": 1, "sentenceId": 3, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 3, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 6, "nodeId": 1, "sentenceId": 4, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 3, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 7, "nodeId": 1, "sentenceId": 6, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 4, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 8, "nodeId": 1, "sentenceId": 8, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 4, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 9, "nodeId": 1, "sentenceId": 10, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 5, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 10, "nodeId": 1, "sentenceId": 13, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 5, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 11, "nodeId": 1, "sentenceId": 14, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 6, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 12, "nodeId": 1, "sentenceId": 16, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 6, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 13, "nodeId": 1, "sentenceId": 18, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 7, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 14, "nodeId": 1, "sentenceId": 19, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 7, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 15, "nodeId": 1, "sentenceId": 20, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 8, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 16, "nodeId": 1, "sentenceId": 23, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 8, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 17, "nodeId": 1, "sentenceId": 24, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 9, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 18, "nodeId": 1, "sentenceId": 27, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 9, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 19, "nodeId": 1, "sentenceId": 28, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 10, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 20, "nodeId": 1, "sentenceId": 30, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 10, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 21, "nodeId": 1, "sentenceId": 32, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 11, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 22, "nodeId": 1, "sentenceId": 34, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 11, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 23, "nodeId": 1, "sentenceId": 36, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 12, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 24, "nodeId": 1, "sentenceId": 38, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 12, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 25, "nodeId": 1, "sentenceId": 8, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 13, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 26, "nodeId": 1, "sentenceId": 10, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 13, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 27, "nodeId": 1, "sentenceId": 40, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 14, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 28, "nodeId": 1, "sentenceId": 41, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 14, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 29, "nodeId": 1, "sentenceId": 42, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 15, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 30, "nodeId": 1, "sentenceId": 45, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 15, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 31, "nodeId": 1, "sentenceId": 46, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 16, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 32, "nodeId": 1, "sentenceId": 48, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 16, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 33, "nodeId": 1, "sentenceId": 50, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 17, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 34, "nodeId": 1, "sentenceId": 51, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 17, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 35, "nodeId": 1, "sentenceId": 52, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 18, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 36, "nodeId": 1, "sentenceId": 53, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 18, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 37, "nodeId": 1, "sentenceId": 54, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 19, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 38, "nodeId": 1, "sentenceId": 55, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 19, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 39, "nodeId": 1, "sentenceId": 57, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 20, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 40, "nodeId": 1, "sentenceId": 59, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 20, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 41, "nodeId": 1, "sentenceId": 60, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 21, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 42, "nodeId": 1, "sentenceId": 61, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 21, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 43, "nodeId": 1, "sentenceId": 63, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 22, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 44, "nodeId": 1, "sentenceId": 66, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 22, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 45, "nodeId": 1, "sentenceId": 67, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 23, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 46, "nodeId": 1, "sentenceId": 70, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 23, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 47, "nodeId": 1, "sentenceId": 72, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 24, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 48, "nodeId": 1, "sentenceId": 75, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 24, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 49, "nodeId": 1, "sentenceId": 76, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 25, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 50, "nodeId": 1, "sentenceId": 78, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 25, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 51, "nodeId": 1, "sentenceId": 79, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 26, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 52, "nodeId": 1, "sentenceId": 81, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 26, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 53, "nodeId": 1, "sentenceId": 82, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 27, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 54, "nodeId": 1, "sentenceId": 84, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 27, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 55, "nodeId": 1, "sentenceId": 86, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 28, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 56, "nodeId": 1, "sentenceId": 88, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 28, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 57, "nodeId": 1, "sentenceId": 90, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 29, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 58, "nodeId": 1, "sentenceId": 92, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 29, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 59, "nodeId": 1, "sentenceId": 94, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 30, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 60, "nodeId": 1, "sentenceId": 96, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 30, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 61, "nodeId": 1, "sentenceId": 97, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 31, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 62, "nodeId": 1, "sentenceId": 100, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 31, "targetItemType": "LEXEME", "promptHint": None},
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

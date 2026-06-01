#!/usr/bin/env python3
"""
Aprende content pipeline (P0.3 spike) — builds the read-only `content.db` SQLite asset
that the app ships via Room `createFromAsset`, enforcing the C5 / SPEC §4.6 content-vetting
workflow as a HARD GATE.

This is a dev-time tool (NOT shipped in the app). It is the ONLY path content takes into
`content.db`: ingest from vetted sources or AI_DRAFT candidates -> derive -> auto-check ->
independent review gate -> publish gate. The publish step FAILS (non-zero exit) if any row
to be shipped lacks a `source` or is not `vettingStatus = REVIEWED` — this is AC17. AI_DRAFT
rows additionally require deterministic checks plus two independent automatic approvals.

Language note (deviation from PLAN P0.3 "JVM/Kotlin tool"): implemented in Python for the
spike because (a) it is dev-time tooling, never shipped; (b) it can be RUN and the gate
PROVEN here, where no JVM/Gradle toolchain exists; (c) Python's sqlite3/data tooling fits
content processing. Can be ported to a Gradle/Kotlin module later — the schema (which the
Kotlin Room entities mirror) is the real contract, not the build language.

Usage:
    python3 build_content_db.py --out <path/to/content.db>          # build db + reports
    python3 build_content_db.py --out <...> --inject-unvetted       # demo: gate must REJECT
    python3 build_content_db.py --out <...> --inject-malformed-exercise --fail-on-coverage-gaps
                                                                  # demo: coverage must REJECT
    python3 build_content_db.py --out <...> --fail-on-coverage-gaps # enforce readiness budgets
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import re
import sys
from dataclasses import dataclass, field

PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BASELINE_SNAPSHOT_PATH = os.path.join(PIPELINE_DIR, "coverage_baseline_snapshot.json")

# --- vetting status lifecycle (SPEC §4.6) ---
UNVETTED = "UNVETTED"
AI_DRAFT = "AI_DRAFT"
AUTO_CHECKED = "AUTO_CHECKED"
AUTO_REVIEWED = "AUTO_REVIEWED"
REVIEWED = "REVIEWED"  # the only status allowed to ship

# Room schema version this asset must match (content.db @Database version, SPEC D2).
SCHEMA_VERSION = 2
FREQUENCY_ATTRIBUTION = {
    "source": "frequencywords",
    "license": "CC-BY-SA-4.0",
}


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
    """CREATE TABLE content_attribution (
        source TEXT NOT NULL,
        license TEXT NOT NULL,
        PRIMARY KEY(source, license)
    )""",
    # FTS over sentences for word/sentence search (SPEC §10.1). Room declares this as an
    # @Fts4(contentEntity = Sentence) entity; the asset mirrors that external-content layout.
    """CREATE VIRTUAL TABLE sentence_fts USING fts4(
        spanishText, englishText, content="sentence"
    )""",
]

# content-bearing tables that the publish gate audits (must be REVIEWED + have a source)
VETTED_TABLES = ["lexeme", "sentence", "accepted_answer"]
AI_DRAFT_SOURCE = "ai_draft"
AUTO_REVIEW_SPANISH = "spanish_correctness_naturalness"
AUTO_REVIEW_PEDAGOGY = "english_pedagogy_cefr"
AUTO_REVIEW_REVIEWERS = {
    AUTO_REVIEW_SPANISH: "auto_review:spanish_v1",
    AUTO_REVIEW_PEDAGOGY: "auto_review:english_pedagogy_v1",
}
AUTO_REVIEW_TS = 1_735_700_000_000
AI_REVIEWED_SENTENCE_PAIRS = {
    "¿Tienes coche?": "Do you have a car?",
    "Quiero un coche.": "I want a car.",
    "Vayamos en autobús.": "Let's go by bus.",
    "Ella viajó en autobús.": "She traveled by bus.",
    "Odio esta tienda.": "I hate this store.",
    "Cerraron la tienda.": "They closed the shop.",
    "Mira el precio.": "Look at the price.",
    "El precio subió.": "The price rose.",
    "Lavémonos las manos.": "Let's wash our hands.",
    "Toma mi mano.": "Take my hand.",
    "¡Usa la cabeza!": "Use your head!",
    "Me duele la cabeza.": "My head hurts.",
    "¿Es malo?": "Is it bad?",
    "Son malos.": "They're bad.",
    "¡Rápido!": "Quick!",
    "Comí rápido.": "I ate quickly.",
    "Es grande.": "It's big.",
    "¿Son grandes?": "Are they big?",
    "Necesito ayuda.": "I need help.",
}

AI_ACCELERATED_PACK_A2_003 = [
    {
        "lexemeId": 42, "lemma": "ayudar", "pos": "verb", "gender": None,
        "englishGloss": "to help", "frequencyRank": 1088, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "help and requests", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 practical needs topic",
        "sentences": [
            (119, 122, "Quiero ayudar.", "I want to help."),
            (120, 123, "¿Puedes ayudarme?", "Can you help me?"),
        ],
    },
    {
        "lexemeId": 43, "lemma": "trabajar", "pos": "verb", "gender": None,
        "englishGloss": "to work", "frequencyRank": 846, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "work routines", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 work/school topic",
        "sentences": [
            (121, 124, "Trabajo hoy.", "I work today."),
            (122, 125, "Ella trabaja aquí.", "She works here."),
        ],
    },
    {
        "lexemeId": 44, "lemma": "aprender", "pos": "verb", "gender": None,
        "englishGloss": "to learn", "frequencyRank": 1788, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "learning", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 school/self-study topic",
        "sentences": [
            (123, 126, "Aprendo español.", "I learn Spanish."),
            (124, 127, "Quiero aprender más.", "I want to learn more."),
        ],
    },
    {
        "lexemeId": 45, "lemma": "escuchar", "pos": "verb", "gender": None,
        "englishGloss": "to listen", "frequencyRank": 1037, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "communication", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 communication topic",
        "sentences": [
            (125, 128, "Escucho música.", "I listen to music."),
            (126, 129, "¿Puedes escuchar?", "Can you listen?"),
        ],
    },
    {
        "lexemeId": 46, "lemma": "pagar", "pos": "verb", "gender": None,
        "englishGloss": "to pay", "frequencyRank": 1007, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "shopping and errands", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 shopping/money topic",
        "sentences": [
            (127, 130, "Pago ahora.", "I pay now."),
            (128, 131, "Quiero pagar.", "I want to pay."),
        ],
    },
    {
        "lexemeId": 47, "lemma": "abrir", "pos": "verb", "gender": None,
        "englishGloss": "to open", "frequencyRank": 664, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "daily actions", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 errands/home topic",
        "sentences": [
            (129, 132, "Abre la puerta.", "Open the door."),
            (130, 133, "Quiero abrir la puerta.", "I want to open the door."),
        ],
    },
    {
        "lexemeId": 48, "lemma": "cerrar", "pos": "verb", "gender": None,
        "englishGloss": "to close", "frequencyRank": 1105, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "daily actions", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 errands/home topic",
        "sentences": [
            (131, 134, "Cierra la puerta.", "Close the door."),
            (132, 135, "Necesito cerrar la tienda.", "I need to close the store."),
        ],
    },
    {
        "lexemeId": 49, "lemma": "fácil", "pos": "adjective", "gender": None,
        "englishGloss": "easy", "frequencyRank": 814, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "common description", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (133, 136, "Es fácil.", "It is easy."),
            (134, 137, "La pregunta es fácil.", "The question is easy."),
        ],
    },
    {
        "lexemeId": 50, "lemma": "difícil", "pos": "adjective", "gender": None,
        "englishGloss": "difficult", "frequencyRank": 938, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "common description", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (135, 138, "Es difícil.", "It is difficult."),
            (136, 139, "El trabajo es difícil.", "The job is difficult."),
        ],
    },
    {
        "lexemeId": 51, "lemma": "cerca", "pos": "adverb", "gender": None,
        "englishGloss": "nearby; close", "frequencyRank": 433, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "location", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (137, 140, "La tienda está cerca.", "The store is nearby."),
            (138, 141, "Estoy cerca.", "I am nearby."),
        ],
    },
    {
        "lexemeId": 52, "lemma": "lejos", "pos": "adverb", "gender": None,
        "englishGloss": "far; far away", "frequencyRank": 1565, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "location", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (139, 142, "Vivo lejos.", "I live far away."),
            (140, 143, "La escuela está lejos.", "The school is far away."),
        ],
    },
    {
        "lexemeId": 53, "lemma": "siempre", "pos": "adverb", "gender": None,
        "englishGloss": "always", "frequencyRank": 171, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "frequency and routines", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (141, 144, "Siempre trabajo.", "I always work."),
            (142, 145, "Siempre quiero agua.", "I always want water."),
        ],
    },
    {
        "lexemeId": 54, "lemma": "nunca", "pos": "adverb", "gender": None,
        "englishGloss": "never", "frequencyRank": 446, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "frequency and routines", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (143, 146, "Nunca pago tarde.", "I never pay late."),
            (144, 147, "Nunca trabajo aquí.", "I never work here."),
        ],
    },
    {
        "lexemeId": 55, "lemma": "ahora", "pos": "adverb", "gender": None,
        "englishGloss": "now", "frequencyRank": 92, "cefrBand": "A2", "difficultyPrior": 0.3,
        "reason": "time and immediacy", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (145, 148, "Necesito agua ahora.", "I need water now."),
            (146, 149, "Estoy aquí ahora.", "I am here now."),
        ],
    },
    {
        "lexemeId": 56, "lemma": "luego", "pos": "adverb", "gender": None,
        "englishGloss": "later; then", "frequencyRank": 505, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "time sequencing", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (147, 150, "Te veo luego.", "I will see you later."),
            (148, 151, "Trabajo luego.", "I work later."),
        ],
    },
    {
        "lexemeId": 57, "lemma": "calle", "pos": "noun", "gender": "F",
        "englishGloss": "street", "frequencyRank": 590, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "directions and errands", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 travel/errands topic",
        "sentences": [
            (149, 152, "Vivo en esta calle.", "I live on this street."),
            (150, 153, "La tienda está en esta calle.", "The store is on this street."),
        ],
    },
    {
        "lexemeId": 58, "lemma": "puerta", "pos": "noun", "gender": "F",
        "englishGloss": "door", "frequencyRank": 852, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "home and errands", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 home/errands topic",
        "sentences": [
            (151, 154, "La puerta está abierta.", "The door is open."),
            (152, 155, "La puerta está cerrada.", "The door is closed."),
        ],
    },
    {
        "lexemeId": 59, "lemma": "mesa", "pos": "noun", "gender": "F",
        "englishGloss": "table", "frequencyRank": 1443, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "home and food", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 home/food topic",
        "sentences": [
            (153, 156, "La comida está en la mesa.", "The food is on the table."),
            (154, 157, "La mesa es grande.", "The table is big."),
        ],
    },
    {
        "lexemeId": 60, "lemma": "teléfono", "pos": "noun", "gender": "M",
        "englishGloss": "phone", "frequencyRank": 1856, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "daily communication", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 communication topic",
        "sentences": [
            (155, 158, "Necesito mi teléfono.", "I need my phone."),
            (156, 159, "El teléfono está en la mesa.", "The phone is on the table."),
        ],
    },
    {
        "lexemeId": 61, "lemma": "pregunta", "pos": "noun", "gender": "F",
        "englishGloss": "question", "frequencyRank": 760, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "learning and clarification", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 questions topic",
        "sentences": [
            (157, 160, "Tengo una pregunta.", "I have a question."),
            (158, 161, "La pregunta es importante.", "The question is important."),
        ],
    },
]

AI_ACCELERATED_PACK_A2_004 = [
    {
        "lexemeId": 62, "lemma": "buscar", "pos": "verb", "gender": None,
        "englishGloss": "to look for; to search", "frequencyRank": 640, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "daily problem solving", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (159, 162, "Busco mi teléfono.", "I look for my phone."),
            (160, 163, "Buscamos la tienda.", "We look for the store."),
        ],
    },
    {
        "lexemeId": 63, "lemma": "encontrar", "pos": "verb", "gender": None,
        "englishGloss": "to find", "frequencyRank": 533, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "daily problem solving", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (161, 164, "Encuentro mi casa.", "I find my house."),
            (162, 165, "Encontré dinero.", "I found money."),
        ],
    },
    {
        "lexemeId": 64, "lemma": "pensar", "pos": "verb", "gender": None,
        "englishGloss": "to think", "frequencyRank": 330, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "thought and opinions", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (163, 166, "Pienso en mi familia.", "I think about my family."),
            (164, 167, "¿Qué piensas?", "What do you think?"),
            (219, 222, "Pienso mucho.", "I think a lot."),
            (220, 223, "Pienso en ti.", "I think about you."),
        ],
    },
    {
        "lexemeId": 65, "lemma": "entender", "pos": "verb", "gender": None,
        "englishGloss": "to understand", "frequencyRank": 674, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "clarification and learning", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (165, 168, "Entiendo la pregunta.", "I understand the question."),
            (166, 169, "No entiendo.", "I do not understand."),
        ],
    },
    {
        "lexemeId": 66, "lemma": "recordar", "pos": "verb", "gender": None,
        "englishGloss": "to remember", "frequencyRank": 1177, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "memory and plans", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 practical communication topic",
        "sentences": [
            (167, 170, "Recuerdo tu casa.", "I remember your house."),
            (168, 171, "¿Recuerdas mi nombre?", "Do you remember my name?"),
        ],
    },
    {
        "lexemeId": 67, "lemma": "esperar", "pos": "verb", "gender": None,
        "englishGloss": "to wait; to hope", "frequencyRank": 477, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "waiting and plans", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (169, 172, "Espero aquí.", "I wait here."),
            (170, 173, "Espero verte luego.", "I hope to see you later."),
            (221, 224, "Esperamos el autobús.", "We wait for the bus."),
            (222, 225, "Espero a mi amigo.", "I wait for my friend."),
        ],
    },
    {
        "lexemeId": 68, "lemma": "mirar", "pos": "verb", "gender": None,
        "englishGloss": "to look at; to watch", "frequencyRank": 312, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "perception and directions", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (171, 174, "Miro la puerta.", "I look at the door."),
            (172, 175, "Mira esta mesa.", "Look at this table."),
            (223, 226, "Miro la ciudad.", "I look at the city."),
            (224, 227, "Miramos el teléfono.", "We look at the phone."),
        ],
    },
    {
        "lexemeId": 69, "lemma": "llevar", "pos": "verb", "gender": None,
        "englishGloss": "to carry; to wear", "frequencyRank": 454, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "daily movement and possessions", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (173, 176, "Llevo mi teléfono.", "I carry my phone."),
            (174, 177, "Ella lleva comida.", "She carries food."),
            (225, 228, "Llevo dinero.", "I carry money."),
            (226, 229, "Llevamos agua.", "We carry water."),
        ],
    },
    {
        "lexemeId": 70, "lemma": "tomar", "pos": "verb", "gender": None,
        "englishGloss": "to take; to drink", "frequencyRank": 445, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "food, drink, and transport", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (175, 178, "Tomo agua.", "I drink water."),
            (176, 179, "Toma el autobús.", "Take the bus."),
            (227, 230, "Tomo el autobús.", "I take the bus."),
            (228, 231, "Tomamos agua.", "We drink water."),
        ],
    },
    {
        "lexemeId": 71, "lemma": "entrar", "pos": "verb", "gender": None,
        "englishGloss": "to enter; to come in", "frequencyRank": 932, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "movement and errands", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (177, 180, "Entro en la tienda.", "I enter the store."),
            (178, 181, "Entra ahora.", "Come in now."),
        ],
    },
    {
        "lexemeId": 72, "lemma": "pasar", "pos": "verb", "gender": None,
        "englishGloss": "to pass; to happen", "frequencyRank": 197, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "movement and events", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (179, 182, "El autobús pasa.", "The bus passes."),
            (180, 183, "Paso por la calle.", "I pass through the street."),
            (229, 232, "Él pasa por aquí.", "He passes through here."),
            (230, 233, "Pasamos por la ciudad.", "We pass through the city."),
        ],
    },
    {
        "lexemeId": 73, "lemma": "volver", "pos": "verb", "gender": None,
        "englishGloss": "to return; to come back", "frequencyRank": 289, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "movement and routines", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (181, 184, "Vuelvo a casa.", "I return home."),
            (182, 185, "Vuelve luego.", "Come back later."),
            (231, 234, "Volvemos a la escuela.", "We return to school."),
            (232, 235, "Vuelvo temprano.", "I return early."),
        ],
    },
    {
        "lexemeId": 74, "lemma": "empezar", "pos": "verb", "gender": None,
        "englishGloss": "to start; to begin", "frequencyRank": 1054, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "time sequencing", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 routines topic",
        "sentences": [
            (183, 186, "Empiezo ahora.", "I start now."),
            (184, 187, "La clase empieza.", "The class starts."),
        ],
    },
    {
        "lexemeId": 75, "lemma": "terminar", "pos": "verb", "gender": None,
        "englishGloss": "to finish; to end", "frequencyRank": 1163, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "time sequencing", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 routines topic",
        "sentences": [
            (185, 188, "Termino el trabajo.", "I finish the job."),
            (186, 189, "La clase termina ahora.", "The class ends now."),
        ],
    },
    {
        "lexemeId": 76, "lemma": "cambiar", "pos": "verb", "gender": None,
        "englishGloss": "to change", "frequencyRank": 595, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "daily changes and plans", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (187, 190, "Cambio de trabajo.", "I change jobs."),
            (188, 191, "El tiempo cambia.", "The weather changes."),
        ],
    },
    {
        "lexemeId": 77, "lemma": "pequeño", "pos": "adjective", "gender": None,
        "englishGloss": "small", "frequencyRank": 535, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "common description", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (189, 192, "La casa es pequeña.", "The house is small."),
            (190, 193, "El perro es pequeño.", "The dog is small."),
        ],
    },
    {
        "lexemeId": 78, "lemma": "nuevo", "pos": "adjective", "gender": None,
        "englishGloss": "new", "frequencyRank": 143, "cefrBand": "A2", "difficultyPrior": 0.3,
        "reason": "common description", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (191, 194, "Tengo un teléfono nuevo.", "I have a new phone."),
            (192, 195, "La escuela es nueva.", "The school is new."),
        ],
    },
    {
        "lexemeId": 79, "lemma": "viejo", "pos": "adjective", "gender": None,
        "englishGloss": "old", "frequencyRank": 576, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "common description", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (193, 196, "Mi coche es viejo.", "My car is old."),
            (194, 197, "La casa es vieja.", "The house is old."),
        ],
    },
    {
        "lexemeId": 80, "lemma": "mismo", "pos": "adjective", "gender": None,
        "englishGloss": "same", "frequencyRank": 173, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "common description and comparison", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (195, 198, "Es la misma persona.", "It is the same person."),
            (196, 199, "Tengo el mismo teléfono.", "I have the same phone."),
        ],
    },
    {
        "lexemeId": 81, "lemma": "primero", "pos": "adjective/adverb", "gender": None,
        "englishGloss": "first", "frequencyRank": 242, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "sequencing", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (197, 200, "Soy el primero.", "I am first."),
            (198, 201, "Es mi primer día.", "It is my first day."),
        ],
    },
    {
        "lexemeId": 82, "lemma": "último", "pos": "adjective", "gender": None,
        "englishGloss": "last; latest", "frequencyRank": 386, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "sequencing", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (199, 202, "Es el último autobús.", "It is the last bus."),
            (200, 203, "La última pregunta es difícil.", "The last question is difficult."),
        ],
    },
    {
        "lexemeId": 83, "lemma": "mejor", "pos": "adjective/adverb", "gender": None,
        "englishGloss": "better; best", "frequencyRank": 116, "cefrBand": "A2", "difficultyPrior": 0.3,
        "reason": "comparison and health state", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (201, 204, "Estoy mejor ahora.", "I am better now."),
            (202, 205, "Es mejor así.", "It is better this way."),
        ],
    },
    {
        "lexemeId": 84, "lemma": "peor", "pos": "adjective/adverb", "gender": None,
        "englishGloss": "worse; worst", "frequencyRank": 798, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "comparison and health state", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (203, 206, "Estoy peor hoy.", "I am worse today."),
            (204, 207, "Es peor ahora.", "It is worse now."),
        ],
    },
    {
        "lexemeId": 85, "lemma": "temprano", "pos": "adverb", "gender": None,
        "englishGloss": "early", "frequencyRank": 1551, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "time and routines", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 routines topic",
        "sentences": [
            (205, 208, "Llego temprano.", "I arrive early."),
            (206, 209, "Salimos temprano.", "We leave early."),
        ],
    },
    {
        "lexemeId": 86, "lemma": "tarde", "pos": "adverb/noun", "gender": "F",
        "englishGloss": "late; afternoon", "frequencyRank": 425, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "time and routines", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (207, 210, "Llego tarde.", "I arrive late."),
            (208, 211, "Trabajo por la tarde.", "I work in the afternoon."),
        ],
    },
    {
        "lexemeId": 87, "lemma": "ciudad", "pos": "noun", "gender": "F",
        "englishGloss": "city", "frequencyRank": 272, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "places and travel", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (209, 212, "Vivo en la ciudad.", "I live in the city."),
            (210, 213, "La ciudad es grande.", "The city is big."),
        ],
    },
    {
        "lexemeId": 88, "lemma": "país", "pos": "noun", "gender": "M",
        "englishGloss": "country", "frequencyRank": 435, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "places and identity", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (211, 214, "Mi país es grande.", "My country is big."),
            (212, 215, "Vivo en este país.", "I live in this country."),
        ],
    },
    {
        "lexemeId": 89, "lemma": "amigo", "pos": "noun", "gender": "M",
        "englishGloss": "friend", "frequencyRank": 160, "cefrBand": "A2", "difficultyPrior": 0.3,
        "reason": "relationships", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (213, 216, "Mi amigo está aquí.", "My friend is here."),
            (214, 217, "Tengo un amigo.", "I have a friend."),
        ],
    },
    {
        "lexemeId": 90, "lemma": "niño", "pos": "noun", "gender": "M",
        "englishGloss": "child; boy", "frequencyRank": 345, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "people and family", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (215, 218, "El niño come.", "The boy eats."),
            (216, 219, "Veo al niño.", "I see the boy."),
        ],
    },
    {
        "lexemeId": 91, "lemma": "mujer", "pos": "noun", "gender": "F",
        "englishGloss": "woman", "frequencyRank": 134, "cefrBand": "A2", "difficultyPrior": 0.3,
        "reason": "people and relationships", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (217, 220, "La mujer trabaja aquí.", "The woman works here."),
            (218, 221, "Esa mujer es mi amiga.", "That woman is my friend."),
        ],
    },
]

AI_ACCELERATED_PACK_A2_005 = [
    {
        "lexemeId": 92, "lemma": "reservar", "pos": "verb", "gender": None,
        "englishGloss": "to reserve; to book", "frequencyRank": 1260, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "travel bookings", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 travel topic",
        "sentences": [
            (233, 236, "Reservo una habitación.", "I book a room."),
            (234, 237, "Reservamos el hotel.", "We book the hotel."),
        ],
    },
    {
        "lexemeId": 93, "lemma": "cancelar", "pos": "verb", "gender": None,
        "englishGloss": "to cancel", "frequencyRank": 1700, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "travel and appointment changes", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 travel/work topic",
        "sentences": [
            (235, 238, "Cancelo la reserva.", "I cancel the reservation."),
            (236, 239, "Cancelamos el viaje.", "We cancel the trip."),
        ],
    },
    {
        "lexemeId": 94, "lemma": "llamar", "pos": "verb", "gender": None,
        "englishGloss": "to call", "frequencyRank": 647, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "phone and health communication", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (237, 240, "Llamo al médico.", "I call the doctor."),
            (238, 241, "Llámame mañana.", "Call me tomorrow."),
        ],
    },
    {
        "lexemeId": 95, "lemma": "preguntar", "pos": "verb", "gender": None,
        "englishGloss": "to ask", "frequencyRank": 768, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "questions and help", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (239, 242, "Pregunto la hora.", "I ask the time."),
            (240, 243, "Preguntamos en la oficina.", "We ask at the office."),
        ],
    },
    {
        "lexemeId": 96, "lemma": "responder", "pos": "verb", "gender": None,
        "englishGloss": "to answer; to respond", "frequencyRank": 955, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "communication", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 communication topic",
        "sentences": [
            (241, 244, "Respondo al mensaje.", "I answer the message."),
            (242, 245, "Ella responde rápido.", "She answers quickly."),
        ],
    },
    {
        "lexemeId": 97, "lemma": "enviar", "pos": "verb", "gender": None,
        "englishGloss": "to send", "frequencyRank": 1112, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "work and social communication", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 work/communication topic",
        "sentences": [
            (243, 246, "Envío un mensaje.", "I send a message."),
            (244, 247, "Enviamos dinero.", "We send money."),
        ],
    },
    {
        "lexemeId": 98, "lemma": "recibir", "pos": "verb", "gender": None,
        "englishGloss": "to receive", "frequencyRank": 758, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "work and household communication", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (245, 248, "Recibo una carta.", "I receive a letter."),
            (246, 249, "Recibimos ayuda.", "We receive help."),
        ],
    },
    {
        "lexemeId": 99, "lemma": "usar", "pos": "verb", "gender": None,
        "englishGloss": "to use", "frequencyRank": 421, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "tools and daily tasks", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (247, 250, "Uso el teléfono.", "I use the phone."),
            (248, 251, "Usamos la cocina.", "We use the kitchen."),
            (303, 306, "Uso esta llave.", "I use this key."),
            (304, 307, "Usan el tren.", "They use the train."),
        ],
    },
    {
        "lexemeId": 100, "lemma": "limpiar", "pos": "verb", "gender": None,
        "englishGloss": "to clean", "frequencyRank": 1380, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "household routines", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 household topic",
        "sentences": [
            (249, 252, "Limpio la casa.", "I clean the house."),
            (250, 253, "Limpiamos la mesa.", "We clean the table."),
        ],
    },
    {
        "lexemeId": 101, "lemma": "cocinar", "pos": "verb", "gender": None,
        "englishGloss": "to cook", "frequencyRank": 1450, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "food and household routines", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 household/food topic",
        "sentences": [
            (251, 254, "Cocino comida.", "I cook food."),
            (252, 255, "Ella cocina en casa.", "She cooks at home."),
        ],
    },
    {
        "lexemeId": 102, "lemma": "descansar", "pos": "verb", "gender": None,
        "englishGloss": "to rest", "frequencyRank": 1505, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "health and routines", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 health/routines topic",
        "sentences": [
            (253, 256, "Descanso por la tarde.", "I rest in the afternoon."),
            (254, 257, "Necesito descansar.", "I need to rest."),
        ],
    },
    {
        "lexemeId": 103, "lemma": "dormir", "pos": "verb", "gender": None,
        "englishGloss": "to sleep", "frequencyRank": 770, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "health and routines", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (255, 258, "Duermo bien.", "I sleep well."),
            (256, 259, "El niño duerme.", "The boy sleeps."),
        ],
    },
    {
        "lexemeId": 104, "lemma": "sentir", "pos": "verb", "gender": None,
        "englishGloss": "to feel", "frequencyRank": 520, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "health and feelings", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (257, 260, "Me siento mejor.", "I feel better."),
            (258, 261, "Siento frío.", "I feel cold."),
        ],
    },
    {
        "lexemeId": 105, "lemma": "doler", "pos": "verb", "gender": None,
        "englishGloss": "to hurt; to ache", "frequencyRank": 1620, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "health symptoms", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 health/body topic",
        "sentences": [
            (259, 262, "Me duele el pie.", "My foot hurts."),
            (260, 263, "A él le duele la mano.", "His hand hurts."),
        ],
    },
    {
        "lexemeId": 106, "lemma": "cuidar", "pos": "verb", "gender": None,
        "englishGloss": "to take care of", "frequencyRank": 1188, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "health, home, and family care", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 health/household topic",
        "sentences": [
            (261, 264, "Cuido a mi hijo.", "I take care of my son."),
            (262, 265, "Cuidamos la casa.", "We take care of the house."),
        ],
    },
    {
        "lexemeId": 107, "lemma": "visitar", "pos": "verb", "gender": None,
        "englishGloss": "to visit", "frequencyRank": 1355, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "travel and social plans", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 travel/social topic",
        "sentences": [
            (263, 266, "Visito a mi familia.", "I visit my family."),
            (264, 267, "Visitamos la ciudad.", "We visit the city."),
        ],
    },
    {
        "lexemeId": 108, "lemma": "conocer", "pos": "verb", "gender": None,
        "englishGloss": "to know; to meet", "frequencyRank": 250, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "people, places, and introductions", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (265, 268, "Conozco a tu amigo.", "I know your friend."),
            (266, 269, "Quiero conocer el país.", "I want to get to know the country."),
            (305, 308, "Conozco la ciudad.", "I know the city."),
            (306, 309, "Conocemos al médico.", "We know the doctor."),
        ],
    },
    {
        "lexemeId": 109, "lemma": "compartir", "pos": "verb", "gender": None,
        "englishGloss": "to share", "frequencyRank": 1322, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "social and household interaction", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 social/household topic",
        "sentences": [
            (267, 270, "Comparto mi comida.", "I share my food."),
            (268, 271, "Compartimos la mesa.", "We share the table."),
        ],
    },
    {
        "lexemeId": 110, "lemma": "preparar", "pos": "verb", "gender": None,
        "englishGloss": "to prepare", "frequencyRank": 890, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "work, food, and travel preparation", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (269, 272, "Preparo la comida.", "I prepare the food."),
            (270, 273, "Preparamos el viaje.", "We prepare the trip."),
        ],
    },
    {
        "lexemeId": 111, "lemma": "seguir", "pos": "verb", "gender": None,
        "englishGloss": "to follow; to continue", "frequencyRank": 172, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "directions and continuing actions", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (271, 274, "Sigo el camino.", "I follow the road."),
            (272, 275, "Sigue trabajando.", "Keep working."),
            (307, 310, "Seguimos juntos.", "We continue together."),
            (308, 311, "Sigo aquí.", "I am still here."),
        ],
    },
    {
        "lexemeId": 112, "lemma": "cerca", "pos": "adverb", "gender": None,
        "englishGloss": "near; nearby", "frequencyRank": 579, "cefrBand": "A2", "difficultyPrior": 0.4,
        "reason": "location and travel", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (273, 276, "El hotel está cerca.", "The hotel is nearby."),
            (274, 277, "Trabajo cerca de casa.", "I work near home."),
        ],
    },
    {
        "lexemeId": 113, "lemma": "lejos", "pos": "adverb", "gender": None,
        "englishGloss": "far; far away", "frequencyRank": 892, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "location and travel", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (275, 278, "El aeropuerto está lejos.", "The airport is far away."),
            (276, 279, "Vivo lejos de la oficina.", "I live far from the office."),
        ],
    },
    {
        "lexemeId": 114, "lemma": "ocupado", "pos": "adjective", "gender": None,
        "englishGloss": "busy; occupied", "frequencyRank": 1344, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "work and availability", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 work/social topic",
        "sentences": [
            (277, 280, "Estoy ocupado hoy.", "I am busy today."),
            (278, 281, "Mi amigo está ocupado.", "My friend is busy."),
        ],
    },
    {
        "lexemeId": 115, "lemma": "libre", "pos": "adjective", "gender": None,
        "englishGloss": "free; available", "frequencyRank": 639, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "availability and plans", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (279, 282, "Estoy libre mañana.", "I am free tomorrow."),
            (280, 283, "La mesa está libre.", "The table is free."),
        ],
    },
    {
        "lexemeId": 116, "lemma": "enfermo", "pos": "adjective", "gender": None,
        "englishGloss": "sick; ill", "frequencyRank": 1267, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "health state", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 health topic",
        "sentences": [
            (281, 284, "Estoy enfermo.", "I am sick."),
            (282, 285, "El niño está enfermo.", "The boy is sick."),
        ],
    },
    {
        "lexemeId": 117, "lemma": "sano", "pos": "adjective", "gender": None,
        "englishGloss": "healthy", "frequencyRank": 1625, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "health state", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 health topic",
        "sentences": [
            (283, 286, "Estoy sano.", "I am healthy."),
            (284, 287, "La comida es sana.", "The food is healthy."),
        ],
    },
    {
        "lexemeId": 118, "lemma": "limpio", "pos": "adjective", "gender": None,
        "englishGloss": "clean", "frequencyRank": 1280, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "household description", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 household topic",
        "sentences": [
            (285, 288, "El hotel está limpio.", "The hotel is clean."),
            (286, 289, "La mesa está limpia.", "The table is clean."),
        ],
    },
    {
        "lexemeId": 119, "lemma": "sucio", "pos": "adjective", "gender": None,
        "englishGloss": "dirty", "frequencyRank": 1565, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "household description", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 household topic",
        "sentences": [
            (287, 290, "El baño está sucio.", "The bathroom is dirty."),
            (288, 291, "Mi camisa está sucia.", "My shirt is dirty."),
        ],
    },
    {
        "lexemeId": 120, "lemma": "seguro", "pos": "adjective", "gender": None,
        "englishGloss": "safe; sure", "frequencyRank": 613, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "travel safety and confidence", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (289, 292, "El viaje es seguro.", "The trip is safe."),
            (290, 293, "Estoy seguro.", "I am sure."),
        ],
    },
    {
        "lexemeId": 121, "lemma": "listo", "pos": "adjective", "gender": None,
        "englishGloss": "ready", "frequencyRank": 977, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "readiness and routines", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 routines/work topic",
        "sentences": [
            (291, 294, "Estoy listo.", "I am ready."),
            (292, 295, "La comida está lista.", "The food is ready."),
        ],
    },
    {
        "lexemeId": 122, "lemma": "hotel", "pos": "noun", "gender": "M",
        "englishGloss": "hotel", "frequencyRank": 726, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "travel lodging", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (293, 296, "El hotel es nuevo.", "The hotel is new."),
            (294, 297, "Reservo un hotel.", "I book a hotel."),
        ],
    },
    {
        "lexemeId": 123, "lemma": "aeropuerto", "pos": "noun", "gender": "M",
        "englishGloss": "airport", "frequencyRank": 1900, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "travel transit", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 travel/transport topic",
        "sentences": [
            (295, 298, "Llego al aeropuerto.", "I arrive at the airport."),
            (296, 299, "Busco el aeropuerto.", "I look for the airport."),
        ],
    },
    {
        "lexemeId": 124, "lemma": "tren", "pos": "noun", "gender": "M",
        "englishGloss": "train", "frequencyRank": 1050, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "transport", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 travel/transport topic",
        "sentences": [
            (297, 300, "Tomo el tren.", "I take the train."),
            (298, 301, "El tren llega tarde.", "The train arrives late."),
        ],
    },
    {
        "lexemeId": 125, "lemma": "médico", "pos": "noun", "gender": "M",
        "englishGloss": "doctor", "frequencyRank": 874, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "health services", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 health topic",
        "sentences": [
            (299, 302, "Necesito un médico.", "I need a doctor."),
            (300, 303, "Veo al médico.", "I see the doctor."),
        ],
    },
    {
        "lexemeId": 126, "lemma": "oficina", "pos": "noun", "gender": "F",
        "englishGloss": "office", "frequencyRank": 806, "cefrBand": "A2", "difficultyPrior": 0.5,
        "reason": "workplace", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (301, 304, "Trabajo en la oficina.", "I work in the office."),
            (302, 305, "La oficina abre temprano.", "The office opens early."),
        ],
    },
]

AI_ACCELERATED_PACK_A2_006 = [
    {
        "lexemeId": 127, "lemma": "creer", "pos": "verb", "gender": None,
        "englishGloss": "to believe; to think", "frequencyRank": 180, "cefrBand": "B1", "difficultyPrior": 0.4,
        "reason": "opinions and uncertainty", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (309, 312, "Creo que sí.", "I think so."),
            (310, 313, "No creo eso.", "I do not believe that."),
            (389, 392, "Creo en ti.", "I believe in you."),
            (390, 393, "Creemos que es importante.", "We think it is important."),
        ],
    },
    {
        "lexemeId": 128, "lemma": "opinar", "pos": "verb", "gender": None,
        "englishGloss": "to give an opinion", "frequencyRank": 2050, "cefrBand": "B1", "difficultyPrior": 0.6,
        "reason": "opinions", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 opinions topic",
        "sentences": [
            (311, 314, "Opino que es mejor.", "I think it is better."),
            (312, 315, "Quiero opinar también.", "I want to give my opinion too."),
        ],
    },
    {
        "lexemeId": 129, "lemma": "preferir", "pos": "verb", "gender": None,
        "englishGloss": "to prefer", "frequencyRank": 1175, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "preferences and choices", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 opinions topic",
        "sentences": [
            (313, 316, "Prefiero comer en casa.", "I prefer to eat at home."),
            (314, 317, "Ella prefiere el tren.", "She prefers the train."),
        ],
    },
    {
        "lexemeId": 130, "lemma": "decidir", "pos": "verb", "gender": None,
        "englishGloss": "to decide", "frequencyRank": 845, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "plans and choices", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (315, 318, "Decido salir temprano.", "I decide to leave early."),
            (316, 319, "Decidimos cambiar la reserva.", "We decide to change the reservation."),
        ],
    },
    {
        "lexemeId": 131, "lemma": "explicar", "pos": "verb", "gender": None,
        "englishGloss": "to explain", "frequencyRank": 996, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "clarifying problems", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 problems/services topic",
        "sentences": [
            (317, 320, "Explico el problema.", "I explain the problem."),
            (318, 321, "¿Puedes explicar esto?", "Can you explain this?"),
        ],
    },
    {
        "lexemeId": 132, "lemma": "avisar", "pos": "verb", "gender": None,
        "englishGloss": "to notify; to warn", "frequencyRank": 1500, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "appointments and problems", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 appointments topic",
        "sentences": [
            (319, 322, "Te aviso mañana.", "I will let you know tomorrow."),
            (320, 323, "Avísame si hay un problema.", "Let me know if there is a problem."),
        ],
    },
    {
        "lexemeId": 133, "lemma": "confirmar", "pos": "verb", "gender": None,
        "englishGloss": "to confirm", "frequencyRank": 1600, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "appointments and bookings", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 appointments/services topic",
        "sentences": [
            (321, 324, "Confirmo la cita.", "I confirm the appointment."),
            (322, 325, "Necesito confirmar la reserva.", "I need to confirm the reservation."),
        ],
    },
    {
        "lexemeId": 134, "lemma": "arreglar", "pos": "verb", "gender": None,
        "englishGloss": "to fix; to arrange", "frequencyRank": 1360, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "problems and repairs", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 problems/services topic",
        "sentences": [
            (323, 326, "Arreglo la puerta.", "I fix the door."),
            (324, 327, "Quiero arreglar la cita.", "I want to arrange the appointment."),
        ],
    },
    {
        "lexemeId": 135, "lemma": "quejarse", "pos": "verb", "gender": None,
        "englishGloss": "to complain", "frequencyRank": 2200, "cefrBand": "B1", "difficultyPrior": 0.6,
        "reason": "services and problems", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 services/problems topic",
        "sentences": [
            (325, 328, "Me quejo del servicio.", "I complain about the service."),
            (326, 329, "No quiero quejarme.", "I do not want to complain."),
        ],
    },
    {
        "lexemeId": 136, "lemma": "solucionar", "pos": "verb", "gender": None,
        "englishGloss": "to solve", "frequencyRank": 1900, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "problems", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 problems topic",
        "sentences": [
            (327, 330, "Soluciono el problema.", "I solve the problem."),
            (328, 331, "Podemos solucionar esto.", "We can solve this."),
        ],
    },
    {
        "lexemeId": 137, "lemma": "elegir", "pos": "verb", "gender": None,
        "englishGloss": "to choose", "frequencyRank": 1210, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "choices and services", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 choices topic",
        "sentences": [
            (329, 332, "Elijo este plato.", "I choose this dish."),
            (330, 333, "Elegimos el hotel.", "We choose the hotel."),
        ],
    },
    {
        "lexemeId": 138, "lemma": "probar", "pos": "verb", "gender": None,
        "englishGloss": "to try; to taste", "frequencyRank": 734, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "food and testing solutions", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (331, 334, "Pruebo la sopa.", "I taste the soup."),
            (332, 335, "Quiero probar otra opción.", "I want to try another option."),
        ],
    },
    {
        "lexemeId": 139, "lemma": "añadir", "pos": "verb", "gender": None,
        "englishGloss": "to add", "frequencyRank": 1505, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "food preparation and details", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 food prep topic",
        "sentences": [
            (333, 336, "Añado sal.", "I add salt."),
            (334, 337, "Añadimos agua a la sopa.", "We add water to the soup."),
        ],
    },
    {
        "lexemeId": 140, "lemma": "mezclar", "pos": "verb", "gender": None,
        "englishGloss": "to mix", "frequencyRank": 1805, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "food preparation", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 food prep topic",
        "sentences": [
            (335, 338, "Mezclo los ingredientes.", "I mix the ingredients."),
            (336, 339, "Mezcla bien la comida.", "Mix the food well."),
        ],
    },
    {
        "lexemeId": 141, "lemma": "calentar", "pos": "verb", "gender": None,
        "englishGloss": "to heat up", "frequencyRank": 1750, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "food preparation", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 food prep topic",
        "sentences": [
            (337, 340, "Caliento la comida.", "I heat up the food."),
            (338, 341, "Calentamos agua.", "We heat up water."),
        ],
    },
    {
        "lexemeId": 142, "lemma": "freír", "pos": "verb", "gender": None,
        "englishGloss": "to fry", "frequencyRank": 2450, "cefrBand": "B1", "difficultyPrior": 0.6,
        "reason": "food preparation", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 food prep topic",
        "sentences": [
            (339, 342, "Frío las papas.", "I fry the potatoes."),
            (340, 343, "No quiero freír la comida.", "I do not want to fry the food."),
        ],
    },
    {
        "lexemeId": 143, "lemma": "hervir", "pos": "verb", "gender": None,
        "englishGloss": "to boil", "frequencyRank": 2350, "cefrBand": "B1", "difficultyPrior": 0.6,
        "reason": "food preparation", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 food prep topic",
        "sentences": [
            (341, 344, "Hiervo agua.", "I boil water."),
            (342, 345, "La sopa hierve.", "The soup boils."),
        ],
    },
    {
        "lexemeId": 144, "lemma": "girar", "pos": "verb", "gender": None,
        "englishGloss": "to turn", "frequencyRank": 1550, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "directions", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 directions topic",
        "sentences": [
            (343, 346, "Giro a la derecha.", "I turn right."),
            (344, 347, "Gira en la esquina.", "Turn at the corner."),
        ],
    },
    {
        "lexemeId": 145, "lemma": "cruzar", "pos": "verb", "gender": None,
        "englishGloss": "to cross", "frequencyRank": 1240, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "directions and travel", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 directions topic",
        "sentences": [
            (345, 348, "Cruzo la calle.", "I cross the street."),
            (346, 349, "Cruzamos el puente.", "We cross the bridge."),
        ],
    },
    {
        "lexemeId": 146, "lemma": "subir", "pos": "verb", "gender": None,
        "englishGloss": "to go up; to get on", "frequencyRank": 620, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "directions and transport", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (347, 350, "Subo al tren.", "I get on the train."),
            (348, 351, "Subimos las escaleras.", "We go up the stairs."),
        ],
    },
    {
        "lexemeId": 147, "lemma": "bajar", "pos": "verb", "gender": None,
        "englishGloss": "to go down; to get off", "frequencyRank": 710, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "directions and transport", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (349, 352, "Bajo del autobús.", "I get off the bus."),
            (350, 353, "Bajamos por la calle.", "We go down the street."),
        ],
    },
    {
        "lexemeId": 148, "lemma": "perder", "pos": "verb", "gender": None,
        "englishGloss": "to lose", "frequencyRank": 630, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "travel and problems", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (351, 354, "Pierdo mi llave.", "I lose my key."),
            (352, 355, "Perdimos el tren.", "We missed the train."),
        ],
    },
    {
        "lexemeId": 149, "lemma": "olvidar", "pos": "verb", "gender": None,
        "englishGloss": "to forget", "frequencyRank": 905, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "problems and appointments", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (353, 356, "Olvido la cita.", "I forget the appointment."),
            (354, 357, "No olvides el mensaje.", "Do not forget the message."),
        ],
    },
    {
        "lexemeId": 150, "lemma": "dejar", "pos": "verb", "gender": None,
        "englishGloss": "to leave; to let", "frequencyRank": 210, "cefrBand": "B1", "difficultyPrior": 0.4,
        "reason": "errands, permission, and problems", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (355, 358, "Dejo la llave aquí.", "I leave the key here."),
            (356, 359, "Déjame hablar.", "Let me speak."),
            (391, 394, "Dejamos el coche en casa.", "We leave the car at home."),
            (392, 395, "No dejes la puerta abierta.", "Do not leave the door open."),
        ],
    },
    {
        "lexemeId": 151, "lemma": "importante", "pos": "adjective", "gender": None,
        "englishGloss": "important", "frequencyRank": 456, "cefrBand": "B1", "difficultyPrior": 0.4,
        "reason": "opinions and priorities", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (357, 360, "La cita es importante.", "The appointment is important."),
            (358, 361, "Es importante llegar temprano.", "It is important to arrive early."),
        ],
    },
    {
        "lexemeId": 152, "lemma": "posible", "pos": "adjective", "gender": None,
        "englishGloss": "possible", "frequencyRank": 410, "cefrBand": "B1", "difficultyPrior": 0.4,
        "reason": "plans and problem solving", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (359, 362, "Es posible cambiar la cita.", "It is possible to change the appointment."),
            (360, 363, "¿Es posible pagar ahora?", "Is it possible to pay now?"),
        ],
    },
    {
        "lexemeId": 153, "lemma": "necesario", "pos": "adjective", "gender": None,
        "englishGloss": "necessary", "frequencyRank": 690, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "needs and services", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (361, 364, "Es necesario llamar.", "It is necessary to call."),
            (362, 365, "No es necesario esperar.", "It is not necessary to wait."),
        ],
    },
    {
        "lexemeId": 154, "lemma": "urgente", "pos": "adjective", "gender": None,
        "englishGloss": "urgent", "frequencyRank": 1800, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "health and service problems", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 problems/services topic",
        "sentences": [
            (363, 366, "Es urgente.", "It is urgent."),
            (364, 367, "Necesito ayuda urgente.", "I need urgent help."),
        ],
    },
    {
        "lexemeId": 155, "lemma": "grave", "pos": "adjective", "gender": None,
        "englishGloss": "serious", "frequencyRank": 1100, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "health and problems", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 problems/health topic",
        "sentences": [
            (365, 368, "El problema es grave.", "The problem is serious."),
            (366, 369, "No parece grave.", "It does not seem serious."),
        ],
    },
    {
        "lexemeId": 156, "lemma": "fácil", "pos": "adjective", "gender": None,
        "englishGloss": "easy", "frequencyRank": 700, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "opinions and difficulty", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (367, 370, "La receta es fácil.", "The recipe is easy."),
            (368, 371, "Es fácil llegar.", "It is easy to arrive."),
        ],
    },
    {
        "lexemeId": 157, "lemma": "difícil", "pos": "adjective", "gender": None,
        "englishGloss": "difficult", "frequencyRank": 602, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "opinions and difficulty", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (369, 372, "La pregunta es difícil.", "The question is difficult."),
            (370, 373, "Es difícil encontrar la oficina.", "It is difficult to find the office."),
        ],
    },
    {
        "lexemeId": 158, "lemma": "molesto", "pos": "adjective", "gender": None,
        "englishGloss": "annoying; upset", "frequencyRank": 1905, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "emotions and complaints", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 emotions/problems topic",
        "sentences": [
            (371, 374, "Estoy molesto.", "I am upset."),
            (372, 375, "El ruido es molesto.", "The noise is annoying."),
        ],
    },
    {
        "lexemeId": 159, "lemma": "claramente", "pos": "adverb", "gender": None,
        "englishGloss": "clearly", "frequencyRank": 1705, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "explaining opinions", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 opinions/clarification topic",
        "sentences": [
            (373, 376, "Habla claramente.", "Speak clearly."),
            (374, 377, "Explico el problema claramente.", "I explain the problem clearly."),
        ],
    },
    {
        "lexemeId": 160, "lemma": "problema", "pos": "noun", "gender": "M",
        "englishGloss": "problem", "frequencyRank": 358, "cefrBand": "B1", "difficultyPrior": 0.4,
        "reason": "problems and services", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (375, 378, "Tengo un problema.", "I have a problem."),
            (376, 379, "El problema está aquí.", "The problem is here."),
        ],
    },
    {
        "lexemeId": 161, "lemma": "cita", "pos": "noun", "gender": "F",
        "englishGloss": "appointment", "frequencyRank": 1205, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "appointments", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 appointments topic",
        "sentences": [
            (377, 380, "Tengo una cita.", "I have an appointment."),
            (378, 381, "Cancelo la cita.", "I cancel the appointment."),
        ],
    },
    {
        "lexemeId": 162, "lemma": "servicio", "pos": "noun", "gender": "M",
        "englishGloss": "service", "frequencyRank": 512, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "services and complaints", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (379, 382, "El servicio es bueno.", "The service is good."),
            (380, 383, "Necesito otro servicio.", "I need another service."),
        ],
    },
    {
        "lexemeId": 163, "lemma": "receta", "pos": "noun", "gender": "F",
        "englishGloss": "recipe; prescription", "frequencyRank": 1808, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "food prep and health", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 food prep/health topic",
        "sentences": [
            (381, 384, "Sigo la receta.", "I follow the recipe."),
            (382, 385, "El médico escribe una receta.", "The doctor writes a prescription."),
        ],
    },
    {
        "lexemeId": 164, "lemma": "ingrediente", "pos": "noun", "gender": "M",
        "englishGloss": "ingredient", "frequencyRank": 2205, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "food preparation", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 food prep topic",
        "sentences": [
            (383, 386, "Necesito un ingrediente.", "I need an ingredient."),
            (384, 387, "Mezclo los ingredientes.", "I mix the ingredients."),
        ],
    },
    {
        "lexemeId": 165, "lemma": "esquina", "pos": "noun", "gender": "F",
        "englishGloss": "corner", "frequencyRank": 1420, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "directions", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 directions topic",
        "sentences": [
            (385, 388, "Gira en la esquina.", "Turn at the corner."),
            (386, 389, "La tienda está en la esquina.", "The store is on the corner."),
        ],
    },
    {
        "lexemeId": 166, "lemma": "puente", "pos": "noun", "gender": "M",
        "englishGloss": "bridge", "frequencyRank": 1325, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "directions and travel", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 directions/travel topic",
        "sentences": [
            (387, 390, "Cruzo el puente.", "I cross the bridge."),
            (388, 391, "El puente está cerca.", "The bridge is nearby."),
        ],
    },
]

AI_ACCELERATED_PACK_A2_007 = [
    {
        "lexemeId": 167, "lemma": "lavar", "pos": "verb", "gender": None,
        "englishGloss": "to wash", "frequencyRank": 1220, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "household and health routines", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 household/health topic",
        "sentences": [
            (393, 396, "Lavo la ropa.", "I wash the clothes."),
            (394, 397, "Lávate las manos.", "Wash your hands."),
        ],
    },
    {
        "lexemeId": 168, "lemma": "secar", "pos": "verb", "gender": None,
        "englishGloss": "to dry", "frequencyRank": 1785, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "household and health routines", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 household/health topic",
        "sentences": [
            (395, 398, "Seco los platos.", "I dry the dishes."),
            (396, 399, "Sécate el pelo.", "Dry your hair."),
        ],
    },
    {
        "lexemeId": 169, "lemma": "ordenar", "pos": "verb", "gender": None,
        "englishGloss": "to organize; to order", "frequencyRank": 1320, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "household and errands", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 household/services topic",
        "sentences": [
            (397, 400, "Ordeno la habitación.", "I organize the room."),
            (398, 401, "Ordenamos los papeles.", "We organize the papers."),
        ],
    },
    {
        "lexemeId": 170, "lemma": "recoger", "pos": "verb", "gender": None,
        "englishGloss": "to pick up; to collect", "frequencyRank": 1160, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "errands and household tasks", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 errands/household topic",
        "sentences": [
            (399, 402, "Recojo el paquete.", "I pick up the package."),
            (400, 403, "Recogemos la mesa.", "We clear the table."),
        ],
    },
    {
        "lexemeId": 171, "lemma": "tirar", "pos": "verb", "gender": None,
        "englishGloss": "to throw away; to pull", "frequencyRank": 980, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "household and problems", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 household topic",
        "sentences": [
            (401, 404, "Tiro la basura.", "I throw away the trash."),
            (402, 405, "No tires la receta.", "Do not throw away the recipe."),
        ],
    },
    {
        "lexemeId": 172, "lemma": "apagar", "pos": "verb", "gender": None,
        "englishGloss": "to turn off", "frequencyRank": 1500, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "household and services", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 household/services topic",
        "sentences": [
            (403, 406, "Apago la luz.", "I turn off the light."),
            (404, 407, "Apaga el teléfono.", "Turn off the phone."),
        ],
    },
    {
        "lexemeId": 173, "lemma": "encender", "pos": "verb", "gender": None,
        "englishGloss": "to turn on; to light", "frequencyRank": 1580, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "household and services", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 household/services topic",
        "sentences": [
            (405, 408, "Enciendo la cocina.", "I turn on the stove."),
            (406, 409, "Enciende la luz.", "Turn on the light."),
        ],
    },
    {
        "lexemeId": 174, "lemma": "reparar", "pos": "verb", "gender": None,
        "englishGloss": "to repair", "frequencyRank": 1700, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "services and problems", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 services/problems topic",
        "sentences": [
            (407, 410, "Reparo la mesa.", "I repair the table."),
            (408, 411, "Necesito reparar el coche.", "I need to repair the car."),
        ],
    },
    {
        "lexemeId": 175, "lemma": "atender", "pos": "verb", "gender": None,
        "englishGloss": "to attend to; to serve", "frequencyRank": 1360, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "services and appointments", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 services/appointments topic",
        "sentences": [
            (409, 412, "Atiendo a un cliente.", "I help a customer."),
            (410, 413, "El médico me atiende.", "The doctor sees me."),
        ],
    },
    {
        "lexemeId": 176, "lemma": "cobrar", "pos": "verb", "gender": None,
        "englishGloss": "to charge; to collect payment", "frequencyRank": 1525, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "services and money", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 services/money topic",
        "sentences": [
            (411, 414, "Cobran por el servicio.", "They charge for the service."),
            (412, 415, "¿Cuánto cobran?", "How much do they charge?"),
        ],
    },
    {
        "lexemeId": 177, "lemma": "firmar", "pos": "verb", "gender": None,
        "englishGloss": "to sign", "frequencyRank": 1450, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "appointments and services", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 services/work topic",
        "sentences": [
            (413, 416, "Firmo el papel.", "I sign the paper."),
            (414, 417, "Necesito firmar aquí.", "I need to sign here."),
        ],
    },
    {
        "lexemeId": 178, "lemma": "solicitar", "pos": "verb", "gender": None,
        "englishGloss": "to request; to apply for", "frequencyRank": 1830, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "requests and services", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 requests/services topic",
        "sentences": [
            (415, 418, "Solicito una cita.", "I request an appointment."),
            (416, 419, "Solicitamos ayuda.", "We request help."),
        ],
    },
    {
        "lexemeId": 179, "lemma": "aceptar", "pos": "verb", "gender": None,
        "englishGloss": "to accept", "frequencyRank": 980, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "requests and decisions", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 requests/opinions topic",
        "sentences": [
            (417, 420, "Acepto la oferta.", "I accept the offer."),
            (418, 421, "Aceptamos el plan.", "We accept the plan."),
        ],
    },
    {
        "lexemeId": 180, "lemma": "rechazar", "pos": "verb", "gender": None,
        "englishGloss": "to reject; to refuse", "frequencyRank": 1680, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "requests and complaints", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 requests/complaints topic",
        "sentences": [
            (419, 422, "Rechazo la oferta.", "I reject the offer."),
            (420, 423, "No quiero rechazar la ayuda.", "I do not want to refuse the help."),
        ],
    },
    {
        "lexemeId": 181, "lemma": "recomendar", "pos": "verb", "gender": None,
        "englishGloss": "to recommend", "frequencyRank": 1540, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "preferences and services", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 preferences/services topic",
        "sentences": [
            (421, 424, "Recomiendo este hotel.", "I recommend this hotel."),
            (422, 425, "El médico recomienda descansar.", "The doctor recommends resting."),
        ],
    },
    {
        "lexemeId": 182, "lemma": "prometer", "pos": "verb", "gender": None,
        "englishGloss": "to promise", "frequencyRank": 1465, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "plans and social commitments", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 plans/social topic",
        "sentences": [
            (423, 426, "Prometo llamar mañana.", "I promise to call tomorrow."),
            (424, 427, "Ella promete llegar temprano.", "She promises to arrive early."),
        ],
    },
    {
        "lexemeId": 183, "lemma": "planificar", "pos": "verb", "gender": None,
        "englishGloss": "to plan", "frequencyRank": 2100, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "plans and work", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 plans/work topic",
        "sentences": [
            (425, 428, "Planifico el viaje.", "I plan the trip."),
            (426, 429, "Planificamos la semana.", "We plan the week."),
        ],
    },
    {
        "lexemeId": 184, "lemma": "proponer", "pos": "verb", "gender": None,
        "englishGloss": "to propose; to suggest", "frequencyRank": 1620, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "opinions and plans", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 opinions/plans topic",
        "sentences": [
            (427, 430, "Propongo otra opción.", "I suggest another option."),
            (428, 431, "Proponemos un plan.", "We propose a plan."),
        ],
    },
    {
        "lexemeId": 185, "lemma": "justificar", "pos": "verb", "gender": None,
        "englishGloss": "to justify", "frequencyRank": 2050, "cefrBand": "B1", "difficultyPrior": 0.6,
        "reason": "reasons and explanations", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 reasons/opinions topic",
        "sentences": [
            (429, 432, "Justifico mi decisión.", "I justify my decision."),
            (430, 433, "No puedo justificar el precio.", "I cannot justify the price."),
        ],
    },
    {
        "lexemeId": 186, "lemma": "depender", "pos": "verb", "gender": None,
        "englishGloss": "to depend", "frequencyRank": 1180, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "reasons and conditions", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 reasons/plans topic",
        "sentences": [
            (431, 434, "Depende del tiempo.", "It depends on the weather."),
            (432, 435, "Todo depende de la cita.", "Everything depends on the appointment."),
        ],
    },
    {
        "lexemeId": 187, "lemma": "causar", "pos": "verb", "gender": None,
        "englishGloss": "to cause", "frequencyRank": 1060, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "reasons and problems", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 reasons/problems topic",
        "sentences": [
            (433, 436, "Eso causa problemas.", "That causes problems."),
            (434, 437, "El ruido causa dolor.", "The noise causes pain."),
        ],
    },
    {
        "lexemeId": 188, "lemma": "disfrutar", "pos": "verb", "gender": None,
        "englishGloss": "to enjoy", "frequencyRank": 1165, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "experiences and preferences", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 experiences/preferences topic",
        "sentences": [
            (435, 438, "Disfruto el viaje.", "I enjoy the trip."),
            (436, 439, "Disfrutamos la comida.", "We enjoy the food."),
        ],
    },
    {
        "lexemeId": 189, "lemma": "sufrir", "pos": "verb", "gender": None,
        "englishGloss": "to suffer", "frequencyRank": 1020, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "health and difficult experiences", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 health/experiences topic",
        "sentences": [
            (437, 440, "Sufro dolor.", "I suffer pain."),
            (438, 441, "Ella sufre mucho.", "She suffers a lot."),
        ],
    },
    {
        "lexemeId": 190, "lemma": "respirar", "pos": "verb", "gender": None,
        "englishGloss": "to breathe", "frequencyRank": 1600, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "health symptoms", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 health topic",
        "sentences": [
            (439, 442, "Respiro bien.", "I breathe well."),
            (440, 443, "No puedo respirar.", "I cannot breathe."),
        ],
    },
    {
        "lexemeId": 191, "lemma": "toser", "pos": "verb", "gender": None,
        "englishGloss": "to cough", "frequencyRank": 2300, "cefrBand": "B1", "difficultyPrior": 0.6,
        "reason": "health symptoms", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 health topic",
        "sentences": [
            (441, 444, "Toso mucho.", "I cough a lot."),
            (442, 445, "El niño tose.", "The boy coughs."),
        ],
    },
    {
        "lexemeId": 192, "lemma": "curar", "pos": "verb", "gender": None,
        "englishGloss": "to cure; to heal", "frequencyRank": 1705, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "health and recovery", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 health topic",
        "sentences": [
            (443, 446, "La medicina cura el dolor.", "The medicine cures the pain."),
            (444, 447, "Quiero curarme pronto.", "I want to get well soon."),
        ],
    },
    {
        "lexemeId": 193, "lemma": "medir", "pos": "verb", "gender": None,
        "englishGloss": "to measure", "frequencyRank": 1505, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "health and practical services", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 health/services topic",
        "sentences": [
            (445, 448, "Mido la mesa.", "I measure the table."),
            (446, 449, "El médico mide la presión.", "The doctor measures the blood pressure."),
        ],
    },
    {
        "lexemeId": 194, "lemma": "pesar", "pos": "verb", "gender": None,
        "englishGloss": "to weigh", "frequencyRank": 1585, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "health and shopping", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 health/shopping topic",
        "sentences": [
            (447, 450, "Peso la comida.", "I weigh the food."),
            (448, 451, "El paquete pesa mucho.", "The package weighs a lot."),
        ],
    },
    {
        "lexemeId": 195, "lemma": "alquilar", "pos": "verb", "gender": None,
        "englishGloss": "to rent", "frequencyRank": 1950, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "travel and services", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 travel/services topic",
        "sentences": [
            (449, 452, "Alquilo un coche.", "I rent a car."),
            (450, 453, "Queremos alquilar una casa.", "We want to rent a house."),
        ],
    },
    {
        "lexemeId": 196, "lemma": "conducir", "pos": "verb", "gender": None,
        "englishGloss": "to drive", "frequencyRank": 1040, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "travel and transport", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 travel/transport topic",
        "sentences": [
            (451, 454, "Conduzco al trabajo.", "I drive to work."),
            (452, 455, "Ella conduce bien.", "She drives well."),
        ],
    },
    {
        "lexemeId": 197, "lemma": "alojarse", "pos": "verb", "gender": None,
        "englishGloss": "to stay; to lodge", "frequencyRank": 2400, "cefrBand": "B1", "difficultyPrior": 0.6,
        "reason": "travel lodging", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 travel topic",
        "sentences": [
            (453, 456, "Me alojo en el hotel.", "I stay at the hotel."),
            (454, 457, "Nos alojamos cerca.", "We stay nearby."),
        ],
    },
    {
        "lexemeId": 198, "lemma": "embarcar", "pos": "verb", "gender": None,
        "englishGloss": "to board", "frequencyRank": 2600, "cefrBand": "B1", "difficultyPrior": 0.6,
        "reason": "travel transit", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 travel topic",
        "sentences": [
            (455, 458, "Embarco a tiempo.", "I board on time."),
            (456, 459, "Embarcamos en la puerta.", "We board at the gate."),
        ],
    },
    {
        "lexemeId": 199, "lemma": "aterrizar", "pos": "verb", "gender": None,
        "englishGloss": "to land", "frequencyRank": 2550, "cefrBand": "B1", "difficultyPrior": 0.6,
        "reason": "travel transit", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 travel topic",
        "sentences": [
            (457, 460, "El avión aterriza tarde.", "The plane lands late."),
            (458, 461, "Aterrizamos en Madrid.", "We land in Madrid."),
        ],
    },
    {
        "lexemeId": 200, "lemma": "facturar", "pos": "verb", "gender": None,
        "englishGloss": "to check in; to invoice", "frequencyRank": 2500, "cefrBand": "B1", "difficultyPrior": 0.6,
        "reason": "travel and services", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 travel/services topic",
        "sentences": [
            (459, 462, "Facturo mi maleta.", "I check in my suitcase."),
            (460, 463, "Necesito facturar ahora.", "I need to check in now."),
        ],
    },
    {
        "lexemeId": 201, "lemma": "contratar", "pos": "verb", "gender": None,
        "englishGloss": "to hire; to contract", "frequencyRank": 1455, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "work and services", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 work/services topic",
        "sentences": [
            (461, 464, "Contratan a mi amigo.", "They hire my friend."),
            (462, 465, "Quiero contratar un servicio.", "I want to hire a service."),
        ],
    },
    {
        "lexemeId": 202, "lemma": "ahorrar", "pos": "verb", "gender": None,
        "englishGloss": "to save money", "frequencyRank": 1850, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "work and money plans", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 work/money topic",
        "sentences": [
            (463, 466, "Ahorro dinero.", "I save money."),
            (464, 467, "Queremos ahorrar más.", "We want to save more."),
        ],
    },
    {
        "lexemeId": 203, "lemma": "ganar", "pos": "verb", "gender": None,
        "englishGloss": "to earn; to win", "frequencyRank": 588, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "work and outcomes", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (465, 468, "Gano dinero.", "I earn money."),
            (466, 469, "Queremos ganar el partido.", "We want to win the game."),
        ],
    },
    {
        "lexemeId": 204, "lemma": "disponible", "pos": "adjective", "gender": None,
        "englishGloss": "available", "frequencyRank": 1250, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "appointments and services", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 appointments/services topic",
        "sentences": [
            (467, 470, "Estoy disponible mañana.", "I am available tomorrow."),
            (468, 471, "La cita está disponible.", "The appointment is available."),
        ],
    },
    {
        "lexemeId": 205, "lemma": "cómodo", "pos": "adjective", "gender": None,
        "englishGloss": "comfortable", "frequencyRank": 1365, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "travel and household preferences", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 travel/household topic",
        "sentences": [
            (469, 472, "El hotel es cómodo.", "The hotel is comfortable."),
            (470, 473, "La silla es cómoda.", "The chair is comfortable."),
        ],
    },
    {
        "lexemeId": 206, "lemma": "tranquilo", "pos": "adjective", "gender": None,
        "englishGloss": "calm; quiet", "frequencyRank": 1185, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "emotions and places", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 emotions/household topic",
        "sentences": [
            (471, 474, "Estoy tranquilo.", "I am calm."),
            (472, 475, "La calle está tranquila.", "The street is quiet."),
        ],
    },
    {
        "lexemeId": 207, "lemma": "preocupado", "pos": "adjective", "gender": None,
        "englishGloss": "worried", "frequencyRank": 1325, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "emotions and problems", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 emotions/problems topic",
        "sentences": [
            (473, 476, "Estoy preocupado.", "I am worried."),
            (474, 477, "Ella está preocupada por la cita.", "She is worried about the appointment."),
        ],
    },
    {
        "lexemeId": 208, "lemma": "satisfecho", "pos": "adjective", "gender": None,
        "englishGloss": "satisfied", "frequencyRank": 1625, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "preferences and services", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 services/opinions topic",
        "sentences": [
            (475, 478, "Estoy satisfecho.", "I am satisfied."),
            (476, 479, "Estamos satisfechos con el servicio.", "We are satisfied with the service."),
        ],
    },
    {
        "lexemeId": 209, "lemma": "amable", "pos": "adjective", "gender": None,
        "englishGloss": "kind; friendly", "frequencyRank": 1435, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "social and service interactions", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 social/services topic",
        "sentences": [
            (477, 480, "El médico es amable.", "The doctor is kind."),
            (478, 481, "La persona fue amable.", "The person was friendly."),
        ],
    },
    {
        "lexemeId": 210, "lemma": "reciente", "pos": "adjective", "gender": None,
        "englishGloss": "recent", "frequencyRank": 1180, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "experiences and work updates", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 experiences/work topic",
        "sentences": [
            (479, 482, "Es una experiencia reciente.", "It is a recent experience."),
            (480, 483, "El cambio es reciente.", "The change is recent."),
        ],
    },
    {
        "lexemeId": 211, "lemma": "común", "pos": "adjective", "gender": None,
        "englishGloss": "common", "frequencyRank": 520, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "reasons and explanations", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (481, 484, "Es un problema común.", "It is a common problem."),
            (482, 485, "Es una razón común.", "It is a common reason."),
        ],
    },
    {
        "lexemeId": 212, "lemma": "experiencia", "pos": "noun", "gender": "F",
        "englishGloss": "experience", "frequencyRank": 555, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "experiences and opinions", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (483, 486, "Tengo experiencia.", "I have experience."),
            (484, 487, "Fue una buena experiencia.", "It was a good experience."),
        ],
    },
    {
        "lexemeId": 213, "lemma": "plan", "pos": "noun", "gender": "M",
        "englishGloss": "plan", "frequencyRank": 705, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "plans and decisions", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 plans topic",
        "sentences": [
            (485, 488, "Tengo un plan.", "I have a plan."),
            (486, 489, "El plan cambia.", "The plan changes."),
        ],
    },
    {
        "lexemeId": 214, "lemma": "razón", "pos": "noun", "gender": "F",
        "englishGloss": "reason", "frequencyRank": 515, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "reasons and explanations", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine",
        "sentences": [
            (487, 490, "Tengo una razón.", "I have a reason."),
            (488, 491, "La razón es simple.", "The reason is simple."),
        ],
    },
    {
        "lexemeId": 215, "lemma": "solicitud", "pos": "noun", "gender": "F",
        "englishGloss": "request; application", "frequencyRank": 1855, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "requests and services", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 requests/services topic",
        "sentences": [
            (489, 492, "Envío la solicitud.", "I send the request."),
            (490, 493, "La solicitud está lista.", "The application is ready."),
        ],
    },
    {
        "lexemeId": 216, "lemma": "queja", "pos": "noun", "gender": "F",
        "englishGloss": "complaint", "frequencyRank": 1900, "cefrBand": "B1", "difficultyPrior": 0.5,
        "reason": "complaints and services", "sourceBasis": "SPANISH_BREADTH_PLAN.md B1 complaints/services topic",
        "sentences": [
            (491, 494, "Tengo una queja.", "I have a complaint."),
            (492, 495, "La queja es sobre el servicio.", "The complaint is about the service."),
        ],
    },
]


def build_ai_accelerated_pack(items):
    return [
        {
            "lexemeId": lexeme_id,
            "lemma": lemma,
            "pos": pos,
            "gender": gender,
            "englishGloss": english_gloss,
            "frequencyRank": frequency_rank,
            "cefrBand": cefr_band,
            "difficultyPrior": difficulty_prior,
            "reason": reason,
            "sourceBasis": source_basis,
            "sentences": sentences,
        }
        for (
            lexeme_id, lemma, pos, gender, english_gloss, frequency_rank, cefr_band,
            difficulty_prior, reason, source_basis, sentences,
        ) in items
    ]


def build_numbered_ai_accelerated_pack(start_lexeme_id, start_sentence_id, start_answer_id, specs):
    items = []
    for offset, (
        lemma, pos, gender, english_gloss, frequency_rank, cefr_band, difficulty_prior,
        reason, source_basis, sentence_pairs,
    ) in enumerate(specs):
        if len(sentence_pairs) != 2:
            raise ValueError(f"{lemma} must define exactly two reviewed sentence pairs")
        sentence_id = start_sentence_id + offset * 2
        answer_id = start_answer_id + offset * 2
        items.append((
            start_lexeme_id + offset, lemma, pos, gender, english_gloss, frequency_rank, cefr_band,
            difficulty_prior, reason, source_basis,
            [
                (sentence_id, answer_id, sentence_pairs[0][0], sentence_pairs[0][1]),
                (sentence_id + 1, answer_id + 1, sentence_pairs[1][0], sentence_pairs[1][1]),
            ],
        ))
    return build_ai_accelerated_pack(items)


AI_ACCELERATED_PACK_A2_008 = build_ai_accelerated_pack([
    (217, "alegrarse", "verb", None, "to be glad", 1850, "B1", 0.5, "feelings", "SPANISH_BREADTH_PLAN.md B1 feelings topic", [(493, 496, "Me alegro por ti.", "I am happy for you."), (494, 497, "Nos alegramos de verte.", "We are glad to see you.")]),
    (218, "enfadarse", "verb", None, "to get angry", 1900, "B1", 0.5, "feelings and conflict", "SPANISH_BREADTH_PLAN.md B1 feelings/conflict topic", [(495, 498, "Me enfado con el servicio.", "I get angry with the service."), (496, 499, "No quiero enfadarme.", "I do not want to get angry.")]),
    (219, "asustarse", "verb", None, "to get scared", 2100, "B1", 0.6, "feelings and medical situations", "SPANISH_BREADTH_PLAN.md B1 feelings/medical topic", [(497, 500, "Me asusto fácilmente.", "I get scared easily."), (498, 501, "El niño se asusta.", "The boy gets scared.")]),
    (220, "animar", "verb", None, "to encourage; to cheer up", 1600, "B1", 0.5, "feelings and advice", "SPANISH_BREADTH_PLAN.md B1 advice/feelings topic", [(499, 502, "Animo a mi amigo.", "I encourage my friend."), (500, 503, "Ella me anima mucho.", "She encourages me a lot.")]),
    (221, "calmar", "verb", None, "to calm", 1700, "B1", 0.5, "feelings and conflict", "SPANISH_BREADTH_PLAN.md B1 feelings/conflict topic", [(501, 504, "Calmo al niño.", "I calm the boy."), (502, 505, "Necesito calmarme.", "I need to calm down.")]),
    (222, "obligar", "verb", None, "to oblige; to force", 1320, "B1", 0.5, "obligations", "SPANISH_BREADTH_PLAN.md B1 obligations topic", [(503, 506, "Me obligan a esperar.", "They make me wait."), (504, 507, "No quiero obligarte.", "I do not want to force you.")]),
    (223, "permitir", "verb", None, "to allow", 760, "B1", 0.5, "permission and obligations", "hermitdave/FrequencyWords high-frequency spine", [(505, 508, "Permiten entrar ahora.", "They allow entry now."), (506, 509, "No me permite salir.", "He does not allow me to leave.")]),
    (224, "aconsejar", "verb", None, "to advise", 1750, "B1", 0.5, "advice", "SPANISH_BREADTH_PLAN.md B1 advice topic", [(507, 510, "Te aconsejo descansar.", "I advise you to rest."), (508, 511, "El médico aconseja caminar.", "The doctor advises walking.")]),
    (225, "advertir", "verb", None, "to warn", 1500, "B1", 0.5, "advice and problems", "SPANISH_BREADTH_PLAN.md B1 advice/problems topic", [(509, 512, "Te advierto del problema.", "I warn you about the problem."), (510, 513, "Nos advierten del retraso.", "They warn us about the delay.")]),
    (226, "insistir", "verb", None, "to insist", 1250, "B1", 0.5, "requests and conflict", "SPANISH_BREADTH_PLAN.md B1 requests/conflict topic", [(511, 514, "Insisto en pagar.", "I insist on paying."), (512, 515, "Ella insiste en llamar.", "She insists on calling.")]),
    (227, "comparar", "verb", None, "to compare", 1420, "B1", 0.5, "comparisons", "SPANISH_BREADTH_PLAN.md B1 comparisons topic", [(513, 516, "Comparo los precios.", "I compare the prices."), (514, 517, "Comparamos dos hoteles.", "We compare two hotels.")]),
    (228, "superar", "verb", None, "to overcome; to exceed", 1180, "B1", 0.5, "experiences and problems", "SPANISH_BREADTH_PLAN.md B1 experiences/problems topic", [(515, 518, "Supero el problema.", "I overcome the problem."), (516, 519, "Queremos superar esto.", "We want to overcome this.")]),
    (229, "adaptarse", "verb", None, "to adapt", 1800, "B1", 0.5, "planning and experiences", "SPANISH_BREADTH_PLAN.md B1 experiences/planning topic", [(517, 520, "Me adapto al cambio.", "I adapt to the change."), (518, 521, "Nos adaptamos rápido.", "We adapt quickly.")]),
    (230, "organizar", "verb", None, "to organize", 1100, "B1", 0.5, "planning and work", "SPANISH_BREADTH_PLAN.md B1 planning/work topic", [(519, 522, "Organizo la reunión.", "I organize the meeting."), (520, 523, "Organizamos el viaje.", "We organize the trip.")]),
    (231, "programar", "verb", None, "to schedule; to program", 1500, "B1", 0.5, "appointments and planning", "SPANISH_BREADTH_PLAN.md B1 appointments/planning topic", [(521, 524, "Programo una cita.", "I schedule an appointment."), (522, 525, "Programamos la visita.", "We schedule the visit.")]),
    (232, "aplazar", "verb", None, "to postpone", 2200, "B1", 0.6, "appointments and planning", "SPANISH_BREADTH_PLAN.md B1 appointments/planning topic", [(523, 526, "Aplazo la cita.", "I postpone the appointment."), (524, 527, "Necesito aplazar el viaje.", "I need to postpone the trip.")]),
    (233, "anticipar", "verb", None, "to anticipate", 1600, "B1", 0.5, "planning and problems", "SPANISH_BREADTH_PLAN.md B1 planning/problems topic", [(525, 528, "Anticipo un problema.", "I anticipate a problem."), (526, 529, "Anticipamos un retraso.", "We anticipate a delay.")]),
    (234, "coordinar", "verb", None, "to coordinate", 1750, "B1", 0.5, "planning and work", "SPANISH_BREADTH_PLAN.md B1 planning/work topic", [(527, 530, "Coordino el trabajo.", "I coordinate the work."), (528, 531, "Coordinamos la reunión.", "We coordinate the meeting.")]),
    (235, "discutir", "verb", None, "to discuss; to argue", 1050, "B1", 0.5, "conflict and opinions", "SPANISH_BREADTH_PLAN.md B1 conflict/opinions topic", [(529, 532, "Discutimos el problema.", "We discuss the problem."), (530, 533, "No quiero discutir.", "I do not want to argue.")]),
    (236, "negociar", "verb", None, "to negotiate", 1700, "B1", 0.5, "conflict and services", "SPANISH_BREADTH_PLAN.md B1 conflict/services topic", [(531, 534, "Negocio el precio.", "I negotiate the price."), (532, 535, "Negociamos con el banco.", "We negotiate with the bank.")]),
    (237, "acordar", "verb", None, "to agree; to arrange", 930, "B1", 0.5, "conflict and planning", "SPANISH_BREADTH_PLAN.md B1 conflict/planning topic", [(533, 536, "Acordamos una hora.", "We agree on a time."), (534, 537, "Quiero acordar un plan.", "I want to agree on a plan.")]),
    (238, "romper", "verb", None, "to break", 880, "B1", 0.5, "repairs and problems", "SPANISH_BREADTH_PLAN.md B1 repairs/problems topic", [(535, 538, "Rompo el vaso.", "I break the glass."), (536, 539, "La silla se rompe.", "The chair breaks.")]),
    (239, "dañar", "verb", None, "to damage", 1700, "B1", 0.5, "repairs and problems", "SPANISH_BREADTH_PLAN.md B1 repairs/problems topic", [(537, 540, "Dañan la puerta.", "They damage the door."), (538, 541, "No quiero dañar el coche.", "I do not want to damage the car.")]),
    (240, "instalar", "verb", None, "to install", 1300, "B1", 0.5, "repairs and services", "SPANISH_BREADTH_PLAN.md B1 repairs/services topic", [(539, 542, "Instalo la aplicación.", "I install the app."), (540, 543, "Instalan una ventana.", "They install a window.")]),
    (241, "reemplazar", "verb", None, "to replace", 2100, "B1", 0.6, "repairs and services", "SPANISH_BREADTH_PLAN.md B1 repairs/services topic", [(541, 544, "Reemplazo la llave.", "I replace the key."), (542, 545, "Necesito reemplazar la tarjeta.", "I need to replace the card.")]),
    (242, "revisar", "verb", None, "to review; to check", 1100, "B1", 0.5, "services and medical checks", "SPANISH_BREADTH_PLAN.md B1 medical/services topic", [(543, 546, "Reviso la factura.", "I check the bill."), (544, 547, "El médico revisa la receta.", "The doctor reviews the prescription.")]),
    (243, "examinar", "verb", None, "to examine", 1500, "B1", 0.5, "medical", "SPANISH_BREADTH_PLAN.md B1 medical topic", [(545, 548, "El médico examina mi mano.", "The doctor examines my hand."), (546, 549, "Necesito examinar el problema.", "I need to examine the problem.")]),
    (244, "recetar", "verb", None, "to prescribe", 2300, "B1", 0.6, "medical", "SPANISH_BREADTH_PLAN.md B1 medical topic", [(547, 550, "El médico receta medicina.", "The doctor prescribes medicine."), (548, 551, "Me recetan descanso.", "They prescribe rest for me.")]),
    (245, "vacunarse", "verb", None, "to get vaccinated", 2600, "B1", 0.6, "medical", "SPANISH_BREADTH_PLAN.md B1 medical topic", [(549, 552, "Me vacuno hoy.", "I get vaccinated today."), (550, 553, "Necesito vacunarme.", "I need to get vaccinated.")]),
    (246, "sangrar", "verb", None, "to bleed", 2400, "B1", 0.6, "medical", "SPANISH_BREADTH_PLAN.md B1 medical topic", [(551, 554, "Me sangra la mano.", "My hand is bleeding."), (552, 555, "La herida sangra.", "The wound bleeds.")]),
    (247, "depositar", "verb", None, "to deposit", 1900, "B1", 0.5, "banking", "SPANISH_BREADTH_PLAN.md B1 banking topic", [(553, 556, "Deposito dinero.", "I deposit money."), (554, 557, "Deposito el cheque en el banco.", "I deposit the check at the bank.")]),
    (248, "retirar", "verb", None, "to withdraw; to remove", 1200, "B1", 0.5, "banking and services", "SPANISH_BREADTH_PLAN.md B1 banking/services topic", [(555, 558, "Retiro dinero.", "I withdraw money."), (556, 559, "Retiro la solicitud.", "I withdraw the application.")]),
    (249, "transferir", "verb", None, "to transfer", 1700, "B1", 0.5, "banking", "SPANISH_BREADTH_PLAN.md B1 banking topic", [(557, 560, "Transfiero dinero.", "I transfer money."), (558, 561, "Transferimos el pago.", "We transfer the payment.")]),
    (250, "prestar", "verb", None, "to lend", 1250, "B1", 0.5, "banking and requests", "SPANISH_BREADTH_PLAN.md B1 banking/requests topic", [(559, 562, "Presto dinero a mi amigo.", "I lend money to my friend."), (560, 563, "¿Puedes prestarme la tarjeta?", "Can you lend me the card?")]),
    (251, "abonar", "verb", None, "to pay; to credit", 2050, "B1", 0.6, "banking and services", "SPANISH_BREADTH_PLAN.md B1 banking/services topic", [(561, 564, "Abono la factura.", "I pay the bill."), (562, 565, "Abonamos con tarjeta.", "We pay by card.")]),
    (252, "mudarse", "verb", None, "to move house", 2200, "B1", 0.6, "lodging and household", "SPANISH_BREADTH_PLAN.md B1 lodging/household topic", [(563, 566, "Me mudo mañana.", "I move tomorrow."), (564, 567, "Nos mudamos a otra casa.", "We move to another house.")]),
    (253, "registrarse", "verb", None, "to register; to check in", 2100, "B1", 0.6, "lodging and services", "SPANISH_BREADTH_PLAN.md B1 lodging/services topic", [(565, 568, "Me registro en el hotel.", "I check in at the hotel."), (566, 569, "Necesito registrarme.", "I need to register.")]),
    (254, "reclamar", "verb", None, "to claim; to complain", 1500, "B1", 0.5, "complaints and services", "SPANISH_BREADTH_PLAN.md B1 complaints/services topic", [(567, 570, "Reclamo mi equipaje.", "I claim my luggage."), (568, 571, "Quiero reclamar el pago.", "I want to dispute the payment.")]),
    (255, "transbordar", "verb", None, "to transfer vehicles", 2600, "B1", 0.6, "transit", "SPANISH_BREADTH_PLAN.md B1 transit topic", [(569, 572, "Transbordo en la estación.", "I transfer at the station."), (570, 573, "Necesitamos transbordar aquí.", "We need to transfer here.")]),
    (256, "abordar", "verb", None, "to board", 1800, "B1", 0.5, "transit", "SPANISH_BREADTH_PLAN.md B1 transit topic", [(571, 574, "Abordo el tren.", "I board the train."), (572, 575, "Abordamos a tiempo.", "We board on time.")]),
    (257, "obligatorio", "adjective", None, "required; mandatory", 1700, "B1", 0.5, "obligations", "SPANISH_BREADTH_PLAN.md B1 obligations topic", [(573, 576, "El seguro es obligatorio.", "Insurance is required."), (574, 577, "La cita no es obligatoria.", "The appointment is not mandatory.")]),
    (258, "recomendable", "adjective", None, "recommended; advisable", 2200, "B1", 0.6, "advice", "SPANISH_BREADTH_PLAN.md B1 advice topic", [(575, 578, "Es recomendable descansar.", "It is advisable to rest."), (576, 579, "No es recomendable esperar.", "It is not advisable to wait.")]),
    (259, "comparable", "adjective", None, "comparable", 2400, "B1", 0.6, "comparisons", "SPANISH_BREADTH_PLAN.md B1 comparisons topic", [(577, 580, "Los precios son comparables.", "The prices are comparable."), (578, 581, "No es comparable.", "It is not comparable.")]),
    (260, "pendiente", "adjective", None, "pending", 1200, "B1", 0.5, "planning and services", "SPANISH_BREADTH_PLAN.md B1 planning/services topic", [(579, 582, "La solicitud está pendiente.", "The request is pending."), (580, 583, "Tengo una factura pendiente.", "I have a pending bill.")]),
    (261, "mensual", "adjective", None, "monthly", 1600, "B1", 0.5, "banking and planning", "SPANISH_BREADTH_PLAN.md B1 banking/planning topic", [(581, 584, "Es un pago mensual.", "It is a monthly payment."), (582, 585, "La factura es mensual.", "The bill is monthly.")]),
    (262, "temporal", "adjective", None, "temporary", 1300, "B1", 0.5, "lodging and work", "SPANISH_BREADTH_PLAN.md B1 lodging/work topic", [(583, 586, "Es un trabajo temporal.", "It is a temporary job."), (584, 587, "El cambio es temporal.", "The change is temporary.")]),
    (263, "doloroso", "adjective", None, "painful", 2100, "B1", 0.6, "medical and feelings", "SPANISH_BREADTH_PLAN.md B1 medical/feelings topic", [(585, 588, "Es doloroso.", "It is painful."), (586, 589, "La herida es dolorosa.", "The wound is painful.")]),
    (264, "descontento", "adjective", None, "dissatisfied", 2300, "B1", 0.6, "complaints and services", "SPANISH_BREADTH_PLAN.md B1 complaints/services topic", [(587, 590, "Estoy descontento.", "I am dissatisfied."), (588, 591, "Estamos descontentos con el servicio.", "We are dissatisfied with the service.")]),
    (265, "obligación", "noun", "F", "obligation", 1300, "B1", 0.5, "obligations", "SPANISH_BREADTH_PLAN.md B1 obligations topic", [(589, 592, "Tengo una obligación.", "I have an obligation."), (590, 593, "Es una obligación importante.", "It is an important obligation.")]),
    (266, "consejo", "noun", "M", "advice", 1150, "B1", 0.5, "advice", "SPANISH_BREADTH_PLAN.md B1 advice topic", [(591, 594, "Necesito un consejo.", "I need advice."), (592, 595, "El consejo es bueno.", "The advice is good.")]),
    (267, "conflicto", "noun", "M", "conflict", 1200, "B1", 0.5, "conflict", "SPANISH_BREADTH_PLAN.md B1 conflict topic", [(593, 596, "Hay un conflicto.", "There is a conflict."), (594, 597, "El conflicto termina hoy.", "The conflict ends today.")]),
    (268, "reparación", "noun", "F", "repair", 1750, "B1", 0.5, "repairs", "SPANISH_BREADTH_PLAN.md B1 repairs topic", [(595, 598, "La reparación cuesta mucho.", "The repair costs a lot."), (596, 599, "Necesito una reparación.", "I need a repair.")]),
    (269, "factura", "noun", "F", "bill; invoice", 1350, "B1", 0.5, "banking and services", "SPANISH_BREADTH_PLAN.md B1 banking/services topic", [(597, 600, "Pago la factura.", "I pay the bill."), (598, 601, "La factura está pendiente.", "The bill is pending.")]),
    (270, "cuenta", "noun", "F", "account; bill", 650, "B1", 0.5, "banking", "hermitdave/FrequencyWords high-frequency spine", [(599, 602, "Abro una cuenta.", "I open an account."), (600, 603, "La cuenta está activa.", "The account is active.")]),
    (271, "banco", "noun", "M", "bank", 650, "B1", 0.5, "banking", "hermitdave/FrequencyWords high-frequency spine", [(601, 604, "Voy al banco.", "I go to the bank."), (602, 605, "El banco abre temprano.", "The bank opens early.")]),
    (272, "tarjeta", "noun", "F", "card", 900, "B1", 0.5, "banking and services", "SPANISH_BREADTH_PLAN.md B1 banking/services topic", [(603, 606, "Pago con tarjeta.", "I pay with a card."), (604, 607, "Pierdo mi tarjeta.", "I lose my card.")]),
    (273, "habitación", "noun", "F", "room", 1250, "B1", 0.5, "lodging", "SPANISH_BREADTH_PLAN.md B1 lodging topic", [(605, 608, "Quiero una habitación.", "I want a room."), (606, 609, "La habitación es cómoda.", "The room is comfortable.")]),
    (274, "equipaje", "noun", "M", "luggage", 1800, "B1", 0.5, "travel", "SPANISH_BREADTH_PLAN.md B1 travel topic", [(607, 610, "Recojo mi equipaje.", "I pick up my luggage."), (608, 611, "Facturo el equipaje.", "I check in the luggage.")]),
    (275, "estación", "noun", "F", "station", 970, "B1", 0.5, "transit", "SPANISH_BREADTH_PLAN.md B1 transit topic", [(609, 612, "La estación está cerca.", "The station is nearby."), (610, 613, "Busco la estación.", "I look for the station.")]),
    (276, "emergencia", "noun", "F", "emergency", 1450, "B1", 0.5, "medical and services", "SPANISH_BREADTH_PLAN.md B1 medical/services topic", [(611, 614, "Es una emergencia.", "It is an emergency."), (612, 615, "Llamo por una emergencia.", "I call about an emergency.")]),
])


AI_ACCELERATED_PACK_A2_009 = build_ai_accelerated_pack([
    (277, "contar", "verb", None, "to tell; to count", 620, "B1", 0.5, "narration and social interaction", "hermitdave/FrequencyWords high-frequency spine", [(613, 616, "Te cuento la historia.", "I tell you the story."), (614, 617, "Contamos lo que pasó.", "We tell what happened.")]),
    (278, "narrar", "verb", None, "to narrate", 2600, "B1", 0.6, "narration", "SPANISH_BREADTH_PLAN.md B1 narration topic", [(615, 618, "Narro mi experiencia.", "I narrate my experience."), (616, 619, "Ella narra el viaje.", "She narrates the trip.")]),
    (279, "describir", "verb", None, "to describe", 1350, "B1", 0.5, "narration and health", "SPANISH_BREADTH_PLAN.md B1 narration/health topic", [(617, 620, "Describo el problema.", "I describe the problem."), (618, 621, "Él describe sus síntomas.", "He describes his symptoms.")]),
    (280, "mencionar", "verb", None, "to mention", 1500, "B1", 0.5, "opinions and workplace", "SPANISH_BREADTH_PLAN.md B1 opinions/workplace topic", [(619, 622, "Menciono la reunión.", "I mention the meeting."), (620, 623, "No mencionan el precio.", "They do not mention the price.")]),
    (281, "ocurrir", "verb", None, "to happen", 760, "B1", 0.5, "narration and past events", "hermitdave/FrequencyWords high-frequency spine", [(621, 624, "Ocurre un cambio.", "A change happens."), (622, 625, "¿Qué ocurrió ayer?", "What happened yesterday?")]),
    (282, "suceder", "verb", None, "to happen", 900, "B1", 0.5, "narration and past events", "hermitdave/FrequencyWords high-frequency spine", [(623, 626, "Sucede algo importante.", "Something important happens."), (624, 627, "Eso sucedió antes.", "That happened before.")]),
    (283, "continuar", "verb", None, "to continue", 800, "B1", 0.5, "planning and work", "hermitdave/FrequencyWords high-frequency spine", [(625, 628, "Continúo el trabajo.", "I continue the work."), (626, 629, "Continuamos mañana.", "We continue tomorrow.")]),
    (284, "avanzar", "verb", None, "to advance; to make progress", 1250, "B1", 0.5, "planning and workplace", "SPANISH_BREADTH_PLAN.md B1 planning/workplace topic", [(627, 630, "Avanzo con el proyecto.", "I make progress on the project."), (628, 631, "El plan avanza rápido.", "The plan moves forward quickly.")]),
    (285, "retrasar", "verb", None, "to delay", 1700, "B1", 0.5, "planning and transit", "SPANISH_BREADTH_PLAN.md B1 planning/transit topic", [(629, 632, "Retraso la cita.", "I delay the appointment."), (630, 633, "El tren se retrasa.", "The train is delayed.")]),
    (286, "finalizar", "verb", None, "to finish; to end", 1450, "B1", 0.5, "workplace and planning", "SPANISH_BREADTH_PLAN.md B1 workplace/planning topic", [(631, 634, "Finalizo el informe.", "I finish the report."), (632, 635, "La reunión finaliza tarde.", "The meeting ends late.")]),
    (287, "lograr", "verb", None, "to manage; to achieve", 850, "B1", 0.5, "planning and outcomes", "hermitdave/FrequencyWords high-frequency spine", [(633, 636, "Logro entenderlo.", "I manage to understand it."), (634, 637, "Queremos lograr el objetivo.", "We want to achieve the goal.")]),
    (288, "intentar", "verb", None, "to try", 900, "B1", 0.5, "planning and problem solving", "hermitdave/FrequencyWords high-frequency spine", [(635, 638, "Intento llamar.", "I try to call."), (636, 639, "Intentamos resolverlo.", "We try to solve it.")]),
    (289, "prever", "verb", None, "to foresee; to expect", 1900, "B1", 0.5, "future planning", "SPANISH_BREADTH_PLAN.md B1 future planning topic", [(637, 640, "Preveo un problema.", "I foresee a problem."), (638, 641, "Prevemos más trabajo.", "We expect more work.")]),
    (290, "evaluar", "verb", None, "to evaluate", 1800, "B1", 0.5, "workplace and services", "SPANISH_BREADTH_PLAN.md B1 workplace/services topic", [(639, 642, "Evalúo la situación.", "I evaluate the situation."), (640, 643, "Evalúan el servicio.", "They evaluate the service.")]),
    (291, "analizar", "verb", None, "to analyze", 1500, "B1", 0.5, "workplace and opinions", "SPANISH_BREADTH_PLAN.md B1 workplace/opinions topic", [(641, 644, "Analizo los datos.", "I analyze the data."), (642, 645, "Analizamos la respuesta.", "We analyze the response.")]),
    (292, "resumir", "verb", None, "to summarize", 2100, "B1", 0.6, "narration and workplace", "SPANISH_BREADTH_PLAN.md B1 narration/workplace topic", [(643, 646, "Resumo el informe.", "I summarize the report."), (644, 647, "Él resume la historia.", "He summarizes the story.")]),
    (293, "presentar", "verb", None, "to present; to submit", 700, "B1", 0.5, "workplace and services", "hermitdave/FrequencyWords high-frequency spine", [(645, 648, "Presento el proyecto.", "I present the project."), (646, 649, "Ella presenta una queja.", "She files a complaint.")]),
    (294, "participar", "verb", None, "to participate", 1100, "B1", 0.5, "workplace and social interaction", "SPANISH_BREADTH_PLAN.md B1 workplace/social topic", [(647, 650, "Participo en la reunión.", "I participate in the meeting."), (648, 651, "Participamos en el curso.", "We participate in the course.")]),
    (295, "colaborar", "verb", None, "to collaborate", 1800, "B1", 0.5, "workplace and social interaction", "SPANISH_BREADTH_PLAN.md B1 workplace/social topic", [(649, 652, "Colaboro con mi equipo.", "I collaborate with my team."), (650, 653, "Colaboramos en el proyecto.", "We collaborate on the project.")]),
    (296, "reunirse", "verb", None, "to meet", 1250, "B1", 0.5, "workplace and social interaction", "SPANISH_BREADTH_PLAN.md B1 workplace/social topic", [(651, 654, "Me reúno con el jefe.", "I meet with the boss."), (652, 655, "Nos reunimos mañana.", "We meet tomorrow.")]),
    (297, "entrevistar", "verb", None, "to interview", 2300, "B1", 0.6, "workplace", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [(653, 656, "Entrevisto al candidato.", "I interview the candidate."), (654, 657, "Me entrevistan hoy.", "They interview me today.")]),
    (298, "capacitar", "verb", None, "to train", 2400, "B1", 0.6, "workplace", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [(655, 658, "Capacito al equipo.", "I train the team."), (656, 659, "La empresa capacita al personal.", "The company trains the staff.")]),
    (299, "ascender", "verb", None, "to be promoted; to rise", 2200, "B1", 0.6, "workplace", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [(657, 660, "Asciendo en el trabajo.", "I get promoted at work."), (658, 661, "Ella asciende este año.", "She is promoted this year.")]),
    (300, "renunciar", "verb", None, "to resign; to give up", 1900, "B1", 0.5, "workplace and decisions", "SPANISH_BREADTH_PLAN.md B1 workplace/decisions topic", [(659, 662, "Renuncio al puesto.", "I resign from the position."), (660, 663, "No quiero renunciar.", "I do not want to resign.")]),
    (301, "consultar", "verb", None, "to consult; to check", 1100, "B1", 0.5, "health and services", "SPANISH_BREADTH_PLAN.md B1 health/services topic", [(661, 664, "Consulto al médico.", "I consult the doctor."), (662, 665, "Consultamos el horario.", "We check the schedule.")]),
    (302, "comunicar", "verb", None, "to communicate", 1200, "B1", 0.5, "workplace and services", "SPANISH_BREADTH_PLAN.md B1 workplace/services topic", [(663, 666, "Comunico la decisión.", "I communicate the decision."), (664, 667, "Nos comunican el cambio.", "They inform us of the change.")]),
    (303, "informar", "verb", None, "to inform", 850, "B1", 0.5, "workplace and services", "hermitdave/FrequencyWords high-frequency spine", [(665, 668, "Informo al cliente.", "I inform the customer."), (666, 669, "Nos informan del retraso.", "They inform us about the delay.")]),
    (304, "saludar", "verb", None, "to greet", 1900, "B1", 0.5, "social interaction", "SPANISH_BREADTH_PLAN.md B1 social topic", [(667, 670, "Saludo a mi vecino.", "I greet my neighbor."), (668, 671, "Nos saludan al entrar.", "They greet us when we enter.")]),
    (305, "despedirse", "verb", None, "to say goodbye", 2200, "B1", 0.6, "social interaction", "SPANISH_BREADTH_PLAN.md B1 social topic", [(669, 672, "Me despido del equipo.", "I say goodbye to the team."), (670, 673, "Nos despedimos en la estación.", "We say goodbye at the station.")]),
    (306, "invitar", "verb", None, "to invite", 1200, "B1", 0.5, "social interaction", "SPANISH_BREADTH_PLAN.md B1 social topic", [(671, 674, "Invito a mis amigos.", "I invite my friends."), (672, 675, "Nos invitan a cenar.", "They invite us to dinner.")]),
    (307, "agradecer", "verb", None, "to thank; to appreciate", 1600, "B1", 0.5, "social and service interactions", "SPANISH_BREADTH_PLAN.md B1 social/services topic", [(673, 676, "Agradezco tu ayuda.", "I appreciate your help."), (674, 677, "Agradecemos el consejo.", "We appreciate the advice.")]),
    (308, "disculparse", "verb", None, "to apologize", 2400, "B1", 0.6, "social and service interactions", "SPANISH_BREADTH_PLAN.md B1 social/services topic", [(675, 678, "Me disculpo por el error.", "I apologize for the mistake."), (676, 679, "Ella se disculpa tarde.", "She apologizes late.")]),
    (309, "celebrar", "verb", None, "to celebrate", 1300, "B1", 0.5, "social interaction and narration", "SPANISH_BREADTH_PLAN.md B1 social/narration topic", [(677, 680, "Celebro mi cumpleaños.", "I celebrate my birthday."), (678, 681, "Celebramos la noticia.", "We celebrate the news.")]),
    (310, "conversar", "verb", None, "to talk; to converse", 2100, "B1", 0.6, "social interaction", "SPANISH_BREADTH_PLAN.md B1 social topic", [(679, 682, "Converso con mi compañero.", "I talk with my coworker."), (680, 683, "Conversamos después.", "We talk afterward.")]),
    (311, "confiar", "verb", None, "to trust", 1350, "B1", 0.5, "opinions and relationships", "SPANISH_BREADTH_PLAN.md B1 opinions/social topic", [(681, 684, "Confío en ti.", "I trust you."), (682, 685, "Confiamos en el médico.", "We trust the doctor.")]),
    (312, "respetar", "verb", None, "to respect", 1200, "B1", 0.5, "opinions and social interaction", "SPANISH_BREADTH_PLAN.md B1 opinions/social topic", [(683, 686, "Respeto tu opinión.", "I respect your opinion."), (684, 687, "Respetamos las reglas.", "We respect the rules.")]),
    (313, "afirmar", "verb", None, "to state; to affirm", 1400, "B1", 0.5, "opinions", "SPANISH_BREADTH_PLAN.md B1 opinions topic", [(685, 688, "Afirmo que es posible.", "I state that it is possible."), (686, 689, "Ella afirma lo contrario.", "She states the opposite.")]),
    (314, "negar", "verb", None, "to deny", 1250, "B1", 0.5, "opinions and conflict", "SPANISH_BREADTH_PLAN.md B1 opinions/conflict topic", [(687, 690, "Niego el error.", "I deny the mistake."), (688, 691, "No niegan el problema.", "They do not deny the problem.")]),
    (315, "dudar", "verb", None, "to doubt", 1500, "B1", 0.5, "opinions and uncertainty", "SPANISH_BREADTH_PLAN.md B1 opinions/uncertainty topic", [(689, 692, "Dudo de la respuesta.", "I doubt the answer."), (690, 693, "Dudamos del plan.", "We doubt the plan.")]),
    (316, "parecer", "verb", None, "to seem", 520, "B1", 0.5, "opinions", "hermitdave/FrequencyWords high-frequency spine", [(691, 694, "Parece difícil.", "It seems difficult."), (692, 695, "Me parece adecuado.", "It seems appropriate to me.")]),
    (317, "mejorar", "verb", None, "to improve", 1100, "B1", 0.5, "health and services", "SPANISH_BREADTH_PLAN.md B1 health/services topic", [(693, 696, "Mejoro cada día.", "I improve every day."), (694, 697, "El servicio mejora mucho.", "The service improves a lot.")]),
    (318, "empeorar", "verb", None, "to get worse", 2200, "B1", 0.6, "health and problems", "SPANISH_BREADTH_PLAN.md B1 health/problems topic", [(695, 698, "Empeora el dolor.", "The pain gets worse."), (696, 699, "No quiero empeorar.", "I do not want to get worse.")]),
    (319, "diagnosticar", "verb", None, "to diagnose", 2500, "B1", 0.6, "health", "SPANISH_BREADTH_PLAN.md B1 health topic", [(697, 700, "Los médicos diagnostican la enfermedad.", "The doctors diagnose the illness."), (698, 701, "El médico diagnostica el problema.", "The doctor diagnoses the problem.")]),
    (320, "ingresar", "verb", None, "to be admitted; to enter", 1200, "B1", 0.5, "health and services", "SPANISH_BREADTH_PLAN.md B1 health/services topic", [(699, 702, "Ingreso en la clínica.", "I am admitted to the clinic."), (700, 703, "Ella ingresa mañana.", "She is admitted tomorrow.")]),
    (321, "operar", "verb", None, "to operate; to perform surgery", 1050, "B1", 0.5, "health and services", "SPANISH_BREADTH_PLAN.md B1 health/services topic", [(701, 704, "Los médicos operan al paciente.", "The doctors operate on the patient."), (702, 705, "El hospital opera hoy.", "The hospital operates today.")]),
    (322, "tratar", "verb", None, "to treat; to deal with", 620, "B1", 0.5, "health and problem solving", "hermitdave/FrequencyWords high-frequency spine", [(703, 706, "Trato el problema.", "I deal with the problem."), (704, 707, "El médico trata la infección.", "The doctor treats the infection.")]),
    (323, "devolver", "verb", None, "to return; to refund", 1400, "B1", 0.5, "services and shopping", "SPANISH_BREADTH_PLAN.md B1 services/shopping topic", [(705, 708, "Devuelvo el producto.", "I return the product."), (706, 709, "Me devuelven el dinero.", "They refund my money.")]),
    (324, "entregar", "verb", None, "to deliver; to submit", 1000, "B1", 0.5, "services and workplace", "SPANISH_BREADTH_PLAN.md B1 services/workplace topic", [(707, 710, "Entrego el documento.", "I submit the document."), (708, 711, "Entregan el paquete.", "They deliver the package.")]),
    (325, "contactar", "verb", None, "to contact", 1700, "B1", 0.5, "services and workplace", "SPANISH_BREADTH_PLAN.md B1 services/workplace topic", [(709, 712, "Contacto con el servicio.", "I contact the service."), (710, 713, "Nos contactan mañana.", "They contact us tomorrow.")]),
    (326, "ajustar", "verb", None, "to adjust", 1500, "B1", 0.5, "planning and services", "SPANISH_BREADTH_PLAN.md B1 planning/services topic", [(711, 714, "Ajusto el horario.", "I adjust the schedule."), (712, 715, "Ajustamos el precio.", "We adjust the price.")]),
    (327, "renovar", "verb", None, "to renew", 1800, "B1", 0.5, "services and planning", "SPANISH_BREADTH_PLAN.md B1 services/planning topic", [(713, 716, "Renuevo el contrato.", "I renew the contract."), (714, 717, "Necesito renovar mi tarjeta.", "I need to renew my card.")]),
    (328, "aprobar", "verb", None, "to approve; to pass", 1150, "B1", 0.5, "workplace and decisions", "SPANISH_BREADTH_PLAN.md B1 workplace/decisions topic", [(715, 718, "Apruebo el plan.", "I approve the plan."), (716, 719, "La empresa aprueba el cambio.", "The company approves the change.")]),
    (329, "suspender", "verb", None, "to suspend; to cancel", 1700, "B1", 0.5, "services and planning", "SPANISH_BREADTH_PLAN.md B1 services/planning topic", [(717, 720, "Suspenden la reunión.", "They suspend the meeting."), (718, 721, "El servicio se suspende.", "The service is suspended.")]),
    (330, "proteger", "verb", None, "to protect", 950, "B1", 0.5, "services and health", "SPANISH_BREADTH_PLAN.md B1 services/health topic", [(719, 722, "Protejo mis datos.", "I protect my data."), (720, 723, "El seguro nos protege.", "The insurance protects us.")]),
    (331, "historia", "noun", "F", "story; history", 680, "B1", 0.5, "narration", "hermitdave/FrequencyWords high-frequency spine", [(721, 724, "La historia es larga.", "The story is long."), (722, 725, "Él cuenta una historia.", "He tells a story.")]),
    (332, "detalle", "noun", "M", "detail", 1200, "B1", 0.5, "narration and services", "SPANISH_BREADTH_PLAN.md B1 narration/services topic", [(723, 726, "Falta un detalle.", "A detail is missing."), (724, 727, "Reviso cada detalle.", "I check every detail.")]),
    (333, "noticia", "noun", "F", "news", 900, "B1", 0.5, "narration and social interaction", "hermitdave/FrequencyWords high-frequency spine", [(725, 728, "La noticia es buena.", "The news is good."), (726, 729, "Recibo una noticia.", "I receive some news.")]),
    (334, "futuro", "noun", "M", "future", 820, "B1", 0.5, "future planning", "hermitdave/FrequencyWords high-frequency spine", [(727, 730, "Pienso en el futuro.", "I think about the future."), (728, 731, "El futuro parece mejor.", "The future seems better.")]),
    (335, "pasado", "noun", "M", "past", 900, "B1", 0.5, "past narration", "SPANISH_BREADTH_PLAN.md B1 past narration topic", [(729, 732, "Recuerdo el pasado.", "I remember the past."), (730, 733, "Eso pasó en el pasado.", "That happened in the past.")]),
    (336, "reunión", "noun", "F", "meeting", 850, "B1", 0.5, "workplace and planning", "hermitdave/FrequencyWords high-frequency spine", [(731, 734, "La reunión empieza ahora.", "The meeting starts now."), (732, 735, "Cancelo la reunión.", "I cancel the meeting.")]),
    (337, "proyecto", "noun", "M", "project", 700, "B1", 0.5, "workplace and planning", "hermitdave/FrequencyWords high-frequency spine", [(733, 736, "El proyecto avanza.", "The project moves forward."), (734, 737, "El proyecto es importante.", "The project is important.")]),
    (338, "empresa", "noun", "F", "company", 560, "B1", 0.5, "workplace", "hermitdave/FrequencyWords high-frequency spine", [(735, 738, "Trabajo en una empresa.", "I work at a company."), (736, 739, "La empresa llama hoy.", "The company calls today.")]),
    (339, "jefe", "noun", "M", "boss", 1000, "B1", 0.5, "workplace and social interaction", "SPANISH_BREADTH_PLAN.md B1 workplace/social topic", [(737, 740, "Mi jefe llega tarde.", "My boss arrives late."), (738, 741, "Hablo con el jefe.", "I speak with the boss.")]),
    (340, "compañero", "noun", "M", "coworker; companion", 1300, "B1", 0.5, "workplace and social interaction", "SPANISH_BREADTH_PLAN.md B1 workplace/social topic", [(739, 742, "Ayudo a mi compañero.", "I help my coworker."), (740, 743, "Mi compañero está enfermo.", "My coworker is sick.")]),
    (341, "contrato", "noun", "M", "contract", 900, "B1", 0.5, "workplace and services", "hermitdave/FrequencyWords high-frequency spine", [(741, 744, "Firmo el contrato.", "I sign the contract."), (742, 745, "El contrato termina hoy.", "The contract ends today.")]),
    (342, "horario", "noun", "M", "schedule", 1400, "B1", 0.5, "planning and services", "SPANISH_BREADTH_PLAN.md B1 planning/services topic", [(743, 746, "Reviso el horario.", "I check the schedule."), (744, 747, "El horario cambia mañana.", "The schedule changes tomorrow.")]),
    (343, "turno", "noun", "M", "shift; turn", 1600, "B1", 0.5, "workplace and services", "SPANISH_BREADTH_PLAN.md B1 workplace/services topic", [(745, 748, "Trabajo en el turno de tarde.", "I work the evening shift."), (746, 749, "Cambio mi turno.", "I change my shift.")]),
    (344, "salario", "noun", "M", "salary", 1500, "B1", 0.5, "workplace and money", "SPANISH_BREADTH_PLAN.md B1 workplace/money topic", [(747, 750, "Recibo mi salario.", "I receive my salary."), (748, 751, "El salario es mensual.", "The salary is monthly.")]),
    (345, "farmacia", "noun", "F", "pharmacy", 1900, "B1", 0.5, "health and services", "SPANISH_BREADTH_PLAN.md B1 health/services topic", [(749, 752, "Voy a la farmacia.", "I go to the pharmacy."), (750, 753, "La farmacia está cerca.", "The pharmacy is nearby.")]),
    (346, "síntoma", "noun", "M", "symptom", 2300, "B1", 0.6, "health", "SPANISH_BREADTH_PLAN.md B1 health topic", [(751, 754, "Tengo un síntoma nuevo.", "I have a new symptom."), (752, 755, "Describo el síntoma.", "I describe the symptom.")]),
])


AI_ACCELERATED_PACK_A2_010 = build_ai_accelerated_pack([
    (347, "aunque", "conjunction", None, "although; even though", 260, "B1", 0.4, "connectors", "hermitdave/FrequencyWords high-frequency spine", [(753, 756, "Voy aunque llueve.", "I go although it is raining."), (754, 757, "Aunque estoy cansado, trabajo.", "Although I am tired, I work.")]),
    (348, "además", "adverb", None, "also; besides", 520, "B1", 0.4, "connectors", "hermitdave/FrequencyWords high-frequency spine", [(755, 758, "Además, necesito ayuda.", "Besides, I need help."), (756, 759, "Trabajo y además estudio.", "I work and also study.")]),
    (349, "entonces", "adverb", None, "then; so", 430, "B1", 0.4, "connectors and narration", "hermitdave/FrequencyWords high-frequency spine", [(757, 760, "Entonces llamé al médico.", "Then I called the doctor."), (758, 761, "No hay tiempo, entonces salimos.", "There is no time, so we leave.")]),
    (350, "mientras", "conjunction", None, "while", 540, "B1", 0.4, "connectors and narration", "hermitdave/FrequencyWords high-frequency spine", [(759, 762, "Espero mientras revisan el coche.", "I wait while they check the car."), (760, 763, "Trabajo mientras tú descansas.", "I work while you rest.")]),
    (351, "todavía", "adverb", None, "still; yet", 620, "B1", 0.4, "time and narration", "hermitdave/FrequencyWords high-frequency spine", [(761, 764, "Todavía espero la respuesta.", "I am still waiting for the answer."), (762, 765, "Todavía no llega el tren.", "The train has not arrived yet.")]),
    (352, "tampoco", "adverb", None, "neither; not either", 760, "B1", 0.4, "connectors and opinions", "hermitdave/FrequencyWords high-frequency spine", [(763, 766, "Yo tampoco estoy de acuerdo.", "I do not agree either."), (764, 767, "Tampoco tenemos efectivo.", "We do not have cash either.")]),
    (353, "incluso", "adverb", None, "even; including", 780, "B1", 0.4, "connectors and emphasis", "hermitdave/FrequencyWords high-frequency spine", [(765, 768, "Incluso el jefe ayuda.", "Even the boss helps."), (766, 769, "Aceptan incluso tarjetas.", "They even accept cards.")]),
    (354, "quizás", "adverb", None, "perhaps; maybe", 900, "B1", 0.5, "opinions and uncertainty", "SPANISH_BREADTH_PLAN.md B1 opinions/uncertainty topic", [(767, 770, "Quizás llegue tarde.", "Maybe I will arrive late."), (768, 771, "Quizás sea mejor esperar.", "Perhaps it is better to wait.")]),
    (355, "aproximadamente", "adverb", None, "approximately", 1700, "B1", 0.5, "appointments and banking", "SPANISH_BREADTH_PLAN.md B1 practical chunks topic", [(769, 772, "Cuesta aproximadamente veinte euros.", "It costs approximately twenty euros."), (770, 773, "Llegamos aproximadamente a las ocho.", "We arrive at approximately eight.")]),
    (356, "normalmente", "adverb", None, "normally", 950, "B1", 0.5, "narration and routine", "hermitdave/FrequencyWords high-frequency spine", [(771, 774, "Normalmente trabajo temprano.", "I normally work early."), (772, 775, "Normalmente pago con tarjeta.", "I normally pay with a card.")]),
    (357, "actualmente", "adverb", None, "currently", 1100, "B1", 0.5, "workplace and narration", "SPANISH_BREADTH_PLAN.md B1 workplace/narration topic", [(773, 776, "Actualmente vivo en Madrid.", "I currently live in Madrid."), (774, 777, "Actualmente busco trabajo.", "I am currently looking for work.")]),
    (358, "especialmente", "adverb", None, "especially", 1200, "B1", 0.5, "opinions and emphasis", "SPANISH_BREADTH_PLAN.md B1 opinions topic", [(775, 778, "Me gusta especialmente este plan.", "I especially like this plan."), (776, 779, "Es especialmente importante hoy.", "It is especially important today.")]),
    (359, "finalmente", "adverb", None, "finally", 1000, "B1", 0.5, "narration and sequencing", "SPANISH_BREADTH_PLAN.md B1 narration topic", [(777, 780, "Finalmente llegamos al hotel.", "Finally we arrive at the hotel."), (778, 781, "Finalmente resolvemos el problema.", "Finally we solve the problem.")]),
    (360, "anteriormente", "adverb", None, "previously", 1700, "B1", 0.5, "past narration", "SPANISH_BREADTH_PLAN.md B1 past narration topic", [(779, 782, "Anteriormente trabajé allí.", "Previously I worked there."), (780, 783, "Lo expliqué anteriormente.", "I explained it previously.")]),
    (361, "después", "adverb", None, "afterward; later", 260, "B1", 0.4, "sequencing and narration", "hermitdave/FrequencyWords high-frequency spine", [(781, 784, "Después llamo al banco.", "Afterward I call the bank."), (782, 785, "Hablamos después de la reunión.", "We talk after the meeting.")]),
    (362, "durante", "preposition", None, "during", 330, "B1", 0.4, "time and narration", "hermitdave/FrequencyWords high-frequency spine", [(783, 786, "Trabajo durante la tarde.", "I work during the afternoon."), (784, 787, "Durante la cita, pregunto mucho.", "During the appointment, I ask a lot.")]),
    (363, "según", "preposition", None, "according to", 420, "B1", 0.4, "connectors and opinions", "hermitdave/FrequencyWords high-frequency spine", [(785, 788, "Según el médico, estoy mejor.", "According to the doctor, I am better."), (786, 789, "Según el informe, falta dinero.", "According to the report, money is missing.")]),
    (364, "mediante", "preposition", None, "by means of; through", 1400, "B1", 0.5, "services and banking", "SPANISH_BREADTH_PLAN.md B1 practical chunks topic", [(787, 790, "Pago mediante transferencia.", "I pay by transfer."), (788, 791, "Reservo mediante la aplicación.", "I book through the app.")]),
    (365, "excepto", "preposition", None, "except", 1200, "B1", 0.5, "connectors and exceptions", "SPANISH_BREADTH_PLAN.md B1 connectors topic", [(789, 792, "Todos vienen excepto Ana.", "Everyone comes except Ana."), (790, 793, "Aceptan todo excepto efectivo.", "They accept everything except cash.")]),
    (366, "alrededor", "adverb", None, "around; nearby", 900, "B1", 0.5, "travel and housing", "SPANISH_BREADTH_PLAN.md B1 travel/housing topic", [(791, 794, "Camino alrededor del edificio.", "I walk around the building."), (792, 795, "Hay tiendas alrededor.", "There are shops nearby.")]),
    (367, "relatar", "verb", None, "to relate; to tell", 2400, "B1", 0.6, "narration", "SPANISH_BREADTH_PLAN.md B1 narration topic", [(793, 796, "Relato lo que ocurrió.", "I tell what happened."), (794, 797, "Ella relata su viaje.", "She tells about her trip.")]),
    (368, "indicar", "verb", None, "to indicate; to point out", 900, "B1", 0.5, "services and directions", "hermitdave/FrequencyWords high-frequency spine", [(795, 798, "Indico mi dirección.", "I indicate my address."), (796, 799, "El cartel indica la salida.", "The sign indicates the exit.")]),
    (369, "señalar", "verb", None, "to point out; to signal", 1100, "B1", 0.5, "narration and services", "SPANISH_BREADTH_PLAN.md B1 narration/services topic", [(797, 800, "Señalo el error.", "I point out the error."), (798, 801, "Ella señala el camino.", "She points out the way.")]),
    (370, "evitar", "verb", None, "to avoid", 760, "B1", 0.5, "problems and health", "hermitdave/FrequencyWords high-frequency spine", [(799, 802, "Evito el problema.", "I avoid the problem."), (800, 803, "Debemos evitar el retraso.", "We should avoid the delay.")]),
    (371, "prevenir", "verb", None, "to prevent", 1500, "B1", 0.5, "health and problems", "SPANISH_BREADTH_PLAN.md B1 health/problems topic", [(801, 804, "Prevengo la infección.", "I prevent the infection."), (802, 805, "Queremos prevenir errores.", "We want to prevent mistakes.")]),
    (372, "afrontar", "verb", None, "to face; to deal with", 1900, "B1", 0.5, "problems and solutions", "SPANISH_BREADTH_PLAN.md B1 problems/solutions topic", [(803, 806, "Afronto el problema.", "I face the problem."), (804, 807, "Afrontamos una situación difícil.", "We face a difficult situation.")]),
    (373, "enfrentar", "verb", None, "to face; to confront", 1300, "B1", 0.5, "problems and conflict", "SPANISH_BREADTH_PLAN.md B1 problems/conflict topic", [(805, 808, "Enfrento una queja.", "I face a complaint."), (806, 809, "La empresa enfrenta cambios.", "The company faces changes.")]),
    (374, "denunciar", "verb", None, "to report; to denounce", 1600, "B1", 0.5, "problems and services", "SPANISH_BREADTH_PLAN.md B1 problems/services topic", [(807, 810, "Denuncio el problema.", "I report the problem."), (808, 811, "Ella denuncia el robo.", "She reports the theft.")]),
    (375, "resolver", "verb", None, "to resolve; to solve", 950, "B1", 0.5, "problems and solutions", "SPANISH_BREADTH_PLAN.md B1 problems/solutions topic", [(809, 812, "Resuelvo la duda.", "I resolve the doubt."), (810, 813, "Resolvemos el conflicto.", "We resolve the conflict.")]),
    (376, "comprobar", "verb", None, "to check; to verify", 1350, "B1", 0.5, "services and problem solving", "SPANISH_BREADTH_PLAN.md B1 services/problems topic", [(811, 814, "Compruebo la reserva.", "I check the reservation."), (812, 815, "Comprueban mi pasaporte.", "They check my passport.")]),
    (377, "verificar", "verb", None, "to verify", 1700, "B1", 0.5, "services and banking", "SPANISH_BREADTH_PLAN.md B1 services/banking topic", [(813, 816, "Verifico mi cuenta.", "I verify my account."), (814, 817, "Verificamos los datos.", "We verify the data.")]),
    (378, "gestionar", "verb", None, "to manage; to handle", 1500, "B1", 0.5, "workplace and services", "SPANISH_BREADTH_PLAN.md B1 workplace/services topic", [(815, 818, "Gestiono la solicitud.", "I handle the request."), (816, 819, "La oficina gestiona el trámite.", "The office manages the procedure.")]),
    (379, "tramitar", "verb", None, "to process paperwork", 2300, "B1", 0.6, "services and bureaucracy", "SPANISH_BREADTH_PLAN.md B1 services topic", [(817, 820, "Tramito el permiso.", "I process the permit."), (818, 821, "Necesito tramitar el visado.", "I need to process the visa.")]),
    (380, "anular", "verb", None, "to cancel; to void", 2000, "B1", 0.6, "appointments and services", "SPANISH_BREADTH_PLAN.md B1 appointments/services topic", [(819, 822, "Anulo la reserva.", "I cancel the reservation."), (820, 823, "Quiero anular la cita.", "I want to cancel the appointment.")]),
    (381, "posponer", "verb", None, "to postpone", 2200, "B1", 0.6, "appointments and planning", "SPANISH_BREADTH_PLAN.md B1 appointments/planning topic", [(821, 824, "Pospongo la reunión.", "I postpone the meeting."), (822, 825, "Posponemos el viaje.", "We postpone the trip.")]),
    (382, "citar", "verb", None, "to cite; to make an appointment", 1700, "B1", 0.5, "appointments and services", "SPANISH_BREADTH_PLAN.md B1 appointments topic", [(823, 826, "Cito al paciente mañana.", "I schedule the patient tomorrow."), (824, 827, "El médico me cita el lunes.", "The doctor schedules me for Monday.")]),
    (383, "acudir", "verb", None, "to attend; to go to", 1600, "B1", 0.5, "appointments and health", "SPANISH_BREADTH_PLAN.md B1 appointments/health topic", [(825, 828, "Acudo a la cita.", "I go to the appointment."), (826, 829, "Acudimos al hospital.", "We go to the hospital.")]),
    (384, "asistir", "verb", None, "to attend", 900, "B1", 0.5, "workplace and appointments", "hermitdave/FrequencyWords high-frequency spine", [(827, 830, "Asisto a la reunión.", "I attend the meeting."), (828, 831, "Ella asiste al curso.", "She attends the course.")]),
    (385, "notificar", "verb", None, "to notify", 1900, "B1", 0.5, "services and workplace", "SPANISH_BREADTH_PLAN.md B1 services/workplace topic", [(829, 832, "Notifico al cliente del cambio.", "I notify the customer of the change."), (830, 833, "Nos notifican la decisión.", "They notify us of the decision.")]),
    (386, "presupuesto", "noun", "M", "budget; estimate", 1200, "B1", 0.5, "banking and services", "SPANISH_BREADTH_PLAN.md B1 banking/services topic", [(831, 834, "El presupuesto es bajo.", "The budget is low."), (832, 835, "Pido un presupuesto.", "I ask for an estimate.")]),
    (387, "cliente", "noun", "M", "customer; client", 700, "B1", 0.5, "workplace and services", "hermitdave/FrequencyWords high-frequency spine", [(833, 836, "El cliente espera.", "The customer waits."), (834, 837, "Ayudo al cliente.", "I help the customer.")]),
    (388, "proveedor", "noun", "M", "supplier; provider", 1900, "B1", 0.5, "workplace and services", "SPANISH_BREADTH_PLAN.md B1 workplace/services topic", [(835, 838, "Llamo al proveedor.", "I call the supplier."), (836, 839, "El proveedor entrega el paquete.", "The supplier delivers the package.")]),
    (389, "equipo", "noun", "M", "team; equipment", 650, "B1", 0.5, "workplace", "hermitdave/FrequencyWords high-frequency spine", [(837, 840, "Mi equipo trabaja bien.", "My team works well."), (838, 841, "Necesito equipo nuevo.", "I need new equipment.")]),
    (390, "informe", "noun", "M", "report", 900, "B1", 0.5, "workplace and narration", "SPANISH_BREADTH_PLAN.md B1 workplace/narration topic", [(839, 842, "Escribo el informe.", "I write the report."), (840, 843, "El informe está listo.", "The report is ready.")]),
    (391, "documento", "noun", "M", "document", 850, "B1", 0.5, "workplace and services", "hermitdave/FrequencyWords high-frequency spine", [(841, 844, "Firmo el documento.", "I sign the document."), (842, 845, "Falta un documento.", "A document is missing.")]),
    (392, "tarea", "noun", "F", "task; homework", 1200, "B1", 0.5, "workplace and planning", "SPANISH_BREADTH_PLAN.md B1 workplace/planning topic", [(843, 846, "Termino la tarea.", "I finish the task."), (844, 847, "La tarea parece fácil.", "The task seems easy.")]),
    (393, "plazo", "noun", "M", "deadline; term", 1300, "B1", 0.5, "workplace and planning", "SPANISH_BREADTH_PLAN.md B1 workplace/planning topic", [(845, 848, "El plazo termina mañana.", "The deadline ends tomorrow."), (846, 849, "Necesito más plazo.", "I need more time.")]),
    (394, "objetivo", "noun", "M", "goal; objective", 850, "B1", 0.5, "planning and workplace", "hermitdave/FrequencyWords high-frequency spine", [(847, 850, "Tengo un objetivo claro.", "I have a clear goal."), (848, 851, "Logramos el objetivo.", "We achieve the goal.")]),
    (395, "resultado", "noun", "M", "result", 760, "B1", 0.5, "workplace and health", "hermitdave/FrequencyWords high-frequency spine", [(849, 852, "Espero el resultado.", "I wait for the result."), (850, 853, "El resultado es normal.", "The result is normal.")]),
    (396, "dato", "noun", "M", "data point; piece of information", 900, "B1", 0.5, "workplace and banking", "SPANISH_BREADTH_PLAN.md B1 workplace/banking topic", [(851, 854, "Falta un dato.", "A piece of information is missing."), (852, 855, "Verifico los datos.", "I verify the data.")]),
    (397, "formulario", "noun", "M", "form", 1900, "B1", 0.5, "services and appointments", "SPANISH_BREADTH_PLAN.md B1 services topic", [(853, 856, "Completo el formulario.", "I complete the form."), (854, 857, "El formulario está listo.", "The form is ready.")]),
    (398, "permiso", "noun", "M", "permission; permit", 1000, "B1", 0.5, "services and workplace", "hermitdave/FrequencyWords high-frequency spine", [(855, 858, "Necesito un permiso.", "I need a permit."), (856, 859, "El permiso es obligatorio.", "The permit is required.")]),
    (399, "calendario", "noun", "M", "calendar", 1600, "B1", 0.5, "appointments and planning", "SPANISH_BREADTH_PLAN.md B1 appointments/planning topic", [(857, 860, "Reviso el calendario.", "I check the calendar."), (858, 861, "El calendario cambia.", "The calendar changes.")]),
    (400, "disponibilidad", "noun", "F", "availability", 2100, "B1", 0.6, "appointments and services", "SPANISH_BREADTH_PLAN.md B1 appointments/services topic", [(859, 862, "Tengo disponibilidad mañana.", "I have availability tomorrow."), (860, 863, "Consulto la disponibilidad.", "I check the availability.")]),
    (401, "retraso", "noun", "M", "delay", 1300, "B1", 0.5, "travel and appointments", "SPANISH_BREADTH_PLAN.md B1 travel/appointments topic", [(861, 864, "Hay un retraso.", "There is a delay."), (862, 865, "El retraso causa problemas.", "The delay causes problems.")]),
    (402, "cambio", "noun", "M", "change", 520, "B1", 0.5, "planning and services", "hermitdave/FrequencyWords high-frequency spine", [(863, 866, "El cambio empieza mañana.", "The change starts tomorrow."), (864, 867, "Acepto el cambio.", "I accept the change.")]),
    (403, "enfermedad", "noun", "F", "illness; disease", 900, "B1", 0.5, "health", "hermitdave/FrequencyWords high-frequency spine", [(865, 868, "La enfermedad mejora.", "The illness improves."), (866, 869, "El médico trata la enfermedad.", "The doctor treats the illness.")]),
    (404, "infección", "noun", "F", "infection", 1700, "B1", 0.5, "health", "SPANISH_BREADTH_PLAN.md B1 health topic", [(867, 870, "Tengo una infección.", "I have an infection."), (868, 871, "La infección empeora.", "The infection gets worse.")]),
    (405, "clínica", "noun", "F", "clinic", 1500, "B1", 0.5, "health and services", "SPANISH_BREADTH_PLAN.md B1 health/services topic", [(869, 872, "Voy a la clínica.", "I go to the clinic."), (870, 873, "La clínica abre temprano.", "The clinic opens early.")]),
    (406, "hospital", "noun", "M", "hospital", 850, "B1", 0.5, "health and services", "hermitdave/FrequencyWords high-frequency spine", [(871, 874, "Estoy en el hospital.", "I am in the hospital."), (872, 875, "El hospital está cerca.", "The hospital is nearby.")]),
    (407, "paciente", "noun", "M", "patient", 950, "B1", 0.5, "health", "hermitdave/FrequencyWords high-frequency spine", [(873, 876, "El paciente espera.", "The patient waits."), (874, 877, "Ayudo al paciente.", "I help the patient.")]),
    (408, "análisis", "noun", "M", "analysis; test", 1100, "B1", 0.5, "health and workplace", "SPANISH_BREADTH_PLAN.md B1 health/workplace topic", [(875, 878, "Necesito un análisis.", "I need a test."), (876, 879, "El análisis está listo.", "The test is ready.")]),
    (409, "tratamiento", "noun", "M", "treatment", 1000, "B1", 0.5, "health", "SPANISH_BREADTH_PLAN.md B1 health topic", [(877, 880, "Empiezo el tratamiento.", "I start the treatment."), (878, 881, "El tratamiento ayuda mucho.", "The treatment helps a lot.")]),
    (410, "medicamento", "noun", "M", "medicine; medication", 1600, "B1", 0.5, "health", "SPANISH_BREADTH_PLAN.md B1 health topic", [(879, 882, "Tomo el medicamento.", "I take the medicine."), (880, 883, "Necesito otro medicamento.", "I need another medication.")]),
    (411, "prueba", "noun", "F", "test; proof", 900, "B1", 0.5, "health and services", "SPANISH_BREADTH_PLAN.md B1 health/services topic", [(881, 884, "Hago una prueba.", "I take a test."), (882, 885, "La prueba es negativa.", "The test is negative.")]),
    (412, "apartamento", "noun", "M", "apartment", 1800, "B1", 0.5, "housing", "SPANISH_BREADTH_PLAN.md B1 housing topic", [(883, 886, "Alquilo un apartamento.", "I rent an apartment."), (884, 887, "El apartamento es cómodo.", "The apartment is comfortable.")]),
    (413, "alquiler", "noun", "M", "rent; rental", 1500, "B1", 0.5, "housing and banking", "SPANISH_BREADTH_PLAN.md B1 housing/banking topic", [(885, 888, "Pago el alquiler.", "I pay the rent."), (886, 889, "El alquiler es mensual.", "The rent is monthly.")]),
    (414, "vecino", "noun", "M", "neighbor", 1400, "B1", 0.5, "housing and social interaction", "SPANISH_BREADTH_PLAN.md B1 housing/social topic", [(887, 890, "Saludo al vecino.", "I greet the neighbor."), (888, 891, "Mi vecino ayuda mucho.", "My neighbor helps a lot.")]),
    (415, "llave", "noun", "F", "key", 1300, "B1", 0.5, "housing and travel", "SPANISH_BREADTH_PLAN.md B1 housing/travel topic", [(889, 892, "Pierdo la llave.", "I lose the key."), (890, 893, "Necesito otra llave.", "I need another key.")]),
    (416, "ascensor", "noun", "M", "elevator", 2300, "B1", 0.6, "housing and services", "SPANISH_BREADTH_PLAN.md B1 housing/services topic", [(891, 894, "El ascensor no funciona.", "The elevator does not work."), (892, 895, "Uso el ascensor.", "I use the elevator.")]),
    (417, "baño", "noun", "M", "bathroom", 1000, "B1", 0.5, "housing and travel", "SPANISH_BREADTH_PLAN.md B1 housing/travel topic", [(893, 896, "El baño está limpio.", "The bathroom is clean."), (894, 897, "Busco el baño.", "I look for the bathroom.")]),
    (418, "destino", "noun", "M", "destination", 1200, "B1", 0.5, "travel", "SPANISH_BREADTH_PLAN.md B1 travel topic", [(895, 898, "Llego a mi destino.", "I arrive at my destination."), (896, 899, "El destino está lejos.", "The destination is far away.")]),
    (419, "ruta", "noun", "F", "route", 1100, "B1", 0.5, "travel and transit", "SPANISH_BREADTH_PLAN.md B1 travel/transit topic", [(897, 900, "Cambio la ruta.", "I change the route."), (898, 901, "La ruta es directa.", "The route is direct.")]),
    (420, "pasaporte", "noun", "M", "passport", 1900, "B1", 0.5, "travel and services", "SPANISH_BREADTH_PLAN.md B1 travel/services topic", [(899, 902, "Muestro mi pasaporte.", "I show my passport."), (900, 903, "Comprueban el pasaporte.", "They check the passport.")]),
    (421, "billete", "noun", "M", "ticket; bill", 1200, "B1", 0.5, "travel and banking", "SPANISH_BREADTH_PLAN.md B1 travel/banking topic", [(901, 904, "Compro un billete.", "I buy a ticket."), (902, 905, "El billete cuesta poco.", "The ticket costs little.")]),
    (422, "préstamo", "noun", "M", "loan", 1500, "B1", 0.5, "banking", "SPANISH_BREADTH_PLAN.md B1 banking topic", [(903, 906, "Solicito un préstamo.", "I apply for a loan."), (904, 907, "El préstamo es caro.", "The loan is expensive.")]),
    (423, "efectivo", "noun", "M", "cash", 1600, "B1", 0.5, "banking and services", "SPANISH_BREADTH_PLAN.md B1 banking/services topic", [(905, 908, "Pago en efectivo.", "I pay in cash."), (906, 909, "No tengo efectivo.", "I do not have cash.")]),
    (424, "recibo", "noun", "M", "receipt", 1700, "B1", 0.5, "banking and services", "SPANISH_BREADTH_PLAN.md B1 banking/services topic", [(907, 910, "Guardo el recibo.", "I keep the receipt."), (908, 911, "Necesito un recibo.", "I need a receipt.")]),
    (425, "cajero", "noun", "M", "cashier; ATM", 1900, "B1", 0.5, "banking and services", "SPANISH_BREADTH_PLAN.md B1 banking/services topic", [(909, 912, "Uso el cajero.", "I use the ATM."), (910, 913, "El cajero no funciona.", "The ATM does not work.")]),
    (426, "cuota", "noun", "F", "fee; installment", 1600, "B1", 0.5, "banking and services", "SPANISH_BREADTH_PLAN.md B1 banking/services topic", [(911, 914, "Pago la cuota mensual.", "I pay the monthly fee."), (912, 915, "La cuota sube este año.", "The fee rises this year.")]),
])


AI_ACCELERATED_PACK_A2_011 = build_ai_accelerated_pack([
    (427, "sin embargo", "adverbial phrase", None, "however", 700, "B1", 0.5, "connectors and opinions", "SPANISH_BREADTH_PLAN.md B1 connectors topic", [(913, 916, "Sin embargo, prefiero esperar.", "However, I prefer to wait."), (914, 917, "El servicio es caro; sin embargo, funciona.", "The service is expensive; however, it works.")]),
    (428, "por eso", "adverbial phrase", None, "therefore; that is why", 650, "B1", 0.5, "connectors and explanations", "SPANISH_BREADTH_PLAN.md B1 connectors topic", [(915, 918, "Por eso llamo al banco.", "That is why I call the bank."), (916, 919, "Estoy enfermo; por eso descanso.", "I am sick; that is why I rest.")]),
    (429, "alternativamente", "adverb", None, "alternatively", 2100, "B1", 0.6, "connectors and planning", "SPANISH_BREADTH_PLAN.md B1 connectors topic", [(917, 920, "Alternativamente, podemos esperar.", "Alternatively, we can wait."), (918, 921, "Alternativamente, llamo mañana.", "Alternatively, I call tomorrow.")]),
    (430, "por ejemplo", "adverbial phrase", None, "for example", 500, "B1", 0.4, "connectors and examples", "hermitdave/FrequencyWords high-frequency spine", [(919, 922, "Necesito documentos, por ejemplo, el pasaporte.", "I need documents, for example, the passport."), (920, 923, "Hay servicios útiles, por ejemplo, la farmacia.", "There are useful services, for example, the pharmacy.")]),
    (431, "en cuanto a", "prepositional phrase", None, "regarding", 1400, "B1", 0.6, "connectors and workplace", "SPANISH_BREADTH_PLAN.md B1 connectors/workplace topic", [(921, 924, "En cuanto al contrato, necesito tiempo.", "Regarding the contract, I need time."), (922, 925, "En cuanto a la cita, puedo cambiarla.", "Regarding the appointment, I can change it.")]),
    (432, "a pesar de", "prepositional phrase", None, "despite", 950, "B1", 0.5, "connectors and narration", "SPANISH_BREADTH_PLAN.md B1 connectors topic", [(923, 926, "A pesar del retraso, llegamos.", "Despite the delay, we arrive."), (924, 927, "Trabajo a pesar del dolor.", "I work despite the pain.")]),
    (433, "de repente", "adverbial phrase", None, "suddenly", 1100, "B1", 0.5, "narration", "SPANISH_BREADTH_PLAN.md B1 narration topic", [(925, 928, "De repente, empezó la lluvia.", "Suddenly, the rain started."), (926, 929, "De repente, me dolió la cabeza.", "Suddenly, my head hurt.")]),
    (434, "al principio", "adverbial phrase", None, "at first", 1000, "B1", 0.5, "narration and sequencing", "SPANISH_BREADTH_PLAN.md B1 narration topic", [(927, 930, "Al principio no entendí.", "At first I did not understand."), (928, 931, "Al principio, el trámite parecía fácil.", "At first, the procedure seemed easy.")]),
    (435, "al final", "adverbial phrase", None, "in the end", 700, "B1", 0.5, "narration and sequencing", "SPANISH_BREADTH_PLAN.md B1 narration topic", [(929, 932, "Al final resolvimos el problema.", "In the end we solved the problem."), (930, 933, "Al final pagué la factura.", "In the end I paid the bill.")]),
    (436, "por lo tanto", "adverbial phrase", None, "therefore", 1200, "B1", 0.5, "connectors and explanations", "SPANISH_BREADTH_PLAN.md B1 connectors topic", [(931, 934, "No hay documentos; por lo tanto, esperamos.", "There are no documents; therefore, we wait."), (932, 935, "El plazo termina hoy; por lo tanto, llamo.", "The deadline ends today; therefore, I call.")]),
    (437, "soler", "verb", None, "to usually do", 1100, "B1", 0.5, "routine and narration", "SPANISH_BREADTH_PLAN.md B1 narration/routine topic", [(933, 936, "Suelo llegar temprano.", "I usually arrive early."), (934, 937, "Solemos pagar con tarjeta.", "We usually pay by card.")]),
    (438, "mantener", "verb", None, "to maintain; to keep", 650, "B1", 0.5, "workplace and health", "hermitdave/FrequencyWords high-frequency spine", [(935, 938, "Mantengo la calma.", "I keep calm."), (936, 939, "Mantenemos el contacto.", "We keep in touch.")]),
    (439, "apoyar", "verb", None, "to support", 950, "B1", 0.5, "social and workplace", "SPANISH_BREADTH_PLAN.md B1 workplace/social topic", [(937, 940, "Apoyo a mi compañero.", "I support my coworker."), (938, 941, "La empresa apoya el proyecto.", "The company supports the project.")]),
    (440, "permitirse", "verb", None, "to afford", 2200, "B1", 0.6, "banking and decisions", "SPANISH_BREADTH_PLAN.md B1 banking/decisions topic", [(939, 942, "No puedo permitirme otro hotel.", "I cannot afford another hotel."), (940, 943, "Podemos permitirnos el alquiler.", "We can afford the rent.")]),
    (441, "acostumbrarse", "verb", None, "to get used to", 2300, "B1", 0.6, "housing and work", "SPANISH_BREADTH_PLAN.md B1 housing/work topic", [(941, 944, "Me acostumbro al horario.", "I get used to the schedule."), (942, 945, "Nos acostumbramos al barrio.", "We get used to the neighborhood.")]),
    (442, "convencer", "verb", None, "to convince", 1300, "B1", 0.5, "opinions and conflict", "SPANISH_BREADTH_PLAN.md B1 opinions/conflict topic", [(943, 946, "Convenzo al cliente.", "I convince the customer."), (944, 947, "No quiero convencerte.", "I do not want to convince you.")]),
    (443, "criticar", "verb", None, "to criticize", 1500, "B1", 0.5, "opinions and workplace", "SPANISH_BREADTH_PLAN.md B1 opinions/workplace topic", [(945, 948, "Critico el servicio.", "I criticize the service."), (946, 949, "Ellos critican la decisión.", "They criticize the decision.")]),
    (444, "valorar", "verb", None, "to value; to assess", 1200, "B1", 0.5, "opinions and workplace", "SPANISH_BREADTH_PLAN.md B1 opinions/workplace topic", [(947, 950, "Valoro tu opinión.", "I value your opinion."), (948, 951, "Valoramos el resultado.", "We assess the result.")]),
    (445, "argumentar", "verb", None, "to argue; to make a case", 2400, "B1", 0.6, "opinions and workplace", "SPANISH_BREADTH_PLAN.md B1 opinions/workplace topic", [(949, 952, "Argumento mi posición.", "I argue my position."), (950, 953, "Ella argumenta con calma.", "She makes her case calmly.")]),
    (446, "aclarar", "verb", None, "to clarify", 1350, "B1", 0.5, "workplace and services", "SPANISH_BREADTH_PLAN.md B1 workplace/services topic", [(951, 954, "Aclaro la duda.", "I clarify the doubt."), (952, 955, "Necesito aclarar el cargo.", "I need to clarify the charge.")]),
    (447, "corregir", "verb", None, "to correct", 1400, "B1", 0.5, "workplace and services", "SPANISH_BREADTH_PLAN.md B1 workplace/services topic", [(953, 956, "Corrijo el error.", "I correct the mistake."), (954, 957, "Corrigen el documento.", "They correct the document.")]),
    (448, "cometer", "verb", None, "to commit; to make", 1300, "B1", 0.5, "problems and narration", "SPANISH_BREADTH_PLAN.md B1 problems/narration topic", [(955, 958, "Cometo un error.", "I make a mistake."), (956, 959, "No quiero cometer otro error.", "I do not want to make another mistake.")]),
    (449, "fallar", "verb", None, "to fail", 1300, "B1", 0.5, "problems and services", "SPANISH_BREADTH_PLAN.md B1 problems/services topic", [(957, 960, "Falla la aplicación.", "The app fails."), (958, 961, "El cajero falla otra vez.", "The ATM fails again.")]),
    (450, "funcionar", "verb", None, "to work; to function", 950, "B1", 0.5, "problems and services", "SPANISH_BREADTH_PLAN.md B1 problems/services topic", [(959, 962, "El ascensor funciona.", "The elevator works."), (960, 963, "La tarjeta no funciona.", "The card does not work.")]),
    (451, "bloquear", "verb", None, "to block", 1800, "B1", 0.5, "banking and problems", "SPANISH_BREADTH_PLAN.md B1 banking/problems topic", [(961, 964, "Bloqueo mi tarjeta.", "I block my card."), (962, 965, "El sistema bloquea la cuenta.", "The system blocks the account.")]),
    (452, "desbloquear", "verb", None, "to unblock", 2600, "B1", 0.6, "banking and services", "SPANISH_BREADTH_PLAN.md B1 banking/services topic", [(963, 966, "Desbloqueo la cuenta.", "I unblock the account."), (964, 967, "Necesito desbloquear mi tarjeta.", "I need to unblock my card.")]),
    (453, "cargar", "verb", None, "to charge; to load", 1100, "B1", 0.5, "banking and services", "SPANISH_BREADTH_PLAN.md B1 banking/services topic", [(965, 968, "Cargan una cuota.", "They charge a fee."), (966, 969, "Cargo el teléfono.", "I charge the phone.")]),
    (454, "cobertura", "noun", "F", "coverage", 1800, "B1", 0.5, "health and services", "SPANISH_BREADTH_PLAN.md B1 health/services topic", [(967, 970, "El seguro tiene cobertura.", "The insurance has coverage."), (968, 971, "Pregunto por la cobertura.", "I ask about the coverage.")]),
    (455, "seguridad", "noun", "F", "security; safety", 650, "B1", 0.5, "health housing and banking", "hermitdave/FrequencyWords high-frequency spine", [(969, 972, "La seguridad es importante.", "Safety is important."), (970, 973, "Reviso la seguridad de la cuenta.", "I check the security of the account.")]),
    (456, "riesgo", "noun", "M", "risk", 850, "B1", 0.5, "health and banking", "hermitdave/FrequencyWords high-frequency spine", [(971, 974, "Hay un riesgo.", "There is a risk."), (972, 975, "El médico explica el riesgo.", "The doctor explains the risk.")]),
    (457, "daño", "noun", "M", "damage; harm", 1100, "B1", 0.5, "problems and health", "SPANISH_BREADTH_PLAN.md B1 problems/health topic", [(973, 976, "El daño es grave.", "The damage is serious."), (974, 977, "Quiero evitar el daño.", "I want to avoid harm.")]),
    (458, "avería", "noun", "F", "breakdown; fault", 2300, "B1", 0.6, "housing and repairs", "SPANISH_BREADTH_PLAN.md B1 housing/repairs topic", [(975, 978, "Hay una avería en casa.", "There is a fault at home."), (976, 979, "La avería es grave.", "The fault is serious.")]),
    (459, "gasto", "noun", "M", "expense", 1000, "B1", 0.5, "banking and housing", "SPANISH_BREADTH_PLAN.md B1 banking/housing topic", [(977, 980, "El gasto es mensual.", "The expense is monthly."), (978, 981, "Reduzco mis gastos.", "I reduce my expenses.")]),
    (460, "ingreso", "noun", "M", "income; admission", 1100, "B1", 0.5, "banking and health", "SPANISH_BREADTH_PLAN.md B1 banking/health topic", [(979, 982, "Tengo un ingreso fijo.", "I have a fixed income."), (980, 983, "El ingreso al hospital es mañana.", "Admission to the hospital is tomorrow.")]),
    (461, "saldo", "noun", "M", "balance", 1800, "B1", 0.5, "banking", "SPANISH_BREADTH_PLAN.md B1 banking topic", [(981, 984, "Consulto mi saldo.", "I check my balance."), (982, 985, "El saldo es bajo.", "The balance is low.")]),
    (462, "cargo", "noun", "M", "charge; position", 1000, "B1", 0.5, "banking and workplace", "SPANISH_BREADTH_PLAN.md B1 banking/workplace topic", [(983, 986, "No reconozco el cargo.", "I do not recognize the charge."), (984, 987, "El cargo aparece hoy.", "The charge appears today.")]),
    (463, "depósito", "noun", "M", "deposit", 1500, "B1", 0.5, "banking and housing", "SPANISH_BREADTH_PLAN.md B1 banking/housing topic", [(985, 988, "Pago el depósito.", "I pay the deposit."), (986, 989, "El depósito es alto.", "The deposit is high.")]),
    (464, "garantía", "noun", "F", "warranty; guarantee", 1400, "B1", 0.5, "services and housing", "SPANISH_BREADTH_PLAN.md B1 services/housing topic", [(987, 990, "La garantía cubre la reparación.", "The warranty covers the repair."), (988, 991, "Necesito la garantía.", "I need the warranty.")]),
    (465, "reserva", "noun", "F", "reservation", 1100, "B1", 0.5, "travel and appointments", "SPANISH_BREADTH_PLAN.md B1 travel/appointments topic", [(989, 992, "Confirmo la reserva.", "I confirm the reservation."), (990, 993, "La reserva está pendiente.", "The reservation is pending.")]),
    (466, "estancia", "noun", "F", "stay", 1700, "B1", 0.5, "travel and lodging", "SPANISH_BREADTH_PLAN.md B1 travel/lodging topic", [(991, 994, "La estancia dura tres días.", "The stay lasts three days."), (992, 995, "Pago la estancia hoy.", "I pay for the stay today.")]),
    (467, "recepción", "noun", "F", "reception; front desk", 1500, "B1", 0.5, "lodging and services", "SPANISH_BREADTH_PLAN.md B1 lodging/services topic", [(993, 996, "Pregunto en recepción.", "I ask at reception."), (994, 997, "La recepción está abierta.", "The front desk is open.")]),
    (468, "maleta", "noun", "F", "suitcase", 1600, "B1", 0.5, "travel", "SPANISH_BREADTH_PLAN.md B1 travel topic", [(995, 998, "Preparo la maleta.", "I pack the suitcase."), (996, 999, "La maleta pesa mucho.", "The suitcase weighs a lot.")]),
    (469, "embarque", "noun", "M", "boarding", 2000, "B1", 0.6, "travel and transit", "SPANISH_BREADTH_PLAN.md B1 travel/transit topic", [(997, 1000, "El embarque empieza ahora.", "Boarding starts now."), (998, 1001, "Espero el embarque.", "I wait for boarding.")]),
    (470, "salida", "noun", "F", "departure; exit", 700, "B1", 0.5, "travel and transit", "hermitdave/FrequencyWords high-frequency spine", [(999, 1002, "La salida está cerca.", "The exit is nearby."), (1000, 1003, "La salida se retrasa.", "The departure is delayed.")]),
    (471, "llegada", "noun", "F", "arrival", 850, "B1", 0.5, "travel and narration", "SPANISH_BREADTH_PLAN.md B1 travel/narration topic", [(1001, 1004, "La llegada es a las ocho.", "The arrival is at eight."), (1002, 1005, "Confirmo la llegada.", "I confirm the arrival.")]),
    (472, "conexión", "noun", "F", "connection", 950, "B1", 0.5, "travel and services", "SPANISH_BREADTH_PLAN.md B1 travel/services topic", [(1003, 1006, "Pierdo la conexión.", "I miss the connection."), (1004, 1007, "La conexión funciona bien.", "The connection works well.")]),
    (473, "frontera", "noun", "F", "border", 1200, "B1", 0.5, "travel", "SPANISH_BREADTH_PLAN.md B1 travel topic", [(1005, 1008, "Cruzamos la frontera.", "We cross the border."), (1006, 1009, "La frontera está cerrada.", "The border is closed.")]),
    (474, "visado", "noun", "M", "visa", 2200, "B1", 0.6, "travel and services", "SPANISH_BREADTH_PLAN.md B1 travel/services topic", [(1007, 1010, "Necesito un visado.", "I need a visa."), (1008, 1011, "Tramito el visado.", "I process the visa.")]),
    (475, "barrio", "noun", "M", "neighborhood", 1000, "B1", 0.5, "housing and social", "SPANISH_BREADTH_PLAN.md B1 housing/social topic", [(1009, 1012, "Vivo en este barrio.", "I live in this neighborhood."), (1010, 1013, "El barrio es tranquilo.", "The neighborhood is quiet.")]),
    (476, "edificio", "noun", "M", "building", 750, "B1", 0.5, "housing and services", "hermitdave/FrequencyWords high-frequency spine", [(1011, 1014, "El edificio es nuevo.", "The building is new."), (1012, 1015, "Trabajo en ese edificio.", "I work in that building.")]),
    (477, "calefacción", "noun", "F", "heating", 2100, "B1", 0.6, "housing and services", "SPANISH_BREADTH_PLAN.md B1 housing/services topic", [(1013, 1016, "La calefacción no funciona.", "The heating does not work."), (1014, 1017, "Enciendo la calefacción.", "I turn on the heating.")]),
    (478, "mudanza", "noun", "F", "move; moving house", 2300, "B1", 0.6, "housing", "SPANISH_BREADTH_PLAN.md B1 housing topic", [(1015, 1018, "La mudanza empieza mañana.", "The move starts tomorrow."), (1016, 1019, "Organizo la mudanza.", "I organize the move.")]),
    (479, "contraseña", "noun", "F", "password", 2200, "B1", 0.6, "services and banking", "SPANISH_BREADTH_PLAN.md B1 banking/services topic", [(1017, 1020, "Olvido la contraseña.", "I forget the password."), (1018, 1021, "Cambio mi contraseña.", "I change my password.")]),
    (480, "usuario", "noun", "M", "user", 1200, "B1", 0.5, "services and technology", "SPANISH_BREADTH_PLAN.md B1 services topic", [(1019, 1022, "El usuario espera ayuda.", "The user waits for help."), (1020, 1023, "Registro un usuario nuevo.", "I register a new user.")]),
    (481, "aplicación", "noun", "F", "application; app", 1100, "B1", 0.5, "services and technology", "SPANISH_BREADTH_PLAN.md B1 services topic", [(1021, 1024, "La aplicación falla.", "The app fails."), (1022, 1025, "Uso la aplicación del banco.", "I use the bank app.")]),
    (482, "mensaje", "noun", "M", "message", 800, "B1", 0.5, "social and services", "hermitdave/FrequencyWords high-frequency spine", [(1023, 1026, "Escribo un mensaje.", "I write a message."), (1024, 1027, "Recibo el mensaje tarde.", "I receive the message late.")]),
    (483, "llamada", "noun", "F", "call", 900, "B1", 0.5, "social and services", "SPANISH_BREADTH_PLAN.md B1 social/services topic", [(1025, 1028, "Hago una llamada.", "I make a call."), (1026, 1029, "Espero tu llamada.", "I wait for your call.")]),
    (484, "código", "noun", "M", "code", 1000, "B1", 0.5, "services and banking", "SPANISH_BREADTH_PLAN.md B1 banking/services topic", [(1027, 1030, "Escribo el código.", "I write the code."), (1028, 1031, "El banco envía un código.", "The bank sends a code.")]),
    (485, "copia", "noun", "F", "copy", 1100, "B1", 0.5, "workplace and services", "SPANISH_BREADTH_PLAN.md B1 workplace/services topic", [(1029, 1032, "Necesito una copia.", "I need a copy."), (1030, 1033, "Envío la copia del documento.", "I send the copy of the document.")]),
    (486, "firma", "noun", "F", "signature", 1300, "B1", 0.5, "workplace and services", "SPANISH_BREADTH_PLAN.md B1 workplace/services topic", [(1031, 1034, "Falta la firma.", "The signature is missing."), (1032, 1035, "La firma aparece aquí.", "The signature appears here.")]),
    (487, "acuerdo", "noun", "M", "agreement", 760, "B1", 0.5, "workplace and conflict", "hermitdave/FrequencyWords high-frequency spine", [(1033, 1036, "Tenemos un acuerdo.", "We have an agreement."), (1034, 1037, "El acuerdo termina hoy.", "The agreement ends today.")]),
    (488, "decisión", "noun", "F", "decision", 720, "B1", 0.5, "workplace and opinions", "hermitdave/FrequencyWords high-frequency spine", [(1035, 1038, "Tomo una decisión.", "I make a decision."), (1036, 1039, "La decisión es difícil.", "The decision is difficult.")]),
    (489, "duda", "noun", "F", "doubt; question", 1000, "B1", 0.5, "opinions and services", "SPANISH_BREADTH_PLAN.md B1 opinions/services topic", [(1037, 1040, "Tengo una duda.", "I have a question."), (1038, 1041, "La duda sigue pendiente.", "The question is still pending.")]),
    (490, "opción", "noun", "F", "option", 800, "B1", 0.5, "planning and services", "SPANISH_BREADTH_PLAN.md B1 planning/services topic", [(1039, 1042, "Elijo otra opción.", "I choose another option."), (1040, 1043, "La opción es barata.", "The option is cheap.")]),
    (491, "ventaja", "noun", "F", "advantage", 1300, "B1", 0.5, "opinions and comparisons", "SPANISH_BREADTH_PLAN.md B1 opinions/comparisons topic", [(1041, 1044, "Es una ventaja clara.", "It is a clear advantage."), (1042, 1045, "Comparamos cada ventaja.", "We compare each advantage.")]),
    (492, "desventaja", "noun", "F", "disadvantage", 2300, "B1", 0.6, "opinions and comparisons", "SPANISH_BREADTH_PLAN.md B1 opinions/comparisons topic", [(1043, 1046, "Hay una desventaja.", "There is a disadvantage."), (1044, 1047, "Explico la desventaja.", "I explain the disadvantage.")]),
    (493, "culpa", "noun", "F", "fault; blame", 1200, "B1", 0.5, "conflict and problems", "SPANISH_BREADTH_PLAN.md B1 conflict/problems topic", [(1045, 1048, "No es mi culpa.", "It is not my fault."), (1046, 1049, "Acepto la culpa.", "I accept the blame.")]),
    (494, "error", "noun", "M", "mistake; error", 850, "B1", 0.5, "problems and services", "SPANISH_BREADTH_PLAN.md B1 problems/services topic", [(1047, 1050, "El error aparece ahora.", "The error appears now."), (1048, 1051, "Ese error causa problemas.", "That error causes problems.")]),
    (495, "solución", "noun", "F", "solution", 900, "B1", 0.5, "problems and solutions", "SPANISH_BREADTH_PLAN.md B1 problems/solutions topic", [(1049, 1052, "Busco una solución.", "I look for a solution."), (1050, 1053, "La solución funciona.", "The solution works.")]),
    (496, "alternativa", "noun", "F", "alternative", 1200, "B1", 0.5, "planning and opinions", "SPANISH_BREADTH_PLAN.md B1 planning/opinions topic", [(1051, 1054, "Tengo una alternativa.", "I have an alternative."), (1052, 1055, "La alternativa parece mejor.", "The alternative seems better.")]),
    (497, "prioridad", "noun", "F", "priority", 1600, "B1", 0.5, "workplace and planning", "SPANISH_BREADTH_PLAN.md B1 workplace/planning topic", [(1053, 1056, "Es mi prioridad.", "It is my priority."), (1054, 1057, "Cambiamos la prioridad.", "We change the priority.")]),
    (498, "responsabilidad", "noun", "F", "responsibility", 900, "B1", 0.5, "workplace and obligations", "SPANISH_BREADTH_PLAN.md B1 workplace/obligations topic", [(1055, 1058, "Tengo una responsabilidad.", "I have a responsibility."), (1056, 1059, "La responsabilidad es grande.", "The responsibility is big.")]),
    (499, "requisito", "noun", "M", "requirement", 1900, "B1", 0.5, "services and work", "SPANISH_BREADTH_PLAN.md B1 services/work topic", [(1057, 1060, "Falta un requisito.", "A requirement is missing."), (1058, 1061, "El requisito es obligatorio.", "The requirement is mandatory.")]),
    (500, "norma", "noun", "F", "rule; standard", 900, "B1", 0.5, "workplace and services", "hermitdave/FrequencyWords high-frequency spine", [(1059, 1062, "Respeto la norma.", "I respect the rule."), (1060, 1063, "La norma cambia mañana.", "The rule changes tomorrow.")]),
    (501, "multa", "noun", "F", "fine", 1800, "B1", 0.5, "services and travel", "SPANISH_BREADTH_PLAN.md B1 services/travel topic", [(1061, 1064, "Pago una multa.", "I pay a fine."), (1062, 1065, "La multa es alta.", "The fine is high.")]),
    (502, "reclamación", "noun", "F", "claim; complaint", 2100, "B1", 0.6, "services and complaints", "SPANISH_BREADTH_PLAN.md B1 services/complaints topic", [(1063, 1066, "Presento una reclamación.", "I file a complaint."), (1064, 1067, "La reclamación sigue pendiente.", "The complaint is still pending.")]),
    (503, "atención", "noun", "F", "attention; service", 650, "B1", 0.5, "services and health", "hermitdave/FrequencyWords high-frequency spine", [(1065, 1068, "La atención es buena.", "The service is good."), (1066, 1069, "Necesito atención médica.", "I need medical attention.")]),
    (504, "cuidado", "noun", "M", "care", 800, "B1", 0.5, "health and social", "SPANISH_BREADTH_PLAN.md B1 health/social topic", [(1067, 1070, "El cuidado es importante.", "Care is important."), (1068, 1071, "Necesito más cuidado.", "I need more care.")]),
    (505, "dolor", "noun", "M", "pain", 700, "B1", 0.5, "health", "hermitdave/FrequencyWords high-frequency spine", [(1069, 1072, "Tengo dolor de espalda.", "I have back pain."), (1070, 1073, "El dolor mejora.", "The pain improves.")]),
    (506, "fiebre", "noun", "F", "fever", 1600, "B1", 0.5, "health", "SPANISH_BREADTH_PLAN.md B1 health topic", [(1071, 1074, "Tengo fiebre.", "I have a fever."), (1072, 1075, "La fiebre baja.", "The fever goes down.")]),
    (507, "tos", "noun", "F", "cough", 1900, "B1", 0.5, "health", "SPANISH_BREADTH_PLAN.md B1 health topic", [(1073, 1076, "Tengo tos.", "I have a cough."), (1074, 1077, "La tos empeora.", "The cough gets worse.")]),
    (508, "herida", "noun", "F", "wound", 1500, "B1", 0.5, "health", "SPANISH_BREADTH_PLAN.md B1 health topic", [(1075, 1078, "La herida duele.", "The wound hurts."), (1076, 1079, "Reviso la herida.", "I check the wound.")]),
    (509, "espalda", "noun", "F", "back", 1200, "B1", 0.5, "health and body", "SPANISH_BREADTH_PLAN.md B1 health/body topic", [(1077, 1080, "Me duele la espalda.", "My back hurts."), (1078, 1081, "Cuido mi espalda.", "I take care of my back.")]),
    (510, "brazo", "noun", "M", "arm", 900, "B1", 0.5, "health and body", "hermitdave/FrequencyWords high-frequency spine", [(1079, 1082, "Me duele el brazo.", "My arm hurts."), (1080, 1083, "Levanto el brazo.", "I raise my arm.")]),
    (511, "pierna", "noun", "F", "leg", 1000, "B1", 0.5, "health and body", "hermitdave/FrequencyWords high-frequency spine", [(1081, 1084, "Me duele la pierna.", "My leg hurts."), (1082, 1085, "La pierna mejora.", "The leg improves.")]),
    (512, "estómago", "noun", "M", "stomach", 1500, "B1", 0.5, "health and body", "SPANISH_BREADTH_PLAN.md B1 health/body topic", [(1083, 1086, "Me duele el estómago.", "My stomach hurts."), (1084, 1087, "El estómago está mejor.", "The stomach is better.")]),
    (513, "positivo", "adjective", None, "positive", 900, "B1", 0.5, "opinions and health", "hermitdave/FrequencyWords high-frequency spine", [(1085, 1088, "El resultado es positivo.", "The result is positive."), (1086, 1089, "Tengo una actitud positiva.", "I have a positive attitude.")]),
    (514, "negativo", "adjective", None, "negative", 950, "B1", 0.5, "opinions and health", "SPANISH_BREADTH_PLAN.md B1 opinions/health topic", [(1087, 1090, "El resultado es negativo.", "The result is negative."), (1088, 1091, "El comentario es negativo.", "The comment is negative.")]),
    (515, "útil", "adjective", None, "useful", 1100, "B1", 0.5, "opinions and services", "SPANISH_BREADTH_PLAN.md B1 opinions/services topic", [(1089, 1092, "La información es útil.", "The information is useful."), (1090, 1093, "Este consejo es útil.", "This advice is useful.")]),
    (516, "inútil", "adjective", None, "useless", 2200, "B1", 0.6, "opinions and complaints", "SPANISH_BREADTH_PLAN.md B1 opinions/complaints topic", [(1091, 1094, "La respuesta es inútil.", "The answer is useless."), (1092, 1095, "El trámite parece inútil.", "The procedure seems useless.")]),
])


AI_ACCELERATED_PACK_A2_012 = build_ai_accelerated_pack([
    (517, "sin duda", "adverbial phrase", None, "without a doubt", 900, "B1", 0.5, "opinions and emphasis", "SPANISH_BREADTH_PLAN.md B1 connectors/opinions topic", [(1093, 1096, "Sin duda, es importante.", "Without a doubt, it is important."), (1094, 1097, "Sin duda, necesitamos ayuda.", "Without a doubt, we need help.")]),
    (518, "tal vez", "adverbial phrase", None, "maybe; perhaps", 850, "B1", 0.5, "opinions and uncertainty", "SPANISH_BREADTH_PLAN.md B1 connectors/opinions topic", [(1095, 1098, "Tal vez llegue tarde.", "Maybe I will arrive late."), (1096, 1099, "Tal vez sea necesario.", "Perhaps it is necessary.")]),
    (519, "de hecho", "adverbial phrase", None, "in fact", 700, "B1", 0.5, "connectors and opinions", "SPANISH_BREADTH_PLAN.md B1 connectors topic", [(1097, 1100, "De hecho, prefiero llamar.", "In fact, I prefer to call."), (1098, 1101, "De hecho, el plan funciona.", "In fact, the plan works.")]),
    (520, "por supuesto", "adverbial phrase", None, "of course", 600, "B1", 0.5, "social interaction", "SPANISH_BREADTH_PLAN.md B1 common chunks topic", [(1099, 1102, "Por supuesto, puedo ayudar.", "Of course, I can help."), (1100, 1103, "Por supuesto, acepto.", "Of course, I accept.")]),
    (521, "a tiempo", "adverbial phrase", None, "on time", 700, "B1", 0.5, "appointments and travel", "SPANISH_BREADTH_PLAN.md B1 common chunks topic", [(1101, 1104, "Llego a tiempo.", "I arrive on time."), (1102, 1105, "El tren sale a tiempo.", "The train leaves on time.")]),
    (522, "a menudo", "adverbial phrase", None, "often", 900, "B1", 0.5, "narration and routine", "SPANISH_BREADTH_PLAN.md B1 narration/routine topic", [(1103, 1106, "A menudo trabajo tarde.", "I often work late."), (1104, 1107, "A menudo llamo al banco.", "I often call the bank.")]),
    (523, "en serio", "adverbial phrase", None, "seriously", 1200, "B1", 0.5, "opinions and social interaction", "SPANISH_BREADTH_PLAN.md B1 common chunks topic", [(1105, 1108, "Hablo en serio.", "I am speaking seriously."), (1106, 1109, "Tomo el problema en serio.", "I take the problem seriously.")]),
    (524, "por cierto", "adverbial phrase", None, "by the way", 1000, "B1", 0.5, "connectors and social interaction", "SPANISH_BREADTH_PLAN.md B1 common chunks topic", [(1107, 1110, "Por cierto, tengo una pregunta.", "By the way, I have a question."), (1108, 1111, "Por cierto, la cita cambió.", "By the way, the appointment changed.")]),
    (525, "en general", "adverbial phrase", None, "in general", 650, "B1", 0.5, "opinions and summaries", "SPANISH_BREADTH_PLAN.md B1 connectors topic", [(1109, 1112, "En general, estoy satisfecho.", "In general, I am satisfied."), (1110, 1113, "En general, el servicio mejora.", "In general, the service improves.")]),
    (526, "cuanto antes", "adverbial phrase", None, "as soon as possible", 1500, "B1", 0.6, "appointments and urgency", "SPANISH_BREADTH_PLAN.md B1 common chunks topic", [(1111, 1114, "Necesito ayuda cuanto antes.", "I need help as soon as possible."), (1112, 1115, "Llama cuanto antes.", "Call as soon as possible.")]),
    (527, "hasta ahora", "adverbial phrase", None, "until now; so far", 700, "B1", 0.5, "narration", "SPANISH_BREADTH_PLAN.md B1 narration topic", [(1113, 1116, "Hasta ahora todo funciona.", "So far everything works."), (1114, 1117, "Hasta ahora no hay respuesta.", "So far there is no answer.")]),
    (528, "desde entonces", "adverbial phrase", None, "since then", 1000, "B1", 0.5, "past narration", "SPANISH_BREADTH_PLAN.md B1 narration topic", [(1115, 1118, "Desde entonces vivo aquí.", "Since then I live here."), (1116, 1119, "Desde entonces trabajo mejor.", "Since then I work better.")]),
    (529, "poco a poco", "adverbial phrase", None, "little by little", 1300, "B1", 0.5, "narration and progress", "SPANISH_BREADTH_PLAN.md B1 narration topic", [(1117, 1120, "Poco a poco mejoro.", "Little by little I improve."), (1118, 1121, "Poco a poco resolvemos el problema.", "Little by little we solve the problem.")]),
    (530, "admitir", "verb", None, "to admit", 950, "B1", 0.5, "opinions and conflict", "SPANISH_BREADTH_PLAN.md B1 opinions/conflict topic", [(1119, 1122, "Admito mi error.", "I admit my mistake."), (1120, 1123, "La empresa admite el problema.", "The company admits the problem.")]),
    (531, "exigir", "verb", None, "to demand; to require", 1200, "B1", 0.5, "services and conflict", "SPANISH_BREADTH_PLAN.md B1 services/conflict topic", [(1121, 1124, "Exijo una solución.", "I demand a solution."), (1122, 1125, "El trámite exige un documento.", "The procedure requires a document.")]),
    (532, "asumir", "verb", None, "to assume; to take on", 1100, "B1", 0.5, "workplace and responsibility", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [(1123, 1126, "Asumo la responsabilidad.", "I take responsibility."), (1124, 1127, "Asumimos el riesgo.", "We assume the risk.")]),
    (533, "reconocer", "verb", None, "to recognize", 900, "B1", 0.5, "opinions and banking", "SPANISH_BREADTH_PLAN.md B1 opinions/banking topic", [(1125, 1128, "Reconozco el cargo.", "I recognize the charge."), (1126, 1129, "Reconocemos el problema.", "We recognize the problem.")]),
    (534, "demostrar", "verb", None, "to demonstrate; to show", 900, "B1", 0.5, "workplace and opinions", "SPANISH_BREADTH_PLAN.md B1 workplace/opinions topic", [(1127, 1130, "Demuestro el resultado.", "I demonstrate the result."), (1128, 1131, "El informe demuestra el riesgo.", "The report shows the risk.")]),
    (535, "sugerir", "verb", None, "to suggest", 1400, "B1", 0.5, "advice and workplace", "SPANISH_BREADTH_PLAN.md B1 advice/workplace topic", [(1129, 1132, "Sugiero otra opción.", "I suggest another option."), (1130, 1133, "Ella sugiere esperar.", "She suggests waiting.")]),
    (536, "debatir", "verb", None, "to debate", 1700, "B1", 0.5, "opinions and workplace", "SPANISH_BREADTH_PLAN.md B1 opinions/workplace topic", [(1131, 1134, "Debato el plan.", "I debate the plan."), (1132, 1135, "Debatimos la decisión.", "We debate the decision.")]),
    (537, "interrumpir", "verb", None, "to interrupt", 1700, "B1", 0.5, "social and workplace conflict", "SPANISH_BREADTH_PLAN.md B1 social/workplace topic", [(1133, 1136, "Interrumpo la reunión.", "I interrupt the meeting."), (1134, 1137, "No quiero interrumpir.", "I do not want to interrupt.")]),
    (538, "competir", "verb", None, "to compete", 1500, "B1", 0.5, "workplace and goals", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [(1135, 1138, "Compito por el puesto.", "I compete for the position."), (1136, 1139, "La empresa compite bien.", "The company competes well.")]),
    (539, "liderar", "verb", None, "to lead", 1900, "B1", 0.5, "workplace", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [(1137, 1140, "Lidero el equipo.", "I lead the team."), (1138, 1141, "Ella lidera el proyecto.", "She leads the project.")]),
    (540, "supervisar", "verb", None, "to supervise", 2100, "B1", 0.6, "workplace", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [(1139, 1142, "Superviso la tarea.", "I supervise the task."), (1140, 1143, "Supervisamos el trabajo.", "We supervise the work.")]),
    (541, "despedir", "verb", None, "to dismiss; to fire", 1300, "B1", 0.5, "workplace conflict", "SPANISH_BREADTH_PLAN.md B1 workplace/conflict topic", [(1141, 1144, "Despiden al empleado.", "They fire the employee."), (1142, 1145, "No quiero despedir a nadie.", "I do not want to fire anyone.")]),
    (542, "jubilarse", "verb", None, "to retire", 2300, "B1", 0.6, "work and life plans", "SPANISH_BREADTH_PLAN.md B1 work/life topic", [(1143, 1146, "Me jubilo este año.", "I retire this year."), (1144, 1147, "Mi jefe se jubila pronto.", "My boss retires soon.")]),
    (543, "faltar", "verb", None, "to be missing; to lack", 850, "B1", 0.5, "services and problems", "SPANISH_BREADTH_PLAN.md B1 services/problems topic", [(1145, 1148, "Falta una firma.", "A signature is missing."), (1146, 1149, "Faltan dos requisitos.", "Two requirements are missing.")]),
    (544, "sobrar", "verb", None, "to be extra; to be left over", 2300, "B1", 0.6, "money and planning", "SPANISH_BREADTH_PLAN.md B1 planning/money topic", [(1147, 1150, "Sobra dinero.", "There is money left over."), (1148, 1151, "Sobran dos entradas.", "There are two tickets left over.")]),
    (545, "matricularse", "verb", None, "to enroll", 2500, "B1", 0.6, "public services and education", "SPANISH_BREADTH_PLAN.md B1 public services topic", [(1149, 1152, "Me matriculo en el curso.", "I enroll in the course."), (1150, 1153, "Necesito matricularme hoy.", "I need to enroll today.")]),
    (546, "inscribirse", "verb", None, "to sign up; to register", 2200, "B1", 0.6, "public services and appointments", "SPANISH_BREADTH_PLAN.md B1 public services topic", [(1151, 1154, "Me inscribo en la lista.", "I sign up on the list."), (1152, 1155, "Nos inscribimos mañana.", "We register tomorrow.")]),
    (547, "votar", "verb", None, "to vote", 900, "B1", 0.5, "public services", "hermitdave/FrequencyWords high-frequency spine", [(1153, 1156, "Voto en la escuela.", "I vote at the school."), (1154, 1157, "Quiero votar temprano.", "I want to vote early.")]),
    (548, "caducar", "verb", None, "to expire", 2300, "B1", 0.6, "public services and banking", "SPANISH_BREADTH_PLAN.md B1 services topic", [(1155, 1158, "Mi tarjeta caduca mañana.", "My card expires tomorrow."), (1156, 1159, "El permiso caduca pronto.", "The permit expires soon.")]),
    (549, "autorizar", "verb", None, "to authorize", 1500, "B1", 0.5, "public services and banking", "SPANISH_BREADTH_PLAN.md B1 services/banking topic", [(1157, 1160, "Autorizo el pago.", "I authorize the payment."), (1158, 1161, "El banco autoriza la transferencia.", "The bank authorizes the transfer.")]),
    (550, "financiar", "verb", None, "to finance", 1500, "B1", 0.5, "banking and housing", "SPANISH_BREADTH_PLAN.md B1 banking/housing topic", [(1159, 1162, "Financio el proyecto.", "I finance the project."), (1160, 1163, "El banco financia la vivienda.", "The bank finances the home.")]),
    (551, "invertir", "verb", None, "to invest", 1100, "B1", 0.5, "money and planning", "SPANISH_BREADTH_PLAN.md B1 banking/planning topic", [(1161, 1164, "Invierto mi dinero.", "I invest my money."), (1162, 1165, "Invertimos en la empresa.", "We invest in the company.")]),
    (552, "gastar", "verb", None, "to spend", 900, "B1", 0.5, "money and housing", "SPANISH_BREADTH_PLAN.md B1 banking/housing topic", [(1163, 1166, "Gasto demasiado dinero.", "I spend too much money."), (1164, 1167, "No quiero gastar más.", "I do not want to spend more.")]),
    (553, "adeudar", "verb", None, "to owe", 2400, "B1", 0.6, "money and obligations", "SPANISH_BREADTH_PLAN.md B1 banking/obligations topic", [(1165, 1168, "Adeudo dinero al banco.", "I owe money to the bank."), (1166, 1169, "No quiero adeudar más.", "I do not want to owe more.")]),
    (554, "recuperar", "verb", None, "to recover", 950, "B1", 0.5, "health and money", "SPANISH_BREADTH_PLAN.md B1 health/money topic", [(1167, 1170, "Recupero mi dinero.", "I recover my money."), (1168, 1171, "Me recupero poco a poco.", "I recover little by little.")]),
    (555, "marearse", "verb", None, "to get dizzy", 2600, "B1", 0.6, "medical", "SPANISH_BREADTH_PLAN.md B1 medical topic", [(1169, 1172, "Me mareo en el autobús.", "I get dizzy on the bus."), (1170, 1173, "No quiero marearme.", "I do not want to get dizzy.")]),
    (556, "vomitar", "verb", None, "to vomit", 2600, "B1", 0.6, "medical", "SPANISH_BREADTH_PLAN.md B1 medical topic", [(1171, 1174, "El niño vomita.", "The child vomits."), (1172, 1175, "Necesito vomitar.", "I need to vomit.")]),
    (557, "estornudar", "verb", None, "to sneeze", 2700, "B1", 0.6, "medical", "SPANISH_BREADTH_PLAN.md B1 medical topic", [(1173, 1176, "Estornudo mucho.", "I sneeze a lot."), (1174, 1177, "Ella estornuda otra vez.", "She sneezes again.")]),
    (558, "adelgazar", "verb", None, "to lose weight", 2400, "B1", 0.6, "health", "SPANISH_BREADTH_PLAN.md B1 health topic", [(1175, 1178, "Quiero adelgazar.", "I want to lose weight."), (1176, 1179, "Adelgazo poco a poco.", "I lose weight little by little.")]),
    (559, "engordar", "verb", None, "to gain weight", 2400, "B1", 0.6, "health", "SPANISH_BREADTH_PLAN.md B1 health topic", [(1177, 1180, "No quiero engordar.", "I do not want to gain weight."), (1178, 1181, "Engordo durante las vacaciones.", "I gain weight during vacation.")]),
    (560, "pintar", "verb", None, "to paint", 1100, "B1", 0.5, "housing and repairs", "SPANISH_BREADTH_PLAN.md B1 housing/repairs topic", [(1179, 1182, "Pinto la pared.", "I paint the wall."), (1180, 1183, "Pintamos el apartamento.", "We paint the apartment.")]),
    (561, "construir", "verb", None, "to build", 850, "B1", 0.5, "housing and work", "hermitdave/FrequencyWords high-frequency spine", [(1181, 1184, "Construyo una casa.", "I build a house."), (1182, 1185, "La empresa construye viviendas.", "The company builds homes.")]),
    (562, "conectar", "verb", None, "to connect", 1300, "B1", 0.5, "housing and services", "SPANISH_BREADTH_PLAN.md B1 services/housing topic", [(1183, 1186, "Conecto el teléfono.", "I connect the phone."), (1184, 1187, "Conectamos el servicio.", "We connect the service.")]),
    (563, "desconectar", "verb", None, "to disconnect", 2200, "B1", 0.6, "housing and services", "SPANISH_BREADTH_PLAN.md B1 services/housing topic", [(1185, 1188, "Desconecto la calefacción.", "I disconnect the heating."), (1186, 1189, "Necesito desconectar el equipo.", "I need to disconnect the equipment.")]),
    (564, "gotear", "verb", None, "to drip; to leak", 2700, "B1", 0.6, "housing and repairs", "SPANISH_BREADTH_PLAN.md B1 housing/repairs topic", [(1187, 1190, "El grifo gotea.", "The faucet drips."), (1188, 1191, "La tubería gotea.", "The pipe leaks.")]),
    (565, "inundar", "verb", None, "to flood", 1900, "B1", 0.5, "housing and problems", "SPANISH_BREADTH_PLAN.md B1 housing/problems topic", [(1189, 1192, "El agua inunda el baño.", "The water floods the bathroom."), (1190, 1193, "La lluvia inunda la calle.", "The rain floods the street.")]),
    (566, "despegar", "verb", None, "to take off", 2200, "B1", 0.6, "travel", "SPANISH_BREADTH_PLAN.md B1 travel topic", [(1191, 1194, "El avión despega tarde.", "The plane takes off late."), (1192, 1195, "Despegamos a tiempo.", "We take off on time.")]),
    (567, "hospedarse", "verb", None, "to stay; to lodge", 2600, "B1", 0.6, "travel and lodging", "SPANISH_BREADTH_PLAN.md B1 travel/lodging topic", [(1193, 1196, "Me hospedo en un hotel.", "I stay at a hotel."), (1194, 1197, "Nos hospedamos cerca.", "We stay nearby.")]),
    (568, "gobierno", "noun", "M", "government", 500, "B1", 0.5, "public services", "hermitdave/FrequencyWords high-frequency spine", [(1195, 1198, "El gobierno anuncia cambios.", "The government announces changes."), (1196, 1199, "Trabajo con el gobierno.", "I work with the government.")]),
    (569, "ayuntamiento", "noun", "M", "city hall", 2100, "B1", 0.6, "public services", "SPANISH_BREADTH_PLAN.md B1 public services topic", [(1197, 1200, "Voy al ayuntamiento.", "I go to city hall."), (1198, 1201, "El ayuntamiento abre temprano.", "City hall opens early.")]),
    (570, "policía", "noun", "F", "police", 700, "B1", 0.5, "public services and safety", "hermitdave/FrequencyWords high-frequency spine", [(1199, 1202, "Llamo a la policía.", "I call the police."), (1200, 1203, "La policía llega rápido.", "The police arrive quickly.")]),
    (571, "bombero", "noun", "M", "firefighter", 2500, "B1", 0.6, "public services and emergencies", "SPANISH_BREADTH_PLAN.md B1 public services topic", [(1201, 1204, "El bombero ayuda.", "The firefighter helps."), (1202, 1205, "Llaman a los bomberos.", "They call the firefighters.")]),
    (572, "juzgado", "noun", "M", "court", 2200, "B1", 0.6, "public services", "SPANISH_BREADTH_PLAN.md B1 public services topic", [(1203, 1206, "Voy al juzgado.", "I go to court."), (1204, 1207, "El juzgado está cerrado.", "The court is closed.")]),
    (573, "certificado", "noun", "M", "certificate", 1600, "B1", 0.5, "public services", "SPANISH_BREADTH_PLAN.md B1 public services topic", [(1205, 1208, "Necesito un certificado.", "I need a certificate."), (1206, 1209, "El certificado caduca pronto.", "The certificate expires soon.")]),
    (574, "impuesto", "noun", "M", "tax", 900, "B1", 0.5, "public services and money", "hermitdave/FrequencyWords high-frequency spine", [(1207, 1210, "Pago el impuesto.", "I pay the tax."), (1208, 1211, "El impuesto sube este año.", "The tax rises this year.")]),
    (575, "deuda", "noun", "F", "debt", 900, "B1", 0.5, "banking", "hermitdave/FrequencyWords high-frequency spine", [(1209, 1212, "Tengo una deuda.", "I have a debt."), (1210, 1213, "Pago la deuda poco a poco.", "I pay the debt little by little.")]),
    (576, "inversión", "noun", "F", "investment", 1200, "B1", 0.5, "banking and planning", "SPANISH_BREADTH_PLAN.md B1 banking/planning topic", [(1211, 1214, "La inversión es segura.", "The investment is safe."), (1212, 1215, "Analizo la inversión.", "I analyze the investment.")]),
    (577, "transferencia", "noun", "F", "transfer", 1300, "B1", 0.5, "banking", "SPANISH_BREADTH_PLAN.md B1 banking topic", [(1213, 1216, "Hago una transferencia.", "I make a transfer."), (1214, 1217, "La transferencia llega mañana.", "The transfer arrives tomorrow.")]),
    (578, "interés", "noun", "M", "interest", 550, "B1", 0.5, "banking and opinions", "hermitdave/FrequencyWords high-frequency spine", [(1215, 1218, "El interés es alto.", "The interest is high."), (1216, 1219, "Tengo interés en el puesto.", "I am interested in the position.")]),
    (579, "moneda", "noun", "F", "coin; currency", 1200, "B1", 0.5, "money and travel", "SPANISH_BREADTH_PLAN.md B1 money/travel topic", [(1217, 1220, "Cambio moneda en el banco.", "I exchange currency at the bank."), (1218, 1221, "Necesito monedas pequeñas.", "I need small coins.")]),
    (580, "enfermera", "noun", "F", "nurse", 1700, "B1", 0.5, "medical", "SPANISH_BREADTH_PLAN.md B1 medical topic", [(1219, 1222, "La enfermera me ayuda.", "The nurse helps me."), (1220, 1223, "Hablo con la enfermera.", "I speak with the nurse.")]),
    (581, "ambulancia", "noun", "F", "ambulance", 1900, "B1", 0.5, "medical and emergency", "SPANISH_BREADTH_PLAN.md B1 medical topic", [(1221, 1224, "Llamo a una ambulancia.", "I call an ambulance."), (1222, 1225, "La ambulancia llega rápido.", "The ambulance arrives quickly.")]),
    (582, "consulta", "noun", "F", "consultation; appointment", 1200, "B1", 0.5, "medical and services", "SPANISH_BREADTH_PLAN.md B1 medical/services topic", [(1223, 1226, "Tengo una consulta médica.", "I have a medical consultation."), (1224, 1227, "La consulta dura poco.", "The consultation lasts a short time.")]),
    (583, "vacuna", "noun", "F", "vaccine", 2000, "B1", 0.5, "medical", "SPANISH_BREADTH_PLAN.md B1 medical topic", [(1225, 1228, "Necesito una vacuna.", "I need a vaccine."), (1226, 1229, "La vacuna es recomendable.", "The vaccine is recommended.")]),
    (584, "pastilla", "noun", "F", "pill", 1900, "B1", 0.5, "medical", "SPANISH_BREADTH_PLAN.md B1 medical topic", [(1227, 1230, "Tomo una pastilla.", "I take a pill."), (1228, 1231, "La pastilla ayuda.", "The pill helps.")]),
    (585, "sangre", "noun", "F", "blood", 900, "B1", 0.5, "medical", "hermitdave/FrequencyWords high-frequency spine", [(1229, 1232, "Veo sangre en la mano.", "I see blood on the hand."), (1230, 1233, "El análisis de sangre está listo.", "The blood test is ready.")]),
    (586, "pecho", "noun", "M", "chest", 1200, "B1", 0.5, "medical and body", "SPANISH_BREADTH_PLAN.md B1 medical/body topic", [(1231, 1234, "Me duele el pecho.", "My chest hurts."), (1232, 1235, "El médico examina el pecho.", "The doctor examines the chest.")]),
    (587, "rodilla", "noun", "F", "knee", 1700, "B1", 0.5, "medical and body", "SPANISH_BREADTH_PLAN.md B1 medical/body topic", [(1233, 1236, "Me duele la rodilla.", "My knee hurts."), (1234, 1237, "La rodilla mejora.", "The knee improves.")]),
    (588, "dedo", "noun", "M", "finger; toe", 1200, "B1", 0.5, "medical and body", "SPANISH_BREADTH_PLAN.md B1 medical/body topic", [(1235, 1238, "Me corto el dedo.", "I cut my finger."), (1236, 1239, "El dedo sangra.", "The finger bleeds.")]),
    (589, "vivienda", "noun", "F", "housing; dwelling", 1000, "B1", 0.5, "housing and public services", "SPANISH_BREADTH_PLAN.md B1 housing topic", [(1237, 1240, "Busco vivienda.", "I look for housing."), (1238, 1241, "La vivienda es cara.", "Housing is expensive.")]),
    (590, "techo", "noun", "M", "roof; ceiling", 1100, "B1", 0.5, "housing and repairs", "SPANISH_BREADTH_PLAN.md B1 housing/repairs topic", [(1239, 1242, "El techo gotea.", "The roof leaks."), (1240, 1243, "Reparo el techo.", "I repair the roof.")]),
    (591, "pared", "noun", "F", "wall", 900, "B1", 0.5, "housing and repairs", "hermitdave/FrequencyWords high-frequency spine", [(1241, 1244, "La pared necesita pintura.", "The wall needs paint."), (1242, 1245, "La pared está sucia.", "The wall is dirty.")]),
    (592, "suelo", "noun", "M", "floor; ground", 750, "B1", 0.5, "housing", "hermitdave/FrequencyWords high-frequency spine", [(1243, 1246, "Limpio el suelo.", "I clean the floor."), (1244, 1247, "El suelo parece nuevo.", "The floor looks new.")]),
    (593, "grifo", "noun", "M", "faucet; tap", 2400, "B1", 0.6, "housing and repairs", "SPANISH_BREADTH_PLAN.md B1 housing/repairs topic", [(1245, 1248, "Reparo el grifo.", "I repair the faucet."), (1246, 1249, "Cierro el grifo.", "I turn off the faucet.")]),
    (594, "tubería", "noun", "F", "pipe", 2300, "B1", 0.6, "housing and repairs", "SPANISH_BREADTH_PLAN.md B1 housing/repairs topic", [(1247, 1250, "La tubería está rota.", "The pipe is broken."), (1248, 1251, "Revisan la tubería.", "They check the pipe.")]),
    (595, "cocina", "noun", "F", "kitchen", 1000, "B1", 0.5, "housing", "SPANISH_BREADTH_PLAN.md B1 housing topic", [(1249, 1252, "La cocina está limpia.", "The kitchen is clean."), (1250, 1253, "Ordeno la cocina.", "I tidy the kitchen.")]),
    (596, "salón", "noun", "M", "living room; hall", 1300, "B1", 0.5, "housing", "SPANISH_BREADTH_PLAN.md B1 housing topic", [(1251, 1254, "El salón es grande.", "The living room is big."), (1252, 1255, "Limpio el salón.", "I clean the living room.")]),
    (597, "empleado", "noun", "M", "employee", 950, "B1", 0.5, "workplace", "hermitdave/FrequencyWords high-frequency spine", [(1253, 1256, "El empleado llega temprano.", "The employee arrives early."), (1254, 1257, "Ayudo al empleado nuevo.", "I help the new employee.")]),
    (598, "candidato", "noun", "M", "candidate", 950, "B1", 0.5, "workplace", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [(1255, 1258, "El candidato espera afuera.", "The candidate waits outside."), (1256, 1259, "El candidato parece preparado.", "The candidate seems prepared.")]),
    (599, "puesto", "noun", "M", "position; job", 750, "B1", 0.5, "workplace", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [(1257, 1260, "Solicito el puesto.", "I apply for the position."), (1258, 1261, "El puesto está disponible.", "The position is available.")]),
    (600, "ascenso", "noun", "M", "promotion", 2100, "B1", 0.6, "workplace", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [(1259, 1262, "Quiero un ascenso.", "I want a promotion."), (1260, 1263, "El ascenso depende del resultado.", "The promotion depends on the result.")]),
    (601, "despido", "noun", "M", "dismissal; firing", 2200, "B1", 0.6, "workplace conflict", "SPANISH_BREADTH_PLAN.md B1 workplace/conflict topic", [(1261, 1264, "El despido causa problemas.", "The dismissal causes problems."), (1262, 1265, "Hablan del despido.", "They talk about the dismissal.")]),
    (602, "turno extra", "noun phrase", "M", "extra shift", 2600, "B1", 0.6, "workplace", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [(1263, 1266, "Acepto un turno extra.", "I accept an extra shift."), (1264, 1267, "El turno extra paga más.", "The extra shift pays more.")]),
    (603, "retrasado", "adjective", None, "delayed; late", 1600, "B1", 0.5, "travel and appointments", "SPANISH_BREADTH_PLAN.md B1 travel/appointments topic", [(1265, 1268, "El vuelo está retrasado.", "The flight is delayed."), (1266, 1269, "La entrega está retrasada.", "The delivery is delayed.")]),
    (604, "mojado", "adjective", None, "wet", 1500, "B1", 0.5, "housing and weather", "SPANISH_BREADTH_PLAN.md B1 housing topic", [(1267, 1270, "La mesa está mojada.", "The table is wet."), (1268, 1271, "La ropa está mojada.", "The clothes are wet.")]),
    (605, "seco", "adjective", None, "dry", 1200, "B1", 0.5, "housing and health", "SPANISH_BREADTH_PLAN.md B1 housing/health topic", [(1269, 1272, "El aire está seco.", "The air is dry."), (1270, 1273, "La ropa está seca.", "The clothes are dry.")]),
    (606, "seguramente", "adverb", None, "surely; probably", 1300, "B1", 0.5, "opinions and uncertainty", "SPANISH_BREADTH_PLAN.md B1 opinions topic", [(1271, 1274, "Seguramente llega mañana.", "He probably arrives tomorrow."), (1272, 1275, "Seguramente es mejor esperar.", "It is probably better to wait.")]),
])


AI_ACCELERATED_PACK_A2_013 = build_ai_accelerated_pack([
    (607, "no obstante", "adverbial phrase", None, "nevertheless", 1500, "B2", 0.6, "discourse markers", "SPANISH_BREADTH_PLAN.md B2 discourse markers topic", [(1273, 1276, "No obstante, acepto la decisión.", "Nevertheless, I accept the decision."), (1274, 1277, "El trámite es lento; no obstante, avanza.", "The procedure is slow; nevertheless, it moves forward.")]),
    (608, "aun así", "adverbial phrase", None, "even so", 1400, "B1", 0.5, "discourse markers", "SPANISH_BREADTH_PLAN.md B1 discourse markers topic", [(1275, 1278, "Aun así, quiero reclamar.", "Even so, I want to complain."), (1276, 1279, "Hace frío; aun así, salgo.", "It is cold; even so, I go out.")]),
    (609, "en resumen", "adverbial phrase", None, "in summary", 1600, "B1", 0.5, "summaries and narration", "SPANISH_BREADTH_PLAN.md B1 discourse markers topic", [(1277, 1280, "En resumen, necesitamos otra opción.", "In summary, we need another option."), (1278, 1281, "En resumen, el servicio falló.", "In summary, the service failed.")]),
    (610, "en conclusión", "adverbial phrase", None, "in conclusion", 1700, "B2", 0.6, "summaries and argumentation", "SPANISH_BREADTH_PLAN.md B2 discourse markers topic", [(1279, 1282, "En conclusión, apoyo el acuerdo.", "In conclusion, I support the agreement."), (1280, 1283, "En conclusión, el riesgo es bajo.", "In conclusion, the risk is low.")]),
    (611, "por un lado", "adverbial phrase", None, "on one hand", 1500, "B1", 0.5, "structured opinions", "SPANISH_BREADTH_PLAN.md B1 discourse markers topic", [(1281, 1284, "Por un lado, el alquiler es caro.", "On one hand, the rent is expensive."), (1282, 1285, "Por un lado, entiendo tu queja.", "On one hand, I understand your complaint.")]),
    (612, "por otro lado", "adverbial phrase", None, "on the other hand", 1500, "B1", 0.5, "structured opinions", "SPANISH_BREADTH_PLAN.md B1 discourse markers topic", [(1283, 1286, "Por otro lado, el barrio es tranquilo.", "On the other hand, the neighborhood is quiet."), (1284, 1287, "Por otro lado, falta un requisito.", "On the other hand, a requirement is missing.")]),
    (613, "es decir", "adverbial phrase", None, "that is to say", 900, "B1", 0.5, "clarification chunks", "SPANISH_BREADTH_PLAN.md B1 discourse markers topic", [(1285, 1288, "Es decir, necesito más tiempo.", "That is to say, I need more time."), (1286, 1289, "Es decir, reclamo el cargo.", "That is to say, I dispute the charge.")]),
    (614, "en otras palabras", "adverbial phrase", None, "in other words", 1900, "B2", 0.6, "clarification chunks", "SPANISH_BREADTH_PLAN.md B2 discourse markers topic", [(1287, 1290, "En otras palabras, no acepto.", "In other words, I do not accept."), (1288, 1291, "En otras palabras, el contrato cambia.", "In other words, the contract changes.")]),
    (615, "al respecto", "adverbial phrase", None, "regarding that", 1500, "B2", 0.6, "formal discourse", "SPANISH_BREADTH_PLAN.md B2 discourse markers topic", [(1289, 1292, "No tengo información al respecto.", "I have no information regarding that."), (1290, 1293, "Quiero hablar al respecto.", "I want to talk about that.")]),
    (616, "mientras tanto", "adverbial phrase", None, "meanwhile", 1400, "B1", 0.5, "narration and sequencing", "SPANISH_BREADTH_PLAN.md B1 narration topic", [(1291, 1294, "Mientras tanto, espero en recepción.", "Meanwhile, I wait at reception."), (1292, 1295, "Mientras tanto, reviso el documento.", "Meanwhile, I check the document.")]),
    (617, "de todos modos", "adverbial phrase", None, "anyway", 1300, "B1", 0.5, "discourse markers", "SPANISH_BREADTH_PLAN.md B1 common chunks topic", [(1293, 1296, "De todos modos, voy a llamar.", "Anyway, I am going to call."), (1294, 1297, "De todos modos, gracias por la ayuda.", "Anyway, thank you for the help.")]),
    (618, "de inmediato", "adverbial phrase", None, "immediately", 1200, "B1", 0.5, "emergencies and services", "SPANISH_BREADTH_PLAN.md B1 common chunks topic", [(1295, 1298, "Necesito ayuda de inmediato.", "I need help immediately."), (1296, 1299, "Llaman a la ambulancia de inmediato.", "They call the ambulance immediately.")]),
    (619, "a largo plazo", "adverbial phrase", None, "in the long term", 1700, "B2", 0.6, "planning and money", "SPANISH_BREADTH_PLAN.md B2 planning topic", [(1297, 1300, "A largo plazo, ahorramos dinero.", "In the long term, we save money."), (1298, 1301, "El plan funciona a largo plazo.", "The plan works in the long term.")]),
    (620, "a corto plazo", "adverbial phrase", None, "in the short term", 1700, "B2", 0.6, "planning and money", "SPANISH_BREADTH_PLAN.md B2 planning topic", [(1299, 1302, "A corto plazo, necesito efectivo.", "In the short term, I need cash."), (1300, 1303, "A corto plazo, el cambio ayuda.", "In the short term, the change helps.")]),
    (621, "a continuación", "adverbial phrase", None, "next; below", 1500, "B1", 0.5, "instructions and bureaucracy", "SPANISH_BREADTH_PLAN.md B1 public services topic", [(1301, 1304, "A continuación, firme el formulario.", "Next, sign the form."), (1302, 1305, "A continuación, explico el trámite.", "Next, I explain the procedure.")]),
    (622, "sin falta", "adverbial phrase", None, "without fail", 1900, "B1", 0.6, "appointments and obligations", "SPANISH_BREADTH_PLAN.md B1 common chunks topic", [(1303, 1306, "Llama mañana sin falta.", "Call tomorrow without fail."), (1304, 1307, "Pago la cuota sin falta.", "I pay the fee without fail.")]),
    (623, "por adelantado", "adverbial phrase", None, "in advance", 1600, "B1", 0.5, "money and appointments", "SPANISH_BREADTH_PLAN.md B1 common chunks topic", [(1305, 1308, "Pago por adelantado.", "I pay in advance."), (1306, 1309, "Reservo la cita por adelantado.", "I book the appointment in advance.")]),
    (624, "en efectivo", "adverbial phrase", None, "in cash", 900, "B1", 0.5, "money and services", "SPANISH_BREADTH_PLAN.md B1 banking topic", [(1307, 1310, "Prefiero pagar en efectivo.", "I prefer to pay in cash."), (1308, 1311, "No aceptan pagos en efectivo.", "They do not accept cash payments.")]),
    (625, "con tarjeta", "adverbial phrase", None, "by card", 900, "B1", 0.5, "money and services", "SPANISH_BREADTH_PLAN.md B1 banking topic", [(1309, 1312, "Ellos pagan con tarjeta.", "They pay by card."), (1310, 1313, "Prefiero pagar con tarjeta.", "I prefer to pay by card.")]),
    (626, "en persona", "adverbial phrase", None, "in person", 1000, "B1", 0.5, "public services", "SPANISH_BREADTH_PLAN.md B1 public services topic", [(1311, 1314, "Presento la solicitud en persona.", "I submit the application in person."), (1312, 1315, "Tengo que ir en persona.", "I have to go in person.")]),
    (627, "mediar", "verb", None, "to mediate", 2200, "B2", 0.6, "work and social conflict", "SPANISH_BREADTH_PLAN.md B2 conflict topic", [(1313, 1316, "Medio en el conflicto.", "I mediate in the conflict."), (1314, 1317, "La jefa media entre equipos.", "The boss mediates between teams.")]),
    (628, "conciliar", "verb", None, "to reconcile; to balance", 2300, "B2", 0.6, "negotiation and work", "SPANISH_BREADTH_PLAN.md B2 conflict/work topic", [(1315, 1318, "Intento conciliar las opiniones.", "I try to reconcile the opinions."), (1316, 1319, "Conciliamos trabajo y familia.", "We balance work and family.")]),
    (629, "ceder", "verb", None, "to give in; to yield", 1400, "B1", 0.5, "negotiation and conflict", "SPANISH_BREADTH_PLAN.md B1 conflict topic", [(1317, 1320, "Cedo en la negociación.", "I give in during the negotiation."), (1318, 1321, "No quiero ceder ahora.", "I do not want to give in now.")]),
    (630, "reembolsar", "verb", None, "to reimburse", 2400, "B2", 0.6, "money and services", "SPANISH_BREADTH_PLAN.md B2 banking/services topic", [(1319, 1322, "Reembolso el pago.", "I reimburse the payment."), (1320, 1323, "La empresa reembolsa el billete.", "The company reimburses the ticket.")]),
    (631, "indemnizar", "verb", None, "to compensate financially", 2500, "B2", 0.6, "legal and money", "SPANISH_BREADTH_PLAN.md B2 legal/money topic", [(1321, 1324, "Indemnizan al cliente.", "They compensate the customer."), (1322, 1325, "La compañía debe indemnizarme.", "The company must compensate me.")]),
    (632, "asegurar", "verb", None, "to insure; to assure", 900, "B1", 0.5, "money housing and safety", "SPANISH_BREADTH_PLAN.md B1 services topic", [(1323, 1326, "Aseguro la vivienda.", "I insure the home."), (1324, 1327, "Me aseguran que todo está bien.", "They assure me that everything is fine.")]),
    (633, "cotizar", "verb", None, "to quote a price; to contribute", 2300, "B2", 0.6, "money and work", "SPANISH_BREADTH_PLAN.md B2 money/work topic", [(1325, 1328, "Cotizo el servicio.", "I quote the service."), (1326, 1329, "Cotizamos para la pensión.", "We contribute toward the pension.")]),
    (634, "presupuestar", "verb", None, "to budget; to estimate", 2600, "B2", 0.6, "money and services", "SPANISH_BREADTH_PLAN.md B2 money/services topic", [(1327, 1330, "Presupuesto la reparación.", "I estimate the repair."), (1328, 1331, "Necesito presupuestar el proyecto.", "I need to budget the project.")]),
    (635, "liquidar", "verb", None, "to settle; to pay off", 2200, "B2", 0.6, "banking and legal obligations", "SPANISH_BREADTH_PLAN.md B2 banking/legal topic", [(1329, 1332, "Liquido la deuda.", "I settle the debt."), (1330, 1333, "Quiero liquidar el préstamo.", "I want to pay off the loan.")]),
    (636, "endeudarse", "verb", None, "to go into debt", 2500, "B2", 0.6, "money and planning", "SPANISH_BREADTH_PLAN.md B2 money topic", [(1331, 1334, "No quiero endeudarme.", "I do not want to go into debt."), (1332, 1335, "Nos endeudamos por la vivienda.", "We go into debt because of the home.")]),
    (637, "hospitalizar", "verb", None, "to hospitalize", 2600, "B2", 0.6, "health systems", "SPANISH_BREADTH_PLAN.md B2 health systems topic", [(1333, 1336, "Hospitalizan al paciente.", "They hospitalize the patient."), (1334, 1337, "El médico quiere hospitalizarlo.", "The doctor wants to hospitalize him.")]),
    (638, "derivar", "verb", None, "to refer; to redirect", 2000, "B2", 0.6, "health and services", "SPANISH_BREADTH_PLAN.md B2 health/services topic", [(1335, 1338, "Me derivan a un especialista.", "They refer me to a specialist."), (1336, 1339, "Derivan la llamada a otro servicio.", "They redirect the call to another service.")]),
    (639, "monitorizar", "verb", None, "to monitor", 2600, "B2", 0.6, "health systems", "SPANISH_BREADTH_PLAN.md B2 health systems topic", [(1337, 1340, "Monitorizan mi presión.", "They monitor my blood pressure."), (1338, 1341, "El hospital monitoriza al paciente.", "The hospital monitors the patient.")]),
    (640, "rehabilitarse", "verb", None, "to rehabilitate; recover", 2600, "B2", 0.6, "health systems", "SPANISH_BREADTH_PLAN.md B2 health systems topic", [(1339, 1342, "Me rehabilito después de la lesión.", "I rehabilitate after the injury."), (1340, 1343, "Necesito rehabilitarme poco a poco.", "I need to rehabilitate little by little.")]),
    (641, "desviar", "verb", None, "to divert; reroute", 1900, "B2", 0.6, "travel disruptions", "SPANISH_BREADTH_PLAN.md B2 travel disruptions topic", [(1341, 1344, "Desvían el tráfico.", "They divert the traffic."), (1342, 1345, "La compañía desvía el vuelo.", "The company reroutes the flight.")]),
    (642, "reubicar", "verb", None, "to relocate", 2600, "B2", 0.6, "travel housing and work", "SPANISH_BREADTH_PLAN.md B2 travel/housing topic", [(1343, 1346, "Reubican a los pasajeros.", "They relocate the passengers."), (1344, 1347, "La empresa reubica al equipo.", "The company relocates the team.")]),
    (643, "compensar", "verb", None, "to compensate", 1600, "B1", 0.5, "services and conflict", "SPANISH_BREADTH_PLAN.md B1 services/conflict topic", [(1345, 1348, "Compenso el retraso.", "I compensate for the delay."), (1346, 1349, "La aerolínea compensa al pasajero.", "The airline compensates the passenger.")]),
    (644, "desalojar", "verb", None, "to evict; to evacuate", 2400, "B2", 0.6, "housing legal and emergencies", "SPANISH_BREADTH_PLAN.md B2 housing/legal topic", [(1347, 1350, "Desalojan el edificio.", "They evacuate the building."), (1348, 1351, "El juez ordena desalojar la vivienda.", "The judge orders the home to be vacated.")]),
    (645, "demandar", "verb", None, "to sue; to demand", 1300, "B2", 0.6, "legal and conflict", "SPANISH_BREADTH_PLAN.md B2 legal topic", [(1349, 1352, "Demando a la empresa.", "I sue the company."), (1350, 1353, "El cliente demanda una solución.", "The customer demands a solution.")]),
    (646, "apelar", "verb", None, "to appeal", 1900, "B2", 0.6, "legal and bureaucracy", "SPANISH_BREADTH_PLAN.md B2 legal topic", [(1351, 1354, "Apelo la decisión.", "I appeal the decision."), (1352, 1355, "Podemos apelar la multa.", "We can appeal the fine.")]),
    (647, "testificar", "verb", None, "to testify", 2500, "B2", 0.6, "legal", "SPANISH_BREADTH_PLAN.md B2 legal topic", [(1353, 1356, "Testifico en el juzgado.", "I testify in court."), (1354, 1357, "Ella testifica mañana.", "She testifies tomorrow.")]),
    (648, "certificar", "verb", None, "to certify", 1700, "B2", 0.6, "bureaucracy", "SPANISH_BREADTH_PLAN.md B2 bureaucracy topic", [(1355, 1358, "Certifico la copia.", "I certify the copy."), (1356, 1359, "El médico certifica la baja.", "The doctor certifies the sick leave.")]),
    (649, "homologar", "verb", None, "to validate officially", 2700, "B2", 0.6, "bureaucracy and work", "SPANISH_BREADTH_PLAN.md B2 bureaucracy topic", [(1357, 1360, "Homologo mi título.", "I validate my degree officially."), (1358, 1361, "Necesito homologar el documento.", "I need to validate the document officially.")]),
    (650, "empadronarse", "verb", None, "to register residency", 2700, "B2", 0.6, "public services and housing", "SPANISH_BREADTH_PLAN.md B2 public services topic", [(1359, 1362, "Me empadrono en el ayuntamiento.", "I register my residency at city hall."), (1360, 1363, "Necesito empadronarme aquí.", "I need to register residency here.")]),
    (651, "solicitud formal", "noun phrase", "F", "formal application", 2600, "B2", 0.6, "bureaucracy", "SPANISH_BREADTH_PLAN.md B2 bureaucracy topic", [(1361, 1364, "Presento una solicitud formal.", "I submit a formal application."), (1362, 1365, "La solicitud formal está completa.", "The formal application is complete.")]),
    (652, "expediente", "noun", "M", "case file; record", 1700, "B2", 0.6, "bureaucracy and legal", "SPANISH_BREADTH_PLAN.md B2 bureaucracy/legal topic", [(1363, 1366, "Reviso el expediente.", "I review the case file."), (1364, 1367, "El expediente sigue abierto.", "The case file remains open.")]),
    (653, "denuncia", "noun", "F", "report; complaint", 1100, "B1", 0.5, "legal and public services", "SPANISH_BREADTH_PLAN.md B1 public services topic", [(1365, 1368, "Pongo una denuncia.", "I file a report."), (1366, 1369, "La denuncia está pendiente.", "The report is pending.")]),
    (654, "cita previa", "noun phrase", "F", "scheduled appointment", 2200, "B1", 0.6, "public services", "SPANISH_BREADTH_PLAN.md B1 public services topic", [(1367, 1370, "Necesito cita previa.", "I need a scheduled appointment."), (1368, 1371, "La cita previa es obligatoria.", "The scheduled appointment is required.")]),
    (655, "seguro médico", "noun phrase", "M", "health insurance", 2100, "B1", 0.6, "health systems", "SPANISH_BREADTH_PLAN.md B1 health systems topic", [(1369, 1372, "Tengo seguro médico.", "I have health insurance."), (1370, 1373, "El seguro médico cubre la consulta.", "The health insurance covers the consultation.")]),
    (656, "urgencias", "noun", "F", "emergency room", 1700, "B1", 0.5, "health systems and emergencies", "SPANISH_BREADTH_PLAN.md B1 health systems topic", [(1371, 1374, "Voy a urgencias.", "I go to the emergency room."), (1372, 1375, "Urgencias está lleno.", "The emergency room is full.")]),
    (657, "especialista", "noun", "M", "specialist", 1100, "B1", 0.5, "health systems", "SPANISH_BREADTH_PLAN.md B1 health systems topic", [(1373, 1376, "Consulto al especialista.", "I consult the specialist."), (1374, 1377, "El especialista revisa el análisis.", "The specialist reviews the test.")]),
    (658, "alergia", "noun", "F", "allergy", 1700, "B1", 0.5, "medical", "SPANISH_BREADTH_PLAN.md B1 medical topic", [(1375, 1378, "Tengo una alergia.", "I have an allergy."), (1376, 1379, "La alergia empeora hoy.", "The allergy gets worse today.")]),
    (659, "lesión", "noun", "F", "injury", 1300, "B1", 0.5, "medical and body", "SPANISH_BREADTH_PLAN.md B1 medical/body topic", [(1377, 1380, "Tengo una lesión en la rodilla.", "I have a knee injury."), (1378, 1381, "La lesión mejora poco a poco.", "The injury improves little by little.")]),
    (660, "fractura", "noun", "F", "fracture", 1900, "B1", 0.5, "medical and body", "SPANISH_BREADTH_PLAN.md B1 medical/body topic", [(1379, 1382, "La fractura duele mucho.", "The fracture hurts a lot."), (1380, 1383, "El médico revisa la fractura.", "The doctor checks the fracture.")]),
    (661, "radiografía", "noun", "F", "x-ray", 2200, "B1", 0.6, "medical systems", "SPANISH_BREADTH_PLAN.md B1 medical systems topic", [(1381, 1384, "Necesito una radiografía.", "I need an x-ray."), (1382, 1385, "La radiografía está lista.", "The x-ray is ready.")]),
    (662, "hipoteca", "noun", "F", "mortgage", 1500, "B1", 0.5, "housing and banking", "SPANISH_BREADTH_PLAN.md B1 housing/banking topic", [(1383, 1386, "Pago la hipoteca.", "I pay the mortgage."), (1384, 1387, "La hipoteca es alta.", "The mortgage is high.")]),
    (663, "nómina", "noun", "F", "payroll; payslip", 1800, "B2", 0.6, "work and banking", "SPANISH_BREADTH_PLAN.md B2 work/banking topic", [(1385, 1388, "Recibo la nómina.", "I receive the payslip."), (1386, 1389, "El banco pide la nómina.", "The bank asks for the payslip.")]),
    (664, "ahorro", "noun", "M", "savings", 1200, "B1", 0.5, "money and planning", "SPANISH_BREADTH_PLAN.md B1 money topic", [(1387, 1390, "Tengo ahorros.", "I have savings."), (1388, 1391, "Uso mis ahorros.", "I use my savings.")]),
    (665, "tarifa", "noun", "F", "rate; fare", 1300, "B1", 0.5, "money and travel", "SPANISH_BREADTH_PLAN.md B1 money/travel topic", [(1389, 1392, "La tarifa sube mañana.", "The fare rises tomorrow."), (1390, 1393, "Comparo la tarifa.", "I compare the rate.")]),
    (666, "comisión", "noun", "F", "fee; commission", 950, "B1", 0.5, "banking and work", "SPANISH_BREADTH_PLAN.md B1 banking/work topic", [(1391, 1394, "El banco cobra una comisión.", "The bank charges a fee."), (1392, 1395, "La comisión es mensual.", "The fee is monthly.")]),
    (667, "recargo", "noun", "M", "surcharge", 2200, "B1", 0.6, "money and services", "SPANISH_BREADTH_PLAN.md B1 money/services topic", [(1393, 1396, "Hay un recargo.", "There is a surcharge."), (1394, 1397, "No acepto el recargo.", "I do not accept the surcharge.")]),
    (668, "inquilino", "noun", "M", "tenant", 1700, "B1", 0.5, "housing and legal", "SPANISH_BREADTH_PLAN.md B1 housing/legal topic", [(1395, 1398, "El inquilino paga el alquiler.", "The tenant pays the rent."), (1396, 1399, "Hablo con el inquilino.", "I speak with the tenant.")]),
    (669, "propietario", "noun", "M", "owner; landlord", 1000, "B1", 0.5, "housing and legal", "SPANISH_BREADTH_PLAN.md B1 housing/legal topic", [(1397, 1400, "Llamo al propietario.", "I call the landlord."), (1398, 1401, "El propietario repara el grifo.", "The landlord repairs the faucet.")]),
    (670, "fianza", "noun", "F", "security deposit", 1800, "B1", 0.5, "housing and money", "SPANISH_BREADTH_PLAN.md B1 housing/money topic", [(1399, 1402, "Pago la fianza.", "I pay the security deposit."), (1400, 1403, "Recupero la fianza.", "I recover the deposit.")]),
    (671, "comunidad", "noun", "F", "community; homeowners association", 800, "B1", 0.5, "housing and public life", "SPANISH_BREADTH_PLAN.md B1 housing topic", [(1401, 1404, "La comunidad paga la reparación.", "The community pays for the repair."), (1402, 1405, "Hablo con la comunidad.", "I speak with the homeowners association.")]),
    (672, "contratista", "noun", "M", "contractor", 2100, "B1", 0.6, "housing and repairs", "SPANISH_BREADTH_PLAN.md B1 housing/repairs topic", [(1403, 1406, "Llamo al contratista.", "I call the contractor."), (1404, 1407, "El contratista revisa el techo.", "The contractor checks the roof.")]),
    (673, "humedad", "noun", "F", "dampness; humidity", 1900, "B1", 0.5, "housing and health", "SPANISH_BREADTH_PLAN.md B1 housing/health topic", [(1405, 1408, "Hay humedad en la pared.", "There is dampness on the wall."), (1406, 1409, "La humedad causa problemas.", "The dampness causes problems.")]),
    (674, "grieta", "noun", "F", "crack", 2100, "B1", 0.6, "housing and repairs", "SPANISH_BREADTH_PLAN.md B1 housing/repairs topic", [(1407, 1410, "Hay una grieta en el techo.", "There is a crack in the ceiling."), (1408, 1411, "Reviso la grieta.", "I check the crack.")]),
    (675, "enchufe", "noun", "M", "electrical outlet", 2400, "B1", 0.6, "housing and repairs", "SPANISH_BREADTH_PLAN.md B1 housing/repairs topic", [(1409, 1412, "El enchufe no funciona.", "The outlet does not work."), (1410, 1413, "Reemplazo el enchufe.", "I replace the outlet.")]),
    (676, "cancelación", "noun", "F", "cancellation", 1500, "B1", 0.5, "travel disruptions and appointments", "SPANISH_BREADTH_PLAN.md B1 travel disruptions topic", [(1411, 1414, "La cancelación causa problemas.", "The cancellation causes problems."), (1412, 1415, "Confirmo la cancelación.", "I confirm the cancellation.")]),
    (677, "reembolso", "noun", "M", "refund", 1900, "B1", 0.5, "money and travel disruptions", "SPANISH_BREADTH_PLAN.md B1 travel/money topic", [(1413, 1416, "Pido un reembolso.", "I ask for a refund."), (1414, 1417, "El reembolso llega mañana.", "The refund arrives tomorrow.")]),
    (678, "itinerario", "noun", "M", "itinerary", 2100, "B1", 0.6, "travel", "SPANISH_BREADTH_PLAN.md B1 travel topic", [(1415, 1418, "Reviso el itinerario.", "I check the itinerary."), (1416, 1419, "El itinerario cambia.", "The itinerary changes.")]),
    (679, "andén", "noun", "M", "platform", 2200, "B1", 0.6, "travel and transit", "SPANISH_BREADTH_PLAN.md B1 travel/transit topic", [(1417, 1420, "Espero en el andén.", "I wait on the platform."), (1418, 1421, "El tren cambia de andén.", "The train changes platforms.")]),
    (680, "aduana", "noun", "F", "customs", 1700, "B1", 0.5, "travel and public services", "SPANISH_BREADTH_PLAN.md B1 travel/public services topic", [(1419, 1422, "Paso por la aduana.", "I go through customs."), (1420, 1423, "La aduana revisa el equipaje.", "Customs checks the luggage.")]),
    (681, "pasajero", "noun", "M", "passenger", 900, "B1", 0.5, "travel", "SPANISH_BREADTH_PLAN.md B1 travel topic", [(1421, 1424, "El pasajero espera.", "The passenger waits."), (1422, 1425, "Ayudo al pasajero.", "I help the passenger.")]),
    (682, "vuelo", "noun", "M", "flight", 800, "B1", 0.5, "travel disruptions", "SPANISH_BREADTH_PLAN.md B1 travel topic", [(1423, 1426, "El vuelo sale tarde.", "The flight leaves late."), (1424, 1427, "Cambio el vuelo.", "I change the flight.")]),
    (683, "malentendido", "noun", "M", "misunderstanding", 2200, "B1", 0.6, "social conflict", "SPANISH_BREADTH_PLAN.md B1 social conflict topic", [(1425, 1428, "Hay un malentendido.", "There is a misunderstanding."), (1426, 1429, "Aclaro el malentendido.", "I clear up the misunderstanding.")]),
    (684, "disculpa", "noun", "F", "apology", 1600, "B1", 0.5, "social conflict", "SPANISH_BREADTH_PLAN.md B1 social conflict topic", [(1427, 1430, "Acepto la disculpa.", "I accept the apology."), (1428, 1431, "Ofrezco una disculpa.", "I offer an apology.")]),
    (685, "tensión", "noun", "F", "tension", 1200, "B1", 0.5, "social and work conflict", "SPANISH_BREADTH_PLAN.md B1 conflict topic", [(1429, 1432, "Hay tensión en el equipo.", "There is tension in the team."), (1430, 1433, "La tensión aumenta.", "The tension increases.")]),
    (686, "mediación", "noun", "F", "mediation", 2200, "B2", 0.6, "social and legal conflict", "SPANISH_BREADTH_PLAN.md B2 conflict/legal topic", [(1431, 1434, "La mediación ayuda.", "Mediation helps."), (1432, 1435, "Solicito una mediación.", "I request mediation.")]),
    (687, "acoso", "noun", "M", "harassment", 1900, "B2", 0.6, "work and legal conflict", "SPANISH_BREADTH_PLAN.md B2 conflict/legal topic", [(1433, 1436, "Denuncio el acoso.", "I report the harassment."), (1434, 1437, "El acoso es grave.", "Harassment is serious.")]),
    (688, "testigo", "noun", "M", "witness", 1300, "B1", 0.5, "legal and public services", "SPANISH_BREADTH_PLAN.md B1 legal topic", [(1435, 1438, "El testigo habla mañana.", "The witness speaks tomorrow."), (1436, 1439, "Necesito un testigo.", "I need a witness.")]),
    (689, "abogado", "noun", "M", "lawyer", 900, "B1", 0.5, "legal and services", "hermitdave/FrequencyWords high-frequency spine", [(1437, 1440, "Llamo al abogado.", "I call the lawyer."), (1438, 1441, "El abogado revisa el contrato.", "The lawyer reviews the contract.")]),
    (690, "juez", "noun", "M", "judge", 900, "B1", 0.5, "legal", "hermitdave/FrequencyWords high-frequency spine", [(1439, 1442, "El juez toma una decisión.", "The judge makes a decision."), (1440, 1443, "Hablo con el juez.", "I speak with the judge.")]),
    (691, "prueba legal", "noun phrase", "F", "legal evidence", 2400, "B2", 0.6, "legal", "SPANISH_BREADTH_PLAN.md B2 legal topic", [(1441, 1444, "Presento una prueba legal.", "I present legal evidence."), (1442, 1445, "La prueba legal es clara.", "The legal evidence is clear.")]),
    (692, "prioritario", "adjective", None, "high-priority", 1800, "B2", 0.6, "emergencies and services", "SPANISH_BREADTH_PLAN.md B2 emergency/services topic", [(1443, 1446, "Es un caso prioritario.", "It is a high-priority case."), (1444, 1447, "Necesito atención prioritaria.", "I need priority attention.")]),
    (693, "leve", "adjective", None, "minor; mild", 1300, "B1", 0.5, "medical and legal", "SPANISH_BREADTH_PLAN.md B1 medical/legal topic", [(1445, 1448, "La lesión es leve.", "The injury is minor."), (1446, 1449, "El daño parece leve.", "The damage seems minor.")]),
    (694, "obligado", "adjective", None, "obliged; required", 1200, "B1", 0.5, "obligations and bureaucracy", "SPANISH_BREADTH_PLAN.md B1 bureaucracy topic", [(1447, 1450, "Estoy obligado a pagar.", "I am obliged to pay."), (1448, 1451, "El trámite es obligado.", "The procedure is required.")]),
    (695, "autorizado", "adjective", None, "authorized", 1400, "B1", 0.5, "bureaucracy and services", "SPANISH_BREADTH_PLAN.md B1 bureaucracy topic", [(1449, 1452, "Estoy autorizado a entrar.", "I am authorized to enter."), (1450, 1453, "El pago está autorizado.", "The payment is authorized.")]),
    (696, "pendiente de pago", "adjective phrase", None, "pending payment", 2300, "B2", 0.6, "money and bureaucracy", "SPANISH_BREADTH_PLAN.md B2 banking/bureaucracy topic", [(1451, 1454, "La factura está pendiente de pago.", "The bill is pending payment."), (1452, 1455, "Tengo una cuota pendiente de pago.", "I have a fee pending payment.")]),
    (697, "apto", "adjective", None, "fit; eligible", 1600, "B2", 0.6, "health work and bureaucracy", "SPANISH_BREADTH_PLAN.md B2 health/work topic", [(1453, 1456, "Estoy apto para trabajar.", "I am fit to work."), (1454, 1457, "El candidato es apto.", "The candidate is eligible.")]),
    (698, "válido", "adjective", None, "valid", 900, "B1", 0.5, "bureaucracy and travel", "SPANISH_BREADTH_PLAN.md B1 bureaucracy/travel topic", [(1455, 1458, "El pasaporte es válido.", "The passport is valid."), (1456, 1459, "El permiso sigue válido.", "The permit remains valid.")]),
    (699, "vencido", "adjective", None, "expired", 1800, "B1", 0.5, "bureaucracy and banking", "SPANISH_BREADTH_PLAN.md B1 bureaucracy/banking topic", [(1457, 1460, "El certificado está vencido.", "The certificate is expired."), (1458, 1461, "La tarjeta está vencida.", "The card is expired.")]),
    (700, "imprescindible", "adjective", None, "essential", 1900, "B2", 0.6, "formal opinions and bureaucracy", "SPANISH_BREADTH_PLAN.md B2 opinions/bureaucracy topic", [(1459, 1462, "Es imprescindible traer el documento.", "It is essential to bring the document."), (1460, 1463, "La firma es imprescindible.", "The signature is essential.")]),
    (701, "razonable", "adjective", None, "reasonable", 1300, "B1", 0.5, "negotiation and opinions", "SPANISH_BREADTH_PLAN.md B1 negotiation topic", [(1461, 1464, "La oferta es razonable.", "The offer is reasonable."), (1462, 1465, "Busco una solución razonable.", "I look for a reasonable solution.")]),
    (702, "abusivo", "adjective", None, "abusive; unfair", 2200, "B2", 0.6, "legal money and conflict", "SPANISH_BREADTH_PLAN.md B2 legal/money topic", [(1463, 1466, "El recargo es abusivo.", "The surcharge is unfair."), (1464, 1467, "La cláusula parece abusiva.", "The clause seems unfair.")]),
    (703, "confidencial", "adjective", None, "confidential", 1500, "B2", 0.6, "work and bureaucracy", "SPANISH_BREADTH_PLAN.md B2 work/bureaucracy topic", [(1465, 1468, "El informe es confidencial.", "The report is confidential."), (1466, 1469, "La información es confidencial.", "The information is confidential.")]),
    (704, "presencial", "adjective", None, "in-person", 2200, "B1", 0.6, "public services and work", "SPANISH_BREADTH_PLAN.md B1 public services/work topic", [(1467, 1470, "La cita es presencial.", "The appointment is in-person."), (1468, 1471, "El curso presencial empieza mañana.", "The in-person course starts tomorrow.")]),
    (705, "remoto", "adjective", None, "remote", 1600, "B1", 0.5, "work and services", "SPANISH_BREADTH_PLAN.md B1 work/services topic", [(1469, 1472, "Trabajo en remoto.", "I work remotely."), (1470, 1473, "La reunión remota funciona bien.", "The remote meeting works well.")]),
    (706, "aproximado", "adjective", None, "approximate", 1700, "B1", 0.5, "money and planning", "SPANISH_BREADTH_PLAN.md B1 planning/money topic", [(1471, 1474, "El precio es aproximado.", "The price is approximate."), (1472, 1475, "Doy una fecha aproximada.", "I give an approximate date.")]),
])


AI_ACCELERATED_PACK_A2_014 = build_numbered_ai_accelerated_pack(707, 1473, 1476, [
    ("en cambio", "adverbial phrase", None, "on the other hand", 1200, "B1", 0.5, "argument and contrast", "SPANISH_BREADTH_PLAN.md B1 discourse markers topic", [("Yo pago hoy; en cambio, tú pagas mañana.", "I pay today; you pay tomorrow."), ("En cambio, prefiero esperar.", "Instead, I prefer to wait.")]),
    ("salvo", "preposition", None, "except; save", 1300, "B1", 0.5, "exceptions and conditions", "SPANISH_BREADTH_PLAN.md B1 connectors topic", [("Todos vienen, salvo Ana.", "Everyone comes except Ana."), ("Salvo error, el pago está hecho.", "Unless there is an error, payment is done.")]),
    ("debido a", "prepositional phrase", None, "due to", 1500, "B1", 0.5, "reasons and problems", "SPANISH_BREADTH_PLAN.md B1 reasons topic", [("El vuelo cambia debido al clima.", "The flight changes due to weather."), ("Debido al ruido, no duermo.", "Due to noise, I cannot sleep.")]),
    ("gracias a", "prepositional phrase", None, "thanks to", 1200, "B1", 0.5, "reasons and outcomes", "SPANISH_BREADTH_PLAN.md B1 reasons topic", [("Gracias a ti, resolvemos el problema.", "Thanks to you, we solve the problem."), ("Llego a tiempo gracias al taxi.", "I arrive on time thanks to the taxi.")]),
    ("al contrario", "adverbial phrase", None, "on the contrary", 1500, "B1", 0.5, "argument and repair", "SPANISH_BREADTH_PLAN.md B1 argument topic", [("Al contrario, estoy de acuerdo.", "On the contrary, I agree."), ("Al contrario, conviene esperar.", "On the contrary, waiting helps.")]),
    ("en cualquier caso", "adverbial phrase", None, "in any case", 1900, "B2", 0.6, "discourse markers", "SPANISH_BREADTH_PLAN.md B2 discourse markers topic", [("En cualquier caso, llamo mañana.", "In any case, I call tomorrow."), ("En cualquier caso, necesito respuesta.", "In any case, I need an answer.")]),
    ("en ese caso", "adverbial phrase", None, "in that case", 1700, "B1", 0.5, "conditions and repair", "SPANISH_BREADTH_PLAN.md B1 conversation repair topic", [("En ese caso, espero aquí.", "In that case, I wait here."), ("En ese caso, cambio la cita.", "In that case, I change the appointment.")]),
    ("por si acaso", "adverbial phrase", None, "just in case", 1600, "B1", 0.5, "planning and precaution", "SPANISH_BREADTH_PLAN.md B1 everyday chunks topic", [("Llevo efectivo por si acaso.", "I carry cash just in case."), ("Guardo la copia por si acaso.", "I keep the copy just in case.")]),
    ("a propósito", "adverbial phrase", None, "by the way; deliberately", 1400, "B1", 0.5, "conversation and intent", "SPANISH_BREADTH_PLAN.md B1 conversation chunks topic", [("A propósito, necesito tu firma.", "By the way, I need your signature."), ("No lo hice a propósito.", "I did not do it deliberately.")]),
    ("desde luego", "adverbial phrase", None, "of course", 1300, "B1", 0.5, "agreement and emphasis", "SPANISH_BREADTH_PLAN.md B1 opinion chunks topic", [("Desde luego, acepto la propuesta.", "Of course, I accept the proposal."), ("Desde luego, esto es importante.", "Of course, this is important.")]),
    ("al fin y al cabo", "adverbial phrase", None, "after all", 2000, "B2", 0.6, "argument and summaries", "SPANISH_BREADTH_PLAN.md B2 argument chunks topic", [("Al fin y al cabo, somos vecinos.", "After all, we are neighbors."), ("Al fin y al cabo, conviene esperar.", "After all, waiting is useful.")]),
    ("por ahora", "adverbial phrase", None, "for now", 1200, "B1", 0.5, "planning and status", "SPANISH_BREADTH_PLAN.md B1 planning chunks topic", [("Por ahora, no necesito ayuda.", "For now, I need no help."), ("El plan funciona por ahora.", "The plan works for now.")]),
    ("por lo menos", "adverbial phrase", None, "at least", 1100, "B1", 0.5, "argument and estimates", "SPANISH_BREADTH_PLAN.md B1 opinion chunks topic", [("Por lo menos, avísame antes.", "At least, tell me beforehand."), ("Necesito por lo menos dos copias.", "I need at least two copies.")]),
    ("por lo visto", "adverbial phrase", None, "apparently", 1700, "B1", 0.5, "uncertainty and narration", "SPANISH_BREADTH_PLAN.md B1 narration chunks topic", [("Por lo visto, la oficina cierra.", "Apparently, the office closes."), ("Por lo visto, falta un documento.", "Apparently, a document is missing.")]),
    ("en principio", "adverbial phrase", None, "in principle", 1600, "B2", 0.6, "formal planning", "SPANISH_BREADTH_PLAN.md B2 discourse markers topic", [("En principio, acepto el acuerdo.", "In principle, I accept the agreement."), ("En principio, la cita sigue.", "In principle, the appointment remains.")]),
    ("en realidad", "adverbial phrase", None, "actually", 900, "B1", 0.5, "clarification", "SPANISH_BREADTH_PLAN.md B1 conversation repair topic", [("En realidad, necesito otra factura.", "Actually, I need another invoice."), ("En realidad, no estoy seguro.", "Actually, I am not sure.")]),
    ("de nuevo", "adverbial phrase", None, "again", 850, "B1", 0.5, "repair and repetition", "SPANISH_BREADTH_PLAN.md B1 conversation repair topic", [("Explícalo de nuevo, por favor.", "Explain it again, please."), ("Llamo de nuevo mañana.", "I call again tomorrow.")]),
    ("otra vez", "adverbial phrase", None, "again", 900, "B1", 0.5, "repair and repetition", "SPANISH_BREADTH_PLAN.md B1 conversation repair topic", [("Repite otra vez, por favor.", "Repeat it again, please."), ("La tarjeta falla otra vez.", "The card fails again.")]),
    ("a la vez", "adverbial phrase", None, "at the same time", 1300, "B1", 0.5, "coordination and work", "SPANISH_BREADTH_PLAN.md B1 workplace chunks topic", [("Trabajamos a la vez.", "We work at the same time."), ("No hablen todos a la vez.", "Do not all speak at once.")]),
    ("al menos", "adverbial phrase", None, "at least", 1000, "B1", 0.5, "estimates and repair", "SPANISH_BREADTH_PLAN.md B1 opinion chunks topic", [("Al menos, dame una copia.", "At least, give me a copy."), ("Necesito al menos una respuesta.", "I need at least one answer.")]),
    ("en vez de", "prepositional phrase", None, "instead of", 1500, "B1", 0.5, "choices and repair", "SPANISH_BREADTH_PLAN.md B1 comparison chunks topic", [("Pago en efectivo en vez de tarjeta.", "I pay cash instead of card."), ("Ven hoy en vez de mañana.", "Come today instead of tomorrow.")]),
    ("a mano", "adverbial phrase", None, "by hand", 1400, "B1", 0.5, "forms and household", "SPANISH_BREADTH_PLAN.md B1 public services topic", [("Relleno el formulario a mano.", "I fill the form by hand."), ("Escribo la dirección a mano.", "I write the address by hand.")]),
    ("a domicilio", "adverbial phrase", None, "home delivery", 1900, "B1", 0.6, "services and household", "SPANISH_BREADTH_PLAN.md B1 services topic", [("El servicio es a domicilio.", "The service is home delivery."), ("Pido comida a domicilio.", "I order food for delivery.")]),
    ("de guardia", "adverbial phrase", None, "on call", 1900, "B2", 0.6, "medical and emergencies", "SPANISH_BREADTH_PLAN.md B2 health systems topic", [("El médico está de guardia.", "The doctor is on call."), ("Hay una farmacia de guardia.", "There is an on-call pharmacy.")]),
    ("fuera de servicio", "adjective phrase", None, "out of service", 2100, "B1", 0.6, "travel and services", "SPANISH_BREADTH_PLAN.md B1 travel disruptions topic", [("El ascensor está fuera de servicio.", "The elevator is out of service."), ("La máquina sigue fuera de servicio.", "The machine remains out of service.")]),
    ("en servicio", "adjective phrase", None, "in service", 1700, "B1", 0.5, "travel and services", "SPANISH_BREADTH_PLAN.md B1 travel/services topic", [("El tren está en servicio.", "The train is in service."), ("La línea vuelve a estar en servicio.", "The line is back in service.")]),
    ("de acuerdo con", "prepositional phrase", None, "according to", 1600, "B2", 0.6, "rules and formal speech", "SPANISH_BREADTH_PLAN.md B2 bureaucracy topic", [("Actúo de acuerdo con la norma.", "I act according to the rule."), ("De acuerdo con el contrato, pago.", "According to the contract, I pay.")]),
    ("con respecto a", "prepositional phrase", None, "regarding", 1800, "B2", 0.6, "formal discourse", "SPANISH_BREADTH_PLAN.md B2 discourse markers topic", [("Con respecto al pago, acepto.", "Regarding the payment, I accept."), ("Tengo dudas con respecto al contrato.", "I have doubts regarding the contract.")]),
    ("por separado", "adverbial phrase", None, "separately", 1600, "B1", 0.5, "forms and money", "SPANISH_BREADTH_PLAN.md B1 money/services topic", [("Pago las tasas por separado.", "I pay the fees separately."), ("Envío los documentos por separado.", "I send the documents separately.")]),
    ("por escrito", "adverbial phrase", None, "in writing", 1500, "B1", 0.5, "bureaucracy and legal", "SPANISH_BREADTH_PLAN.md B1 bureaucracy/legal topic", [("Lo pido por escrito.", "I request it in writing."), ("Necesito la respuesta por escrito.", "I need the answer in writing.")]),
    ("verbalmente", "adverb", None, "verbally", 2200, "B2", 0.6, "work and legal", "SPANISH_BREADTH_PLAN.md B2 workplace/legal topic", [("Acepto verbalmente.", "I accept verbally."), ("Me informa verbalmente.", "He informs me verbally.")]),
    ("sinceramente", "adverb", None, "honestly", 1500, "B1", 0.5, "opinions and repair", "SPANISH_BREADTH_PLAN.md B1 opinion language topic", [("Sinceramente, no entiendo.", "Honestly, I do not understand."), ("Sinceramente, prefiero otra opción.", "Honestly, I prefer another option.")]),
    ("justamente", "adverb", None, "precisely; fairly", 1500, "B1", 0.5, "argument and emphasis", "SPANISH_BREADTH_PLAN.md B1 argument language topic", [("Eso es justamente el problema.", "That is precisely the problem."), ("Me tratan justamente.", "They treat me fairly.")]),
    ("precisamente", "adverb", None, "precisely", 1200, "B1", 0.5, "argument and emphasis", "SPANISH_BREADTH_PLAN.md B1 argument language topic", [("Precisamente por eso llamo.", "That is precisely why I call."), ("Necesito precisamente ese documento.", "I need precisely that document.")]),
    ("probablemente", "adverb", None, "probably", 1100, "B1", 0.5, "uncertainty and planning", "SPANISH_BREADTH_PLAN.md B1 uncertainty topic", [("Probablemente llega tarde.", "He probably arrives late."), ("Probablemente necesito otra cita.", "I probably need another appointment.")]),
    ("raramente", "adverb", None, "rarely", 1900, "B1", 0.5, "frequency and narration", "SPANISH_BREADTH_PLAN.md B1 frequency topic", [("Raramente uso efectivo.", "I rarely use cash."), ("Raramente tengo problemas aquí.", "I rarely have problems here.")]),
    ("posteriormente", "adverb", None, "later; subsequently", 1800, "B2", 0.6, "formal sequencing", "SPANISH_BREADTH_PLAN.md B2 narration topic", [("Posteriormente, firmo el contrato.", "Later, I sign the contract."), ("Posteriormente, revisan el expediente.", "Later, they review the file.")]),
    ("diariamente", "adverb", None, "daily", 1700, "B1", 0.5, "routines and health", "SPANISH_BREADTH_PLAN.md B1 routine/health topic", [("Tomo la medicina diariamente.", "I take the medicine daily."), ("Reviso el correo diariamente.", "I check email daily.")]),
    ("semanalmente", "adverb", None, "weekly", 1900, "B1", 0.5, "routines and money", "SPANISH_BREADTH_PLAN.md B1 routine/money topic", [("Pago semanalmente.", "I pay weekly."), ("Nos reunimos semanalmente.", "We meet weekly.")]),
    ("mensualmente", "adverb", None, "monthly", 1900, "B1", 0.5, "routines and money", "SPANISH_BREADTH_PLAN.md B1 routine/money topic", [("Pago el alquiler mensualmente.", "I pay rent monthly."), ("Recibo la factura mensualmente.", "I receive the bill monthly.")]),
    ("sustituir", "verb", None, "to replace", 1300, "B1", 0.5, "services and repairs", "SPANISH_BREADTH_PLAN.md B1 household/services topic", [("Sustituyo la bombilla.", "I replace the bulb."), ("Necesito sustituir la tarjeta.", "I need to replace the card.")]),
    ("actualizar", "verb", None, "to update", 1700, "B1", 0.5, "services and bureaucracy", "SPANISH_BREADTH_PLAN.md B1 services/technology topic", [("Actualizo mis datos.", "I update my details."), ("Necesito actualizar la aplicación.", "I need to update the app.")]),
    ("adelantar", "verb", None, "to move earlier; advance", 1600, "B1", 0.5, "appointments and planning", "SPANISH_BREADTH_PLAN.md B1 appointments topic", [("Adelanto la cita.", "I move the appointment earlier."), ("Quiero adelantar el pago.", "I want to advance the payment.")]),
    ("interrogar", "verb", None, "to question; interrogate", 2300, "B2", 0.6, "legal and conflict", "SPANISH_BREADTH_PLAN.md B2 legal topic", [("Interrogan al testigo.", "They question the witness."), ("El abogado quiere interrogarlo.", "The lawyer wants to question him.")]),
    ("investigar", "verb", None, "to investigate", 1000, "B1", 0.5, "legal and problems", "SPANISH_BREADTH_PLAN.md B1 legal/problems topic", [("Investigo el problema.", "I investigate the problem."), ("La policía investiga la denuncia.", "The police investigate the report.")]),
    ("encargarse", "verb", None, "to take care of", 1500, "B1", 0.5, "work and services", "SPANISH_BREADTH_PLAN.md B1 work/services topic", [("Me encargo del trámite.", "I handle the procedure."), ("Ella se encarga del pago.", "She handles the payment.")]),
    ("sellar", "verb", None, "to stamp; seal", 2200, "B1", 0.6, "bureaucracy and household", "SPANISH_BREADTH_PLAN.md B1 bureaucracy topic", [("Sello el formulario.", "I stamp the form."), ("Sellan la copia en recepción.", "They stamp the copy at reception.")]),
    ("escanear", "verb", None, "to scan", 2400, "B1", 0.6, "bureaucracy and technology", "SPANISH_BREADTH_PLAN.md B1 public services topic", [("Escaneo el documento.", "I scan the document."), ("Necesito escanear la copia.", "I need to scan the copy.")]),
    ("adjuntar", "verb", None, "to attach", 2300, "B1", 0.6, "bureaucracy and technology", "SPANISH_BREADTH_PLAN.md B1 public services topic", [("Adjunto la factura.", "I attach the invoice."), ("Debes adjuntar el certificado.", "You must attach the certificate.")]),
    ("audiencia", "noun", "F", "hearing; audience", 1600, "B2", 0.6, "legal and public life", "SPANISH_BREADTH_PLAN.md B2 legal topic", [("La audiencia empieza mañana.", "The hearing starts tomorrow."), ("Asisto a la audiencia.", "I attend the hearing.")]),
    ("juzgar", "verb", None, "to judge", 1400, "B1", 0.5, "legal and opinions", "SPANISH_BREADTH_PLAN.md B1 legal/opinions topic", [("No quiero juzgarte.", "I do not want to judge you."), ("El juez juzga el caso.", "The judge tries the case.")]),
    ("declarar", "verb", None, "to declare; testify", 1000, "B1", 0.5, "legal and bureaucracy", "SPANISH_BREADTH_PLAN.md B1 legal topic", [("Declaro la verdad.", "I state the truth."), ("Ella declara ante el juez.", "She testifies before the judge.")]),
    ("comparecer", "verb", None, "to appear formally", 2400, "B2", 0.6, "legal and bureaucracy", "SPANISH_BREADTH_PLAN.md B2 legal topic", [("Comparezco ante el juez.", "I appear before the judge."), ("Debes comparecer mañana.", "You must appear tomorrow.")]),
    ("sancionar", "verb", None, "to penalize; sanction", 2100, "B2", 0.6, "legal and public services", "SPANISH_BREADTH_PLAN.md B2 legal/public services topic", [("Sancionan a la empresa.", "They penalize the company."), ("Pueden sancionar el incumplimiento.", "They can penalize noncompliance.")]),
    ("multar", "verb", None, "to fine", 2200, "B1", 0.6, "legal and travel", "SPANISH_BREADTH_PLAN.md B1 legal/travel topic", [("Me multan por aparcar mal.", "They fine me for bad parking."), ("Pueden multar al conductor.", "They can fine the driver.")]),
    ("recurso", "noun", "M", "appeal; resource", 1200, "B2", 0.6, "legal and bureaucracy", "SPANISH_BREADTH_PLAN.md B2 legal topic", [("Presento un recurso.", "I file an appeal."), ("El recurso sigue pendiente.", "The appeal remains pending.")]),
    ("apelación", "noun", "F", "appeal", 2200, "B2", 0.6, "legal", "SPANISH_BREADTH_PLAN.md B2 legal topic", [("La apelación tarda meses.", "The appeal takes months."), ("Preparo la apelación.", "I prepare the appeal.")]),
    ("sentencia", "noun", "F", "sentence; ruling", 1100, "B2", 0.6, "legal", "SPANISH_BREADTH_PLAN.md B2 legal topic", [("La sentencia sale hoy.", "The ruling comes out today."), ("Leo la sentencia completa.", "I read the complete ruling.")]),
    ("acusación", "noun", "F", "accusation", 1900, "B2", 0.6, "legal and conflict", "SPANISH_BREADTH_PLAN.md B2 legal/conflict topic", [("La acusación es grave.", "The accusation is serious."), ("Niega la acusación.", "He denies the accusation.")]),
    ("defensa legal", "noun phrase", "F", "legal defense", 2600, "B2", 0.6, "legal", "SPANISH_BREADTH_PLAN.md B2 legal topic", [("Necesito defensa legal.", "I need legal defense."), ("La defensa legal cuesta dinero.", "Legal defense costs money.")]),
    ("asesoría", "noun", "F", "advisory office", 2200, "B2", 0.6, "work legal and money", "SPANISH_BREADTH_PLAN.md B2 services topic", [("Voy a una asesoría.", "I go to an advisory office."), ("La asesoría revisa mis impuestos.", "The advisory office reviews my taxes.")]),
    ("notaría", "noun", "F", "notary office", 2500, "B2", 0.6, "legal and bureaucracy", "SPANISH_BREADTH_PLAN.md B2 legal/bureaucracy topic", [("Voy a la notaría.", "I go to the notary office."), ("Firmo en la notaría.", "I sign at the notary office.")]),
    ("registro civil", "noun phrase", "M", "civil registry", 2500, "B2", 0.6, "public services", "SPANISH_BREADTH_PLAN.md B2 public services topic", [("Voy al registro civil.", "I go to the civil registry."), ("El registro civil emite certificados.", "The civil registry issues certificates.")]),
    ("certificado médico", "noun phrase", "M", "medical certificate", 2200, "B1", 0.6, "medical and work", "SPANISH_BREADTH_PLAN.md B1 medical/work topic", [("Necesito un certificado médico.", "I need a medical certificate."), ("El certificado médico llega hoy.", "The medical certificate arrives today.")]),
    ("alta médica", "noun phrase", "F", "medical discharge", 2300, "B2", 0.6, "medical systems", "SPANISH_BREADTH_PLAN.md B2 medical systems topic", [("Recibo el alta médica.", "I receive medical discharge."), ("El alta médica depende del doctor.", "Medical discharge depends on the doctor.")]),
    ("baja médica", "noun phrase", "F", "sick leave", 2100, "B1", 0.6, "medical and work", "SPANISH_BREADTH_PLAN.md B1 medical/work topic", [("Tengo baja médica.", "I have sick leave."), ("La baja médica dura una semana.", "The sick leave lasts one week.")]),
    ("cita médica", "noun phrase", "F", "medical appointment", 1200, "B1", 0.5, "medical systems", "SPANISH_BREADTH_PLAN.md B1 medical topic", [("Tengo una cita médica.", "I have a medical appointment."), ("Cambio la cita médica.", "I change the medical appointment.")]),
    ("mareo", "noun", "M", "dizziness", 1900, "B1", 0.5, "medical symptoms", "SPANISH_BREADTH_PLAN.md B1 medical symptoms topic", [("Siento mareo.", "I feel dizzy."), ("El mareo pasa pronto.", "Dizziness passes soon.")]),
    ("vómito", "noun", "M", "vomiting", 2200, "B1", 0.6, "medical symptoms", "SPANISH_BREADTH_PLAN.md B1 medical symptoms topic", [("El vómito continúa.", "The vomiting continues."), ("El niño tiene vómitos.", "The child is vomiting.")]),
    ("estornudo", "noun", "M", "sneeze", 2200, "B1", 0.6, "medical symptoms", "SPANISH_BREADTH_PLAN.md B1 medical symptoms topic", [("Los estornudos me molestan.", "The sneezes bother me."), ("Tengo estornudos por la alergia.", "I sneeze because of allergies.")]),
    ("análisis de sangre", "noun phrase", "M", "blood test", 2300, "B1", 0.6, "medical systems", "SPANISH_BREADTH_PLAN.md B1 medical systems topic", [("Necesito un análisis de sangre.", "I need a blood test."), ("El análisis de sangre sale bien.", "The blood test comes out well.")]),
    ("presión arterial", "noun phrase", "F", "blood pressure", 2100, "B1", 0.6, "medical systems", "SPANISH_BREADTH_PLAN.md B1 medical systems topic", [("Miden mi presión arterial.", "They measure my blood pressure."), ("La presión arterial está alta.", "Blood pressure is high.")]),
    ("seguro privado", "noun phrase", "M", "private insurance", 2200, "B2", 0.6, "health and money", "SPANISH_BREADTH_PLAN.md B2 health/money topic", [("Tengo seguro privado.", "I have private insurance."), ("El seguro privado cubre la consulta.", "Private insurance covers the consultation.")]),
    ("tarjeta sanitaria", "noun phrase", "F", "health card", 2100, "B1", 0.6, "health systems", "SPANISH_BREADTH_PLAN.md B1 health systems topic", [("Traigo mi tarjeta sanitaria.", "I bring my health card."), ("La tarjeta sanitaria está vencida.", "The health card is expired.")]),
    ("centro de salud", "noun phrase", "M", "health center", 1500, "B1", 0.5, "health systems", "SPANISH_BREADTH_PLAN.md B1 health systems topic", [("Voy al centro de salud.", "I go to the health center."), ("El centro de salud abre temprano.", "The health center opens early.")]),
    ("persiana", "noun", "F", "blind; shutter", 2200, "B1", 0.6, "household and repairs", "SPANISH_BREADTH_PLAN.md B1 household topic", [("La persiana está rota.", "The blind is broken."), ("Subo la persiana.", "I raise the blind.")]),
    ("bombilla", "noun", "F", "light bulb", 2200, "B1", 0.6, "household and repairs", "SPANISH_BREADTH_PLAN.md B1 household topic", [("Cambio la bombilla.", "I change the bulb."), ("La bombilla no funciona.", "The bulb does not work.")]),
    ("interruptor", "noun", "M", "switch", 2200, "B1", 0.6, "household and repairs", "SPANISH_BREADTH_PLAN.md B1 household topic", [("El interruptor falla.", "The switch fails."), ("Pulso el interruptor.", "I press the switch.")]),
    ("calentador", "noun", "M", "water heater", 2200, "B1", 0.6, "household and repairs", "SPANISH_BREADTH_PLAN.md B1 household topic", [("El calentador no enciende.", "The heater does not start."), ("Reviso el calentador.", "I check the heater.")]),
    ("nevera", "noun", "F", "fridge", 1600, "B1", 0.5, "household", "SPANISH_BREADTH_PLAN.md B1 household topic", [("La nevera está vacía.", "The fridge is empty."), ("Limpio la nevera.", "I clean the fridge.")]),
    ("lavadora", "noun", "F", "washing machine", 1900, "B1", 0.5, "household", "SPANISH_BREADTH_PLAN.md B1 household topic", [("La lavadora pierde agua.", "The washer leaks water."), ("Uso la lavadora.", "I use the washer.")]),
    ("fregadero", "noun", "M", "sink", 2200, "B1", 0.6, "household and repairs", "SPANISH_BREADTH_PLAN.md B1 household topic", [("El fregadero está atascado.", "The sink is clogged."), ("Limpio el fregadero.", "I clean the sink.")]),
    ("horno", "noun", "M", "oven", 1700, "B1", 0.5, "household and food", "SPANISH_BREADTH_PLAN.md B1 household/food topic", [("El horno calienta mal.", "The oven heats badly."), ("Apago el horno.", "I turn off the oven.")]),
    ("colchón", "noun", "M", "mattress", 2200, "B1", 0.6, "household and lodging", "SPANISH_BREADTH_PLAN.md B1 lodging topic", [("El colchón es incómodo.", "The mattress is uncomfortable."), ("Cambio el colchón.", "I change the mattress.")]),
    ("armario", "noun", "M", "closet; cabinet", 1800, "B1", 0.5, "household", "SPANISH_BREADTH_PLAN.md B1 household topic", [("El armario está lleno.", "The closet is full."), ("Ordeno el armario.", "I organize the closet.")]),
    ("pasillo", "noun", "M", "hallway", 1800, "B1", 0.5, "housing and travel", "SPANISH_BREADTH_PLAN.md B1 housing/lodging topic", [("El pasillo está oscuro.", "The hallway is dark."), ("Espero en el pasillo.", "I wait in the hallway.")]),
    ("balcón", "noun", "M", "balcony", 1700, "B1", 0.5, "housing", "SPANISH_BREADTH_PLAN.md B1 housing topic", [("El balcón es pequeño.", "The balcony is small."), ("Limpio el balcón.", "I clean the balcony.")]),
    ("escalera", "noun", "F", "stairs; ladder", 1500, "B1", 0.5, "housing and travel", "SPANISH_BREADTH_PLAN.md B1 housing topic", [("Subo la escalera.", "I climb the stairs."), ("La escalera está mojada.", "The stairs are wet.")]),
    ("ruido", "noun", "M", "noise", 1200, "B1", 0.5, "housing and complaints", "SPANISH_BREADTH_PLAN.md B1 housing/complaints topic", [("El ruido no me deja dormir.", "The noise keeps me awake."), ("Denuncio el ruido.", "I report the noise.")]),
    ("reforma", "noun", "F", "renovation; reform", 1300, "B1", 0.5, "housing and services", "SPANISH_BREADTH_PLAN.md B1 housing/services topic", [("La reforma empieza mañana.", "The renovation starts tomorrow."), ("Pago parte de la reforma.", "I pay part of the renovation.")]),
    ("sueldo", "noun", "M", "salary", 1600, "B1", 0.5, "work and money", "SPANISH_BREADTH_PLAN.md B1 work/money topic", [("Cobro el sueldo mañana.", "I collect my salary tomorrow."), ("El sueldo no alcanza.", "The salary is not enough.")]),
    ("convenio", "noun", "M", "agreement; labor contract", 1500, "B2", 0.6, "work and legal", "SPANISH_BREADTH_PLAN.md B2 workplace/legal topic", [("El convenio mejora el horario.", "The agreement improves the schedule."), ("Reviso el convenio.", "I review the agreement.")]),
    ("jornada laboral", "noun phrase", "F", "workday", 1800, "B1", 0.5, "work", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [("La jornada laboral termina tarde.", "The workday ends late."), ("Reduzco mi jornada laboral.", "I reduce my workday.")]),
    ("contrato temporal", "noun phrase", "M", "temporary contract", 1900, "B1", 0.6, "work and legal", "SPANISH_BREADTH_PLAN.md B1 workplace/legal topic", [("Tengo un contrato temporal.", "I have a temporary contract."), ("El contrato temporal termina pronto.", "The temporary contract ends soon.")]),
    ("baja laboral", "noun phrase", "F", "work leave", 2000, "B2", 0.6, "work and medical", "SPANISH_BREADTH_PLAN.md B2 workplace/medical topic", [("Pido una baja laboral.", "I request work leave."), ("La baja laboral está aprobada.", "The work leave is approved.")]),
    ("permiso laboral", "noun phrase", "M", "work permit", 1900, "B1", 0.6, "work and bureaucracy", "SPANISH_BREADTH_PLAN.md B1 workplace/bureaucracy topic", [("Necesito permiso laboral.", "I need work permission."), ("El permiso laboral está firmado.", "The work permit is signed.")]),
    ("entrevista", "noun", "F", "interview", 1200, "B1", 0.5, "work and social", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [("Tengo una entrevista mañana.", "I have an interview tomorrow."), ("La entrevista sale bien.", "The interview goes well.")]),
    ("currículum", "noun", "M", "resume", 2000, "B1", 0.6, "work", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [("Envío mi currículum.", "I send my resume."), ("Actualizo el currículum.", "I update the resume.")]),
    ("departamento", "noun", "M", "department", 900, "B1", 0.5, "work and services", "SPANISH_BREADTH_PLAN.md B1 workplace/services topic", [("Trabajo en otro departamento.", "I work in another department."), ("El departamento responde tarde.", "The department answers late.")]),
    ("equipo de trabajo", "noun phrase", "M", "work team", 1600, "B1", 0.5, "work and collaboration", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [("El equipo de trabajo ayuda.", "The work team helps."), ("Cambio de equipo de trabajo mañana.", "I change work teams tomorrow.")]),
    ("puerta de embarque", "noun phrase", "F", "boarding gate", 1900, "B1", 0.6, "travel", "SPANISH_BREADTH_PLAN.md B1 travel topic", [("Busco la puerta de embarque.", "I look for the boarding gate."), ("La puerta de embarque cambia.", "The boarding gate changes.")]),
    ("tarjeta de embarque", "noun phrase", "F", "boarding pass", 1900, "B1", 0.6, "travel", "SPANISH_BREADTH_PLAN.md B1 travel topic", [("Imprimo la tarjeta de embarque.", "I print the boarding pass."), ("Pierdo la tarjeta de embarque.", "I lose the boarding pass.")]),
    ("transbordo", "noun", "M", "transfer", 1700, "B1", 0.5, "travel and transit", "SPANISH_BREADTH_PLAN.md B1 transit topic", [("Hago transbordo en Madrid.", "I transfer in Madrid."), ("El transbordo tarda diez minutos.", "The transfer takes ten minutes.")]),
    ("atención al cliente", "noun phrase", "F", "customer service", 1400, "B1", 0.5, "services and complaints", "SPANISH_BREADTH_PLAN.md B1 services topic", [("Llamo a atención al cliente.", "I call customer service."), ("Atención al cliente no responde.", "Customer service does not answer.")]),
    ("hoja de reclamaciones", "noun phrase", "F", "complaint form", 2400, "B2", 0.6, "services and legal", "SPANISH_BREADTH_PLAN.md B2 services/legal topic", [("Pido la hoja de reclamaciones.", "I request the complaint form."), ("Relleno la hoja de reclamaciones.", "I fill the complaint form.")]),
    ("servicio técnico", "noun phrase", "M", "technical service", 1900, "B1", 0.6, "services and repairs", "SPANISH_BREADTH_PLAN.md B1 services/repairs topic", [("Llamo al servicio técnico.", "I call technical service."), ("El servicio técnico llega tarde.", "Technical service arrives late.")]),
    ("devolución", "noun", "F", "return; refund", 1600, "B1", 0.5, "shopping and services", "SPANISH_BREADTH_PLAN.md B1 shopping/services topic", [("Pido una devolución.", "I request a return."), ("La devolución tarda tres días.", "The return takes three days.")]),
    ("cambio de producto", "noun phrase", "M", "product exchange", 2300, "B1", 0.6, "shopping and services", "SPANISH_BREADTH_PLAN.md B1 shopping/services topic", [("Pido un cambio de producto.", "I request a product exchange."), ("El cambio de producto es gratis.", "The product exchange is free.")]),
    ("factura electrónica", "noun phrase", "F", "electronic invoice", 2000, "B1", 0.6, "money and services", "SPANISH_BREADTH_PLAN.md B1 money/services topic", [("Recibo la factura electrónica.", "I receive the electronic invoice."), ("La factura electrónica está lista.", "The electronic invoice is ready.")]),
    ("cajero automático", "noun phrase", "M", "ATM", 1700, "B1", 0.5, "banking and travel", "SPANISH_BREADTH_PLAN.md B1 banking topic", [("Uso el cajero automático.", "I use the ATM."), ("El cajero automático no funciona.", "The ATM does not work.")]),
    ("cuenta corriente", "noun phrase", "F", "checking account", 1800, "B1", 0.5, "banking", "SPANISH_BREADTH_PLAN.md B1 banking topic", [("Abro una cuenta corriente.", "I open a checking account."), ("La cuenta corriente tiene saldo.", "The checking account has balance.")]),
    ("cargo bancario", "noun phrase", "M", "bank charge", 2000, "B1", 0.6, "banking and complaints", "SPANISH_BREADTH_PLAN.md B1 banking/complaints topic", [("No reconozco el cargo bancario.", "I do not recognize the charge."), ("El cargo bancario es incorrecto.", "The bank charge is incorrect.")]),
    ("saldo disponible", "noun phrase", "M", "available balance", 1900, "B1", 0.5, "banking", "SPANISH_BREADTH_PLAN.md B1 banking topic", [("Consulto el saldo disponible.", "I check the available balance."), ("El saldo disponible es bajo.", "The available balance is low.")]),
    ("tipo de interés", "noun phrase", "M", "interest rate", 1900, "B2", 0.6, "banking and money", "SPANISH_BREADTH_PLAN.md B2 banking topic", [("El tipo de interés sube.", "The interest rate rises."), ("Comparo el tipo de interés.", "I compare the interest rate.")]),
    ("pago pendiente", "noun phrase", "M", "pending payment", 1700, "B1", 0.5, "money and obligations", "SPANISH_BREADTH_PLAN.md B1 money/obligations topic", [("Tengo un pago pendiente.", "I have a pending payment."), ("El pago pendiente vence hoy.", "The pending payment is due today.")]),
    ("recibo domiciliado", "noun phrase", "M", "direct-debit bill", 2300, "B2", 0.6, "banking and housing", "SPANISH_BREADTH_PLAN.md B2 banking/housing topic", [("Pago el recibo domiciliado.", "I pay the direct-debit bill."), ("El recibo domiciliado falla.", "The direct-debit bill fails.")]),
    ("presupuesto cerrado", "noun phrase", "M", "fixed estimate", 2300, "B2", 0.6, "money and services", "SPANISH_BREADTH_PLAN.md B2 money/services topic", [("Quiero un presupuesto cerrado.", "I want a fixed estimate."), ("El presupuesto cerrado incluye todo.", "The fixed estimate includes everything.")]),
    ("contrato escrito", "noun phrase", "M", "written contract", 1900, "B1", 0.5, "legal and work", "SPANISH_BREADTH_PLAN.md B1 legal/work topic", [("Necesito un contrato escrito.", "I need a written contract."), ("El contrato escrito protege a ambos.", "The written contract protects both.")]),
    ("acuerdo verbal", "noun phrase", "M", "verbal agreement", 2200, "B2", 0.6, "work and legal", "SPANISH_BREADTH_PLAN.md B2 workplace/legal topic", [("Tenemos un acuerdo verbal.", "We have a verbal agreement."), ("El acuerdo verbal no basta.", "The verbal agreement is insufficient.")]),
    ("en mi opinión", "adverbial phrase", None, "in my opinion", 1100, "B1", 0.5, "opinion language", "SPANISH_BREADTH_PLAN.md B1 opinion language topic", [("En mi opinión, conviene esperar.", "In my opinion, waiting helps."), ("En mi opinión, falta información.", "In my opinion, information is missing.")]),
])


AI_ACCELERATED_PACK_A2_015 = build_numbered_ai_accelerated_pack(827, 1713, 1716, [
    ("a ver", "discourse marker", None, "let's see", 900, "B1", 0.5, "conversation repair", "SPANISH_BREADTH_PLAN.md B1 conversation repair topic", [("A ver, explícame eso.", "Let's see, explain that."), ("A ver, repite despacio.", "Let's see, repeat slowly.")]),
    ("o sea", "discourse marker", None, "I mean; that is", 900, "B1", 0.5, "conversation repair", "SPANISH_BREADTH_PLAN.md B1 conversation repair topic", [("O sea, necesito otra cita.", "I mean, I need another appointment."), ("O sea, no entiendo bien.", "I mean, I do not understand well.")]),
    ("me refiero a", "verbal phrase", None, "I mean; I refer to", 1300, "B1", 0.5, "clarification", "SPANISH_BREADTH_PLAN.md B1 conversation repair topic", [("Me refiero al recibo.", "I mean the receipt."), ("Me refiero a este documento.", "I mean this document.")]),
    ("quiero decir", "verbal phrase", None, "I mean", 1000, "B1", 0.5, "clarification", "SPANISH_BREADTH_PLAN.md B1 conversation repair topic", [("Quiero decir otra cosa.", "I mean something else."), ("Quiero decir que acepto.", "I mean that I accept.")]),
    ("si no me equivoco", "adverbial phrase", None, "if I am not mistaken", 1900, "B2", 0.6, "careful speech", "SPANISH_BREADTH_PLAN.md B2 conversation repair topic", [("Si no me equivoco, falta una firma.", "Unless I am wrong, a signature is missing."), ("Si no me equivoco, pagué ayer.", "If I am not mistaken, I paid yesterday.")]),
    ("corrígeme si me equivoco", "sentence chunk", None, "correct me if I am wrong", 2600, "B2", 0.6, "conversation repair", "SPANISH_BREADTH_PLAN.md B2 conversation repair topic", [("Corrígeme si me equivoco.", "Correct me if I am wrong."), ("Corrígeme si me equivoco, por favor.", "Correct me if I am wrong, please.")]),
    ("dicho de otra manera", "adverbial phrase", None, "said another way", 2500, "B2", 0.6, "clarification", "SPANISH_BREADTH_PLAN.md B2 discourse markers topic", [("Dicho de otra manera, acepto.", "Said another way, I accept."), ("Dicho de otra manera, falta dinero.", "Said another way, money is missing.")]),
    ("por así decirlo", "adverbial phrase", None, "so to speak", 2600, "B2", 0.6, "argument nuance", "SPANISH_BREADTH_PLAN.md B2 discourse markers topic", [("Es mi turno, por así decirlo.", "It is my turn, so to speak."), ("La oficina duerme, por así decirlo.", "The office sleeps, so to speak.")]),
    ("en pocas palabras", "adverbial phrase", None, "in short", 1900, "B1", 0.5, "summaries", "SPANISH_BREADTH_PLAN.md B1 discourse markers topic", [("En pocas palabras, necesito ayuda.", "In short, I need help."), ("En pocas palabras, no funciona.", "In short, it does not work.")]),
    ("en definitiva", "adverbial phrase", None, "ultimately", 1800, "B2", 0.6, "summaries and opinion", "SPANISH_BREADTH_PLAN.md B2 discourse markers topic", [("En definitiva, conviene llamar.", "Ultimately, calling is useful."), ("En definitiva, aceptamos el acuerdo.", "Ultimately, we accept the agreement.")]),
    ("para empezar", "adverbial phrase", None, "to begin with", 1500, "B1", 0.5, "sequencing", "SPANISH_BREADTH_PLAN.md B1 discourse markers topic", [("Para empezar, necesito tu nombre.", "To begin with, I need your name."), ("Para empezar, revise el formulario.", "To begin with, check the form.")]),
    ("para terminar", "adverbial phrase", None, "to finish", 1600, "B1", 0.5, "sequencing", "SPANISH_BREADTH_PLAN.md B1 discourse markers topic", [("Para terminar, firme aquí.", "To finish, sign here."), ("Para terminar, gracias por venir.", "To finish, thank you for coming.")]),
    ("en primer lugar", "adverbial phrase", None, "first of all", 1500, "B1", 0.5, "structured argument", "SPANISH_BREADTH_PLAN.md B1 discourse markers topic", [("En primer lugar, pago la tasa.", "First of all, I pay the fee."), ("En primer lugar, reviso el contrato.", "First of all, I review the contract.")]),
    ("en segundo lugar", "adverbial phrase", None, "secondly", 1600, "B1", 0.5, "structured argument", "SPANISH_BREADTH_PLAN.md B1 discourse markers topic", [("En segundo lugar, envío la copia.", "Secondly, I send the copy."), ("En segundo lugar, llamo al banco.", "Secondly, I call the bank.")]),
    ("por último", "adverbial phrase", None, "finally", 1200, "B1", 0.5, "sequencing", "SPANISH_BREADTH_PLAN.md B1 discourse markers topic", [("Por último, firmo el documento.", "Finally, I sign the document."), ("Por último, espero la respuesta.", "Finally, I wait for the answer.")]),
    ("por una parte", "adverbial phrase", None, "on one hand", 1700, "B1", 0.5, "structured opinion", "SPANISH_BREADTH_PLAN.md B1 opinion language topic", [("Por una parte, entiendo tu problema.", "On one hand, I understand your problem."), ("Por una parte, el precio ayuda.", "On one hand, the price helps.")]),
    ("por otra parte", "adverbial phrase", None, "on the other hand", 1700, "B1", 0.5, "structured opinion", "SPANISH_BREADTH_PLAN.md B1 opinion language topic", [("Por otra parte, falta tiempo.", "On the other hand, time is missing."), ("Por otra parte, el contrato cambia.", "On the other hand, the contract changes.")]),
    ("sea como sea", "adverbial phrase", None, "be that as it may", 2100, "B2", 0.6, "argument repair", "SPANISH_BREADTH_PLAN.md B2 discourse markers topic", [("Sea como sea, voy mañana.", "Be that as it may, I go tomorrow."), ("Sea como sea, necesito pagar.", "Either way, I need to pay.")]),
    ("de todas formas", "adverbial phrase", None, "anyway", 1300, "B1", 0.5, "discourse markers", "SPANISH_BREADTH_PLAN.md B1 everyday chunks topic", [("De todas formas, llamo luego.", "Anyway, I call later."), ("De todas formas, gracias.", "Anyway, thank you.")]),
    ("de momento", "adverbial phrase", None, "for now", 1000, "B1", 0.5, "status and planning", "SPANISH_BREADTH_PLAN.md B1 planning chunks topic", [("De momento, espero aquí.", "For now, I wait here."), ("De momento, no hay respuesta.", "For now, there is no answer.")]),
    ("hasta entonces", "adverbial phrase", None, "until then", 1600, "B1", 0.5, "time and planning", "SPANISH_BREADTH_PLAN.md B1 sequencing topic", [("Hasta entonces, guardo la copia.", "Until then, I keep the copy."), ("Hasta entonces, espero noticias.", "Until then, I await news.")]),
    ("desde luego que sí", "sentence chunk", None, "of course yes", 1900, "B1", 0.5, "agreement", "SPANISH_BREADTH_PLAN.md B1 opinion chunks topic", [("Desde luego que sí.", "Of course."), ("Desde luego que sí, acepto.", "Of course, I accept.")]),
    ("claro que no", "sentence chunk", None, "of course not", 1200, "B1", 0.5, "disagreement", "SPANISH_BREADTH_PLAN.md B1 opinion chunks topic", [("Claro que no.", "Of course not."), ("Claro que no, falta una prueba.", "Of course not, evidence is missing.")]),
    ("ni hablar", "sentence chunk", None, "no way", 1600, "B1", 0.5, "strong disagreement", "SPANISH_BREADTH_PLAN.md B1 opinion chunks topic", [("Ni hablar, no pago eso.", "No way, I do not pay that."), ("Ni hablar, es abusivo.", "No way, it is unfair.")]),
    ("ni modo", "sentence chunk", None, "no way; oh well", 2100, "B2", 0.6, "reaction chunks", "SPANISH_BREADTH_PLAN.md B2 everyday chunks topic", [("Ni modo, espero otra vez.", "Oh well, I wait again."), ("Ni modo, cambio el plan.", "Oh well, I change the plan.")]),
    ("qué va", "sentence chunk", None, "no way", 1700, "B1", 0.5, "informal disagreement", "SPANISH_BREADTH_PLAN.md B1 conversation chunks topic", [("Qué va, no es tarde.", "No way, it is not late."), ("Qué va, estoy bien.", "No way, I am fine.")]),
    ("ya veo", "sentence chunk", None, "I see", 900, "B1", 0.5, "listening and repair", "SPANISH_BREADTH_PLAN.md B1 listening chunks topic", [("Ya veo, gracias.", "I see, thank you."), ("Ya veo el problema.", "I see the problem.")]),
    ("entiendo", "sentence chunk", None, "I understand", 850, "B1", 0.5, "listening and repair", "SPANISH_BREADTH_PLAN.md B1 listening chunks topic", [("Entiendo, gracias.", "I understand, thank you."), ("Entiendo tu queja.", "I understand your complaint.")]),
    ("lo siento", "sentence chunk", None, "I am sorry", 900, "B1", 0.5, "apologies", "SPANISH_BREADTH_PLAN.md B1 social repair topic", [("Lo siento mucho.", "I am very sorry."), ("Lo siento, llego tarde.", "I am sorry, I arrive late.")]),
    ("perdona", "sentence chunk", None, "sorry; excuse me", 1300, "B1", 0.5, "apologies and repair", "SPANISH_BREADTH_PLAN.md B1 conversation repair topic", [("Perdona, no te oigo.", "Sorry, I cannot hear you."), ("Perdona, repite eso.", "Sorry, repeat that.")]),
    ("disculpe", "sentence chunk", None, "excuse me", 1300, "B1", 0.5, "formal repair", "SPANISH_BREADTH_PLAN.md B1 conversation repair topic", [("Disculpe, tengo una duda.", "Excuse me, I have a question."), ("Disculpe, no entiendo.", "Excuse me, I do not understand.")]),
    ("un momento", "sentence chunk", None, "one moment", 900, "B1", 0.5, "conversation repair", "SPANISH_BREADTH_PLAN.md B1 conversation repair topic", [("Un momento, por favor.", "One moment, please."), ("Un momento, reviso la factura.", "One moment, I check the invoice.")]),
    ("espere un momento", "sentence chunk", None, "wait a moment", 1500, "B1", 0.5, "service interaction", "SPANISH_BREADTH_PLAN.md B1 service chunks topic", [("Espere un momento, por favor.", "Wait a moment, please."), ("Espere un momento en recepción.", "Wait a moment at reception.")]),
    ("hable más despacio", "sentence chunk", None, "speak more slowly", 1800, "B1", 0.5, "listening repair", "SPANISH_BREADTH_PLAN.md B1 listening chunks topic", [("Hable más despacio, por favor.", "Speak more slowly, please."), ("Hable más despacio, no entiendo.", "Speak more slowly, I do not understand.")]),
    ("no le oigo", "sentence chunk", None, "I cannot hear you", 1800, "B1", 0.5, "listening repair", "SPANISH_BREADTH_PLAN.md B1 listening chunks topic", [("No le oigo bien.", "I cannot hear you well."), ("No le oigo por el ruido.", "I cannot hear you because of noise.")]),
    ("se corta la llamada", "sentence chunk", None, "the call is breaking up", 2200, "B1", 0.6, "phone repair", "SPANISH_BREADTH_PLAN.md B1 phone repair topic", [("Se corta la llamada.", "The call is breaking up."), ("Se corta la llamada otra vez.", "The call is breaking up again.")]),
    ("se oye mal", "sentence chunk", None, "it sounds bad", 1900, "B1", 0.5, "listening repair", "SPANISH_BREADTH_PLAN.md B1 listening chunks topic", [("Se oye mal.", "It sounds bad."), ("Se oye mal en mi teléfono.", "It sounds bad on my phone.")]),
    ("repita por favor", "sentence chunk", None, "repeat please", 1600, "B1", 0.5, "listening repair", "SPANISH_BREADTH_PLAN.md B1 listening chunks topic", [("Repita, por favor.", "Repeat, please."), ("Repita por favor el número.", "Please repeat the number.")]),
    ("puede repetir", "sentence chunk", None, "can you repeat", 1500, "B1", 0.5, "listening repair", "SPANISH_BREADTH_PLAN.md B1 listening chunks topic", [("¿Puede repetir, por favor?", "Can you repeat, please?"), ("¿Puede repetir la dirección?", "Can you repeat the address?")]),
    ("cómo se pronuncia", "question chunk", None, "how is it pronounced", 1900, "B1", 0.5, "pronunciation repair", "SPANISH_BREADTH_PLAN.md B1 pronunciation topic", [("¿Cómo se pronuncia esto?", "How is this pronounced?"), ("¿Cómo se pronuncia su apellido?", "How is your surname pronounced?")]),
    ("cómo se escribe", "question chunk", None, "how is it written", 1700, "B1", 0.5, "spelling repair", "SPANISH_BREADTH_PLAN.md B1 spelling topic", [("¿Cómo se escribe su nombre?", "How is your name written?"), ("¿Cómo se escribe la calle?", "How is the street written?")]),
    ("qué significa", "question chunk", None, "what does it mean", 1200, "B1", 0.5, "meaning repair", "SPANISH_BREADTH_PLAN.md B1 conversation repair topic", [("¿Qué significa esta palabra?", "What does this word mean?"), ("¿Qué significa este aviso?", "What does this notice mean?")]),
    ("a qué se refiere", "question chunk", None, "what does it refer to", 1800, "B2", 0.6, "clarification", "SPANISH_BREADTH_PLAN.md B2 conversation repair topic", [("¿A qué se refiere?", "What does it refer to?"), ("¿A qué se refiere la carta?", "What does the letter refer to?")]),
    ("no me queda claro", "sentence chunk", None, "it is not clear to me", 1800, "B1", 0.5, "clarification", "SPANISH_BREADTH_PLAN.md B1 conversation repair topic", [("No me queda claro.", "It is not clear to me."), ("No me queda claro el plazo.", "The deadline is not clear to me.")]),
    ("me queda claro", "sentence chunk", None, "it is clear to me", 1700, "B1", 0.5, "confirmation", "SPANISH_BREADTH_PLAN.md B1 conversation repair topic", [("Ahora me queda claro.", "Now it is clear to me."), ("Me queda claro el precio.", "The price is clear to me.")]),
    ("estoy de acuerdo", "sentence chunk", None, "I agree", 900, "B1", 0.5, "agreement", "SPANISH_BREADTH_PLAN.md B1 opinion chunks topic", [("Estoy de acuerdo contigo.", "I agree with you."), ("Estoy de acuerdo con la propuesta.", "I agree with the proposal.")]),
    ("no estoy seguro", "sentence chunk", None, "I am not sure", 900, "B1", 0.5, "uncertainty", "SPANISH_BREADTH_PLAN.md B1 opinion chunks topic", [("No estoy seguro.", "I am not sure."), ("No estoy seguro del precio.", "I am not sure about the price.")]),
    ("depende", "sentence chunk", None, "it depends", 900, "B1", 0.5, "uncertainty", "SPANISH_BREADTH_PLAN.md B1 opinion chunks topic", [("Depende del horario.", "It depends on the schedule."), ("Depende de la respuesta.", "It depends on the answer.")]),
    ("puede ser", "sentence chunk", None, "maybe; it could be", 950, "B1", 0.5, "uncertainty", "SPANISH_BREADTH_PLAN.md B1 opinion chunks topic", [("Puede ser verdad.", "It could be true."), ("Puede ser una buena opción.", "It could be a good option.")]),
    ("me preocupa", "sentence chunk", None, "it worries me", 1300, "B1", 0.5, "concerns and opinion", "SPANISH_BREADTH_PLAN.md B1 emotions/opinions topic", [("Me preocupa el retraso.", "The delay worries me."), ("Me preocupa la factura.", "The bill worries me.")]),
    ("me molesta", "sentence chunk", None, "it bothers me", 1300, "B1", 0.5, "complaints", "SPANISH_BREADTH_PLAN.md B1 complaint language topic", [("Me molesta el ruido.", "The noise bothers me."), ("Me molesta esperar tanto.", "Waiting so long bothers me.")]),
    ("me conviene", "sentence chunk", None, "it suits me", 1400, "B1", 0.5, "preferences", "SPANISH_BREADTH_PLAN.md B1 preference language topic", [("Me conviene pagar mañana.", "Paying tomorrow suits me."), ("Me conviene este horario.", "This schedule suits me.")]),
    ("me interesa", "sentence chunk", None, "it interests me", 1100, "B1", 0.5, "preferences", "SPANISH_BREADTH_PLAN.md B1 preference language topic", [("Me interesa esa opción.", "That option interests me."), ("Me interesa el contrato.", "The contract interests me.")]),
    ("me cuesta", "sentence chunk", None, "it is hard for me", 1200, "B1", 0.5, "difficulty and repair", "SPANISH_BREADTH_PLAN.md B1 conversation repair topic", [("Me cuesta entenderlo.", "Understanding it is hard for me."), ("Me cuesta pagar todo.", "Paying everything is hard for me.")]),
    ("me hace falta", "sentence chunk", None, "I need", 1000, "B1", 0.5, "needs and services", "SPANISH_BREADTH_PLAN.md B1 needs topic", [("Me hace falta una copia.", "I need a copy."), ("Me hace falta más tiempo.", "I need more time.")]),
    ("me falta", "sentence chunk", None, "I am missing", 1000, "B1", 0.5, "needs and paperwork", "SPANISH_BREADTH_PLAN.md B1 needs topic", [("Me falta una firma.", "I am missing a signature."), ("Me falta el recibo.", "I am missing the receipt.")]),
    ("me sobra", "sentence chunk", None, "I have extra", 1300, "B1", 0.5, "money and quantities", "SPANISH_BREADTH_PLAN.md B1 money/topic", [("Me sobra dinero.", "I have extra money."), ("Me sobra una copia.", "I have an extra copy.")]),
    ("me urge", "sentence chunk", None, "it is urgent for me", 1400, "B1", 0.5, "urgency and services", "SPANISH_BREADTH_PLAN.md B1 urgency topic", [("Me urge una respuesta.", "An answer is urgent for me."), ("Me urge cambiar la cita.", "Changing the appointment is urgent for me.")]),
    ("me da miedo", "sentence chunk", None, "it scares me", 1200, "B1", 0.5, "emotions and medical", "SPANISH_BREADTH_PLAN.md B1 emotions topic", [("Me da miedo la operación.", "The operation scares me."), ("Me da miedo viajar solo.", "Traveling alone scares me.")]),
    ("me da vergüenza", "sentence chunk", None, "it embarrasses me", 1600, "B1", 0.5, "emotions and repair", "SPANISH_BREADTH_PLAN.md B1 emotions topic", [("Me da vergüenza preguntar.", "Asking embarrasses me."), ("Me da vergüenza reclamar.", "Complaining embarrasses me.")]),
    ("me da rabia", "sentence chunk", None, "it makes me angry", 1800, "B1", 0.5, "emotions and complaints", "SPANISH_BREADTH_PLAN.md B1 emotions/complaints topic", [("Me da rabia esperar.", "Waiting makes me angry."), ("Me da rabia el recargo.", "The surcharge makes me angry.")]),
    ("me da pena", "sentence chunk", None, "it makes me sad", 1600, "B1", 0.5, "emotions", "SPANISH_BREADTH_PLAN.md B1 emotions topic", [("Me da pena cancelar.", "Canceling makes me sad."), ("Me da pena vender la casa.", "Selling the house makes me sad.")]),
    ("me alegra", "sentence chunk", None, "it makes me happy", 1500, "B1", 0.5, "emotions and social", "SPANISH_BREADTH_PLAN.md B1 emotions topic", [("Me alegra verte.", "Seeing you makes me happy."), ("Me alegra la noticia.", "The news makes me happy.")]),
    ("quedar en algo", "verbal phrase", None, "to agree on something", 1800, "B1", 0.5, "negotiation", "SPANISH_BREADTH_PLAN.md B1 negotiation topic", [("Quedamos en llamarnos mañana.", "We agree to call tomorrow."), ("Quedamos en pagar después.", "We agree to pay later.")]),
    ("ponerse de acuerdo", "verbal phrase", None, "to reach agreement", 1600, "B1", 0.5, "negotiation", "SPANISH_BREADTH_PLAN.md B1 negotiation topic", [("Intentamos ponernos de acuerdo.", "We try to reach agreement."), ("Necesito ponerme de acuerdo contigo.", "I need to agree with you.")]),
    ("llegar a un acuerdo", "verbal phrase", None, "to reach an agreement", 1600, "B1", 0.5, "negotiation", "SPANISH_BREADTH_PLAN.md B1 negotiation topic", [("Queremos llegar a un acuerdo.", "We want to reach an agreement."), ("Llegan a un acuerdo hoy.", "They reach an agreement today.")]),
    ("romper el acuerdo", "verbal phrase", None, "to break the agreement", 1900, "B2", 0.6, "legal and conflict", "SPANISH_BREADTH_PLAN.md B2 legal/conflict topic", [("No quiero romper el acuerdo.", "I do not want to break the agreement."), ("Ellos rompen el acuerdo.", "They break the agreement.")]),
    ("hacer falta", "verbal phrase", None, "to be needed", 900, "B1", 0.5, "needs and services", "SPANISH_BREADTH_PLAN.md B1 needs topic", [("Hace falta otra copia.", "Another copy is needed."), ("Hace falta llamar antes.", "Calling beforehand is needed.")]),
    ("tener sentido", "verbal phrase", None, "to make sense", 900, "B1", 0.5, "opinion and repair", "SPANISH_BREADTH_PLAN.md B1 opinion language topic", [("Eso tiene sentido.", "That makes sense."), ("El plan no tiene sentido.", "The plan makes no sense.")]),
    ("tener en cuenta", "verbal phrase", None, "to take into account", 1200, "B1", 0.5, "planning and argument", "SPANISH_BREADTH_PLAN.md B1 argument language topic", [("Ten en cuenta el plazo.", "Take the deadline into account."), ("Tengo en cuenta tu opinión.", "I consider your opinion.")]),
    ("darse cuenta", "verbal phrase", None, "to realize", 900, "B1", 0.5, "narration and repair", "SPANISH_BREADTH_PLAN.md B1 narration topic", [("Me doy cuenta tarde.", "I realize it late."), ("Ella se da cuenta del error.", "She realizes the error.")]),
    ("echar de menos", "verbal phrase", None, "to miss", 1600, "B1", 0.5, "emotions and social", "SPANISH_BREADTH_PLAN.md B1 emotions topic", [("Echo de menos mi casa.", "I miss my home."), ("Echo de menos a mi familia.", "I miss my family.")]),
    ("llevar a cabo", "verbal phrase", None, "to carry out", 1600, "B2", 0.6, "formal work", "SPANISH_BREADTH_PLAN.md B2 work/formal topic", [("Llevamos a cabo el plan.", "We carry out the plan."), ("La empresa lleva a cabo cambios.", "The company carries out changes.")]),
    ("poner en marcha", "verbal phrase", None, "to start up", 1700, "B1", 0.5, "work and services", "SPANISH_BREADTH_PLAN.md B1 work/services topic", [("Pongo en marcha el proyecto.", "I start the project."), ("Ponen en marcha el servicio.", "They start the service.")]),
    ("dar de alta", "verbal phrase", None, "to register; activate", 1800, "B2", 0.6, "medical and services", "SPANISH_BREADTH_PLAN.md B2 services/medical topic", [("Me dan de alta hoy.", "They discharge me today."), ("Doy de alta el servicio.", "I activate the service.")]),
    ("dar de baja", "verbal phrase", None, "to cancel; unregister", 1800, "B2", 0.6, "services and work", "SPANISH_BREADTH_PLAN.md B2 services/work topic", [("Doy de baja el contrato.", "I cancel the contract."), ("Me dan de baja mañana.", "They unregister me tomorrow.")]),
    ("estar al tanto", "verbal phrase", None, "to be aware", 1700, "B1", 0.5, "work and updates", "SPANISH_BREADTH_PLAN.md B1 work/updates topic", [("Estoy al tanto del cambio.", "I am aware of the change."), ("Manténme al tanto, por favor.", "Keep me informed, please.")]),
    ("estar pendiente", "verbal phrase", None, "to be pending; watchful", 1600, "B1", 0.5, "status and planning", "SPANISH_BREADTH_PLAN.md B1 planning topic", [("Estoy pendiente de la respuesta.", "I am waiting for the answer."), ("El pago está pendiente.", "The payment is pending.")]),
    ("enviar adjunto", "verbal phrase", None, "to send attached", 2200, "B1", 0.6, "bureaucracy and technology", "SPANISH_BREADTH_PLAN.md B1 public services topic", [("Envío adjunto el recibo.", "I send the receipt attached."), ("Envíe adjunto el formulario.", "Send the form attached.")]),
    ("acuse de recibo", "noun phrase", "M", "acknowledgment of receipt", 2400, "B2", 0.6, "bureaucracy and legal", "SPANISH_BREADTH_PLAN.md B2 bureaucracy/legal topic", [("Necesito acuse de recibo.", "I need an acknowledgment of receipt."), ("El acuse de recibo llega hoy.", "The acknowledgment arrives today.")]),
    ("plazo de entrega", "noun phrase", "M", "delivery deadline", 1800, "B1", 0.5, "services and work", "SPANISH_BREADTH_PLAN.md B1 services/work topic", [("El plazo de entrega cambia.", "The delivery deadline changes."), ("Pregunto por el plazo de entrega.", "I ask about the delivery deadline.")]),
    ("fecha límite", "noun phrase", "F", "deadline", 1600, "B1", 0.5, "work and bureaucracy", "SPANISH_BREADTH_PLAN.md B1 work/bureaucracy topic", [("La fecha límite es mañana.", "The deadline is tomorrow."), ("Cambio la fecha límite.", "I change the deadline.")]),
    ("lista de espera", "noun phrase", "F", "waiting list", 1700, "B1", 0.5, "medical and services", "SPANISH_BREADTH_PLAN.md B1 health/services topic", [("Estoy en lista de espera.", "I am on the waiting list."), ("La lista de espera es larga.", "The waiting list is long.")]),
    ("número de expediente", "noun phrase", "M", "case number", 2000, "B2", 0.6, "bureaucracy and legal", "SPANISH_BREADTH_PLAN.md B2 bureaucracy/legal topic", [("Necesito el número de expediente.", "I need the case number."), ("El número de expediente está aquí.", "The case number is here.")]),
    ("código postal", "noun phrase", "M", "postal code", 1500, "B1", 0.5, "forms and addresses", "SPANISH_BREADTH_PLAN.md B1 public services topic", [("Escribo el código postal.", "I write the postal code."), ("El código postal falta.", "The postal code is missing.")]),
    ("dirección fiscal", "noun phrase", "F", "tax address", 2200, "B2", 0.6, "taxes and bureaucracy", "SPANISH_BREADTH_PLAN.md B2 money/bureaucracy topic", [("Cambio la dirección fiscal.", "I change the tax address."), ("La dirección fiscal está mal.", "The tax address is wrong.")]),
    ("domicilio actual", "noun phrase", "M", "current address", 2000, "B1", 0.6, "forms and housing", "SPANISH_BREADTH_PLAN.md B1 public services/housing topic", [("Escribo mi domicilio actual.", "I write my current address."), ("Mi domicilio actual cambió.", "My current address changed.")]),
    ("titular de cuenta", "noun phrase", "M", "account holder", 2200, "B2", 0.6, "banking", "SPANISH_BREADTH_PLAN.md B2 banking topic", [("Soy titular de cuenta.", "I am the account holder."), ("El titular de cuenta firma.", "The account holder signs.")]),
    ("justificante de pago", "noun phrase", "M", "proof of payment", 2100, "B1", 0.6, "money and bureaucracy", "SPANISH_BREADTH_PLAN.md B1 money/bureaucracy topic", [("Envío el justificante de pago.", "I send the payment proof."), ("Necesito justificante de pago.", "I need proof of payment.")]),
    ("orden de pago", "noun phrase", "F", "payment order", 2000, "B2", 0.6, "banking", "SPANISH_BREADTH_PLAN.md B2 banking topic", [("Firmo la orden de pago.", "I sign the payment order."), ("La orden de pago falla.", "The payment order fails.")]),
    ("recargo por demora", "noun phrase", "M", "late surcharge", 2300, "B2", 0.6, "money and complaints", "SPANISH_BREADTH_PLAN.md B2 money/complaints topic", [("Cobran recargo por demora.", "They charge a late surcharge."), ("Reclamo el recargo por demora.", "I dispute the late surcharge.")]),
    ("interés de demora", "noun phrase", "M", "late interest", 2400, "B2", 0.6, "banking and legal", "SPANISH_BREADTH_PLAN.md B2 banking/legal topic", [("El interés de demora sube.", "The late interest rises."), ("Pago interés de demora.", "I pay late interest.")]),
    ("impago", "noun", "M", "nonpayment", 2200, "B2", 0.6, "money and legal", "SPANISH_BREADTH_PLAN.md B2 money/legal topic", [("El impago causa problemas.", "Nonpayment causes problems."), ("Evito el impago.", "I avoid nonpayment.")]),
    ("deudor", "noun", "M", "debtor", 2200, "B2", 0.6, "money and legal", "SPANISH_BREADTH_PLAN.md B2 money/legal topic", [("El deudor firma el acuerdo.", "The debtor signs the agreement."), ("Llaman al deudor.", "They call the debtor.")]),
    ("acreedor", "noun", "M", "creditor", 2400, "B2", 0.6, "money and legal", "SPANISH_BREADTH_PLAN.md B2 money/legal topic", [("El acreedor acepta el plan.", "The creditor accepts the plan."), ("Pago al acreedor.", "I pay the creditor.")]),
    ("aval", "noun", "M", "guarantee", 2100, "B2", 0.6, "banking and housing", "SPANISH_BREADTH_PLAN.md B2 banking/housing topic", [("Necesito un aval.", "I need a guarantee."), ("El aval cubre el alquiler.", "The guarantee covers the rent.")]),
    ("garante", "noun", "M", "guarantor", 2400, "B2", 0.6, "banking and housing", "SPANISH_BREADTH_PLAN.md B2 banking/housing topic", [("El garante firma mañana.", "The guarantor signs tomorrow."), ("Necesito un garante.", "I need a guarantor.")]),
    ("horas extra", "noun phrase", "F", "overtime hours", 1900, "B1", 0.5, "work and money", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [("Hago horas extra hoy.", "I work overtime today."), ("Pago las horas extra.", "I pay the overtime hours.")]),
    ("periodo de prueba", "noun phrase", "M", "trial period", 2000, "B1", 0.6, "work", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [("Empiezo el periodo de prueba.", "I start the trial period."), ("El periodo de prueba termina mañana.", "The trial period ends tomorrow.")]),
    ("desempleo", "noun", "M", "unemployment", 1300, "B1", 0.5, "work and public services", "SPANISH_BREADTH_PLAN.md B1 work/public services topic", [("Solicito ayuda por desempleo.", "I apply for unemployment aid."), ("El desempleo me preocupa.", "Unemployment worries me.")]),
    ("sala de espera", "noun phrase", "F", "waiting room", 1600, "B1", 0.5, "medical and services", "SPANISH_BREADTH_PLAN.md B1 medical/services topic", [("Espero en la sala de espera.", "I wait in the waiting room."), ("La sala de espera está llena.", "The waiting room is full.")]),
    ("consulta externa", "noun phrase", "F", "outpatient clinic", 2300, "B2", 0.6, "medical systems", "SPANISH_BREADTH_PLAN.md B2 medical systems topic", [("Voy a consulta externa.", "I go to the outpatient clinic."), ("La consulta externa abre temprano.", "The clinic opens early.")]),
    ("urgencia médica", "noun phrase", "F", "medical emergency", 1500, "B1", 0.5, "medical emergencies", "SPANISH_BREADTH_PLAN.md B1 medical emergencies topic", [("Es una urgencia médica.", "It is a medical emergency."), ("Atienden la urgencia médica.", "They handle the medical emergency.")]),
    ("dolor agudo", "noun phrase", "M", "sharp pain", 1800, "B1", 0.5, "medical symptoms", "SPANISH_BREADTH_PLAN.md B1 medical symptoms topic", [("Siento dolor agudo.", "I feel sharp pain."), ("El dolor agudo empieza ahora.", "The sharp pain starts now.")]),
    ("dolor crónico", "noun phrase", "M", "chronic pain", 1900, "B2", 0.6, "medical symptoms", "SPANISH_BREADTH_PLAN.md B2 medical symptoms topic", [("Tengo dolor crónico.", "I have chronic pain."), ("El dolor crónico empeora.", "The chronic pain worsens.")]),
    ("malestar", "noun", "M", "discomfort; malaise", 1700, "B1", 0.5, "medical symptoms", "SPANISH_BREADTH_PLAN.md B1 medical symptoms topic", [("Siento malestar general.", "I feel general discomfort."), ("El malestar continúa.", "The discomfort continues.")]),
    ("náusea", "noun", "F", "nausea", 2200, "B1", 0.6, "medical symptoms", "SPANISH_BREADTH_PLAN.md B1 medical symptoms topic", [("Tengo náusea.", "I feel nauseous."), ("La náusea aparece después.", "Nausea appears afterward.")]),
    ("tos seca", "noun phrase", "F", "dry cough", 1900, "B1", 0.5, "medical symptoms", "SPANISH_BREADTH_PLAN.md B1 medical symptoms topic", [("Tengo tos seca.", "I have a dry cough."), ("La tos seca molesta.", "The dry cough bothers me.")]),
    ("falta de aire", "noun phrase", "F", "shortness of breath", 2000, "B1", 0.6, "medical symptoms", "SPANISH_BREADTH_PLAN.md B1 medical symptoms topic", [("Tengo falta de aire.", "I have shortness of breath."), ("La falta de aire preocupa.", "Shortness of breath is worrying.")]),
    ("dificultad respiratoria", "noun phrase", "F", "breathing difficulty", 2300, "B2", 0.6, "medical symptoms", "SPANISH_BREADTH_PLAN.md B2 medical symptoms topic", [("Tengo dificultad respiratoria.", "I have breathing difficulty."), ("La dificultad respiratoria es grave.", "The breathing difficulty is serious.")]),
    ("alquiler mensual", "noun phrase", "M", "monthly rent", 1600, "B1", 0.5, "housing and money", "SPANISH_BREADTH_PLAN.md B1 housing/money topic", [("Pago el alquiler mensual.", "I pay the monthly rent."), ("El alquiler mensual sube.", "The monthly rent rises.")]),
    ("seguro de hogar", "noun phrase", "M", "home insurance", 2100, "B1", 0.6, "housing and money", "SPANISH_BREADTH_PLAN.md B1 housing/money topic", [("Tengo seguro de hogar.", "I have home insurance."), ("El seguro de hogar cubre daños.", "Home insurance covers damage.")]),
    ("corte de luz", "noun phrase", "M", "power outage", 1900, "B1", 0.5, "household emergencies", "SPANISH_BREADTH_PLAN.md B1 household emergencies topic", [("Hay un corte de luz.", "There is a power outage."), ("El corte de luz dura horas.", "The power outage lasts hours.")]),
    ("corte de agua", "noun phrase", "M", "water outage", 2000, "B1", 0.6, "household emergencies", "SPANISH_BREADTH_PLAN.md B1 household emergencies topic", [("Hay un corte de agua.", "There is a water outage."), ("Avisan del corte de agua.", "They warn about the water outage.")]),
    ("fuga de gas", "noun phrase", "F", "gas leak", 2200, "B1", 0.6, "household emergencies", "SPANISH_BREADTH_PLAN.md B1 household emergencies topic", [("Hay una fuga de gas.", "There is a gas leak."), ("La fuga de gas es urgente.", "The gas leak is urgent.")]),
    ("llave de repuesto", "noun phrase", "F", "spare key", 2200, "B1", 0.6, "housing", "SPANISH_BREADTH_PLAN.md B1 housing topic", [("Tengo una llave de repuesto.", "I have a spare key."), ("Pierdo la llave de repuesto.", "I lose the spare key.")]),
    ("hora de salida", "noun phrase", "F", "departure time", 1300, "B1", 0.5, "travel", "SPANISH_BREADTH_PLAN.md B1 travel topic", [("Confirmo la hora de salida.", "I confirm the departure time."), ("La hora de salida cambia.", "The departure time changes.")]),
    ("control de seguridad", "noun phrase", "M", "security checkpoint", 1700, "B1", 0.5, "travel", "SPANISH_BREADTH_PLAN.md B1 travel topic", [("Paso el control de seguridad.", "I pass security."), ("El control de seguridad tarda.", "Security takes time.")]),
    ("pérdida de equipaje", "noun phrase", "F", "lost luggage", 2200, "B1", 0.6, "travel disruptions", "SPANISH_BREADTH_PLAN.md B1 travel disruptions topic", [("Denuncio la pérdida de equipaje.", "I report lost luggage."), ("La pérdida de equipaje me preocupa.", "Lost luggage worries me.")]),
    ("salida de emergencia", "noun phrase", "F", "emergency exit", 1700, "B1", 0.5, "travel and emergencies", "SPANISH_BREADTH_PLAN.md B1 travel/emergencies topic", [("Busco la salida de emergencia.", "I look for the emergency exit."), ("La salida de emergencia está cerca.", "The emergency exit is nearby.")]),
])

AI_ACCELERATED_PACK_A2_016 = build_numbered_ai_accelerated_pack(947, 1953, 1956, [
    ("cómo digo", "question chunk", None, "how do I say", 1800, "B1", 0.5, "conversation repair", "SPANISH_BREADTH_PLAN.md B1 listening-friendly repair topic", [("¿Cómo digo esto?", "How do I say this?"), ("¿Cómo digo mi dirección?", "How do I say my address?")]),
    ("cómo se dice", "question chunk", None, "how do you say", 1200, "B1", 0.5, "conversation repair", "SPANISH_BREADTH_PLAN.md B1 pronunciation topic", [("¿Cómo se dice recibo?", "How do you say receipt?"), ("¿Cómo se dice esto?", "How do you say this?")]),
    ("no capto", "sentence chunk", None, "I do not catch", 2100, "B2", 0.6, "listening repair", "SPANISH_BREADTH_PLAN.md B2 conversation repair topic", [("No capto la idea.", "I do not catch the idea."), ("No capto el número.", "I do not catch the number.")]),
    ("no entiendo la palabra", "sentence chunk", None, "I do not understand the word", 1900, "B1", 0.5, "listening repair", "SPANISH_BREADTH_PLAN.md B1 conversation repair topic", [("No entiendo la palabra.", "I do not understand the word."), ("No entiendo la palabra clave.", "I do not understand the key word.")]),
    ("hable claro", "sentence chunk", None, "speak clearly", 1700, "B1", 0.5, "listening repair", "SPANISH_BREADTH_PLAN.md B1 listening repair topic", [("Hable claro, por favor.", "Speak clearly, please."), ("Hable claro al teléfono.", "Speak clearly on the phone.")]),
    ("mande un mensaje", "sentence chunk", None, "send a message", 1600, "B1", 0.5, "phone and services", "SPANISH_BREADTH_PLAN.md B1 phone repair topic", [("Mande un mensaje, por favor.", "Send a message, please."), ("Mande un mensaje al técnico.", "Send a message to the technician.")]),
    ("déjeme pensar", "sentence chunk", None, "let me think", 1600, "B1", 0.5, "conversation repair", "SPANISH_BREADTH_PLAN.md B1 conversation repair topic", [("Déjeme pensar un momento.", "Let me think a moment."), ("Déjeme pensar la respuesta.", "Let me think about the answer.")]),
    ("déjeme verlo", "sentence chunk", None, "let me see it", 1700, "B1", 0.5, "service interaction", "SPANISH_BREADTH_PLAN.md B1 service chunks topic", [("Déjeme verlo, por favor.", "Let me see it, please."), ("Déjeme verlo otra vez.", "Let me see it again.")]),
    ("vuelvo enseguida", "sentence chunk", None, "I will be right back", 1600, "B1", 0.5, "service interaction", "SPANISH_BREADTH_PLAN.md B1 service chunks topic", [("Vuelvo enseguida.", "I will be right back."), ("Vuelvo enseguida con la copia.", "I return soon with the copy.")]),
    ("gracias por avisar", "sentence chunk", None, "thanks for warning", 1600, "B1", 0.5, "conversation repair", "SPANISH_BREADTH_PLAN.md B1 social repair topic", [("Gracias por avisar.", "Thanks for letting me know."), ("Gracias por avisar tan rápido.", "Thanks for warning me so quickly.")]),
    ("gracias por esperar", "sentence chunk", None, "thanks for waiting", 1500, "B1", 0.5, "service interaction", "SPANISH_BREADTH_PLAN.md B1 service chunks topic", [("Gracias por esperar.", "Thanks for waiting."), ("Gracias por esperar aquí.", "Thanks for waiting here.")]),
    ("perdón por molestar", "sentence chunk", None, "sorry to bother", 1700, "B1", 0.5, "conversation repair", "SPANISH_BREADTH_PLAN.md B1 social repair topic", [("Perdón por molestar.", "Sorry to bother you."), ("Perdón por molestar otra vez.", "Sorry to bother you again.")]),
    ("sin problema", "sentence chunk", None, "no problem", 900, "B1", 0.5, "social repair", "SPANISH_BREADTH_PLAN.md B1 conversation chunks topic", [("Sin problema, espero aquí.", "No problem, I wait here."), ("Sin problema, pago mañana.", "No problem, I pay tomorrow.")]),
    ("con permiso", "sentence chunk", None, "excuse me", 1300, "B1", 0.5, "polite interaction", "SPANISH_BREADTH_PLAN.md B1 service chunks topic", [("Con permiso, paso.", "Excuse me, coming through."), ("Con permiso, necesito entrar.", "Excuse me, I need to enter.")]),
    ("por favor avise", "sentence chunk", None, "please notify", 1700, "B1", 0.5, "service interaction", "SPANISH_BREADTH_PLAN.md B1 service chunks topic", [("Por favor avise al médico.", "Please notify the doctor."), ("Por favor avise cuando llegue.", "Please notify me when it arrives.")]),
    ("quedo atento", "sentence chunk", None, "I remain attentive", 2100, "B2", 0.6, "formal messages", "SPANISH_BREADTH_PLAN.md B2 work/bureaucracy topic", [("Quedo atento a su respuesta.", "I await your answer."), ("Quedo atento al correo.", "I will watch for the email.")]),
    ("estoy disponible", "sentence chunk", None, "I am available", 1300, "B1", 0.5, "work and planning", "SPANISH_BREADTH_PLAN.md B1 workplace chunks topic", [("Estoy disponible el lunes.", "I am available on Monday."), ("Estoy disponible por la tarde.", "I am available in the afternoon.")]),
    ("estoy ocupado", "sentence chunk", None, "I am busy", 1100, "B1", 0.5, "work and planning", "SPANISH_BREADTH_PLAN.md B1 workplace chunks topic", [("Estoy ocupado ahora.", "I am busy now."), ("Estoy ocupado con el informe.", "I am busy with the report.")]),
    ("no puedo atender", "sentence chunk", None, "I cannot answer", 1800, "B1", 0.5, "phone and work", "SPANISH_BREADTH_PLAN.md B1 phone repair topic", [("No puedo atender ahora.", "I cannot answer now."), ("No puedo atender la llamada.", "I cannot answer the call.")]),
    ("llámeme luego", "sentence chunk", None, "call me later", 1600, "B1", 0.5, "phone and services", "SPANISH_BREADTH_PLAN.md B1 phone repair topic", [("Llámeme luego, por favor.", "Call me later, please."), ("Llámeme luego al móvil.", "Call me later on my mobile.")]),
    ("avísame cuando puedas", "sentence chunk", None, "let me know when you can", 1900, "B1", 0.5, "conversation repair", "SPANISH_BREADTH_PLAN.md B1 conversation chunks topic", [("Avísame cuando puedas.", "Let me know when you can."), ("Avísame cuando puedas venir.", "Tell me when you can come.")]),
    ("según entiendo", "adverbial phrase", None, "as I understand", 1900, "B2", 0.6, "careful speech", "SPANISH_BREADTH_PLAN.md B2 conversation repair topic", [("Según entiendo, falta una copia.", "As I understand, one copy is missing."), ("Según entiendo, pago después.", "As I understand, I pay later.")]),
    ("según me dicen", "adverbial phrase", None, "as they tell me", 2000, "B2", 0.6, "reported information", "SPANISH_BREADTH_PLAN.md B2 narration topic", [("Según me dicen, hay retraso.", "They tell me there is a delay."), ("Según me dicen, abre mañana.", "They tell me it opens tomorrow.")]),
    ("por lo general", "adverbial phrase", None, "generally", 1300, "B1", 0.5, "frequency and explanation", "SPANISH_BREADTH_PLAN.md B1 discourse markers topic", [("Por lo general, pago con tarjeta.", "Generally, I pay by card."), ("Por lo general, llego temprano.", "Generally, I arrive early.")]),
    ("en concreto", "adverbial phrase", None, "specifically", 1600, "B2", 0.6, "clarification", "SPANISH_BREADTH_PLAN.md B2 discourse markers topic", [("En concreto, necesito el recibo.", "Specifically, I need the receipt."), ("En concreto, hablo del contrato.", "Specifically, I mean the contract.")]),
    ("en parte", "adverbial phrase", None, "partly", 1200, "B1", 0.5, "opinion and nuance", "SPANISH_BREADTH_PLAN.md B1 opinion language topic", [("En parte, estoy de acuerdo.", "Partly, I agree."), ("En parte, el problema sigue.", "Partly, the problem remains.")]),
    ("de todas maneras", "adverbial phrase", None, "anyway", 1400, "B1", 0.5, "discourse markers", "SPANISH_BREADTH_PLAN.md B1 discourse markers topic", [("De todas maneras, llamo mañana.", "Anyway, I call tomorrow."), ("De todas maneras, gracias.", "Anyway, thank you.")]),
    ("a más tardar", "adverbial phrase", None, "at the latest", 1900, "B2", 0.6, "deadlines", "SPANISH_BREADTH_PLAN.md B2 bureaucracy topic", [("Pague a más tardar mañana.", "Pay by tomorrow at the latest."), ("Llega a más tardar el lunes.", "It arrives by Monday at the latest.")]),
    ("fuera de plazo", "adverbial phrase", None, "after the deadline", 2100, "B2", 0.6, "bureaucracy and deadlines", "SPANISH_BREADTH_PLAN.md B2 bureaucracy topic", [("Entrego fuera de plazo.", "I submit it late."), ("El pago llega fuera de plazo.", "The payment arrives late.")]),
    ("bajo petición", "adverbial phrase", None, "upon request", 2300, "B2", 0.6, "bureaucracy and services", "SPANISH_BREADTH_PLAN.md B2 public services topic", [("Envían copia bajo petición.", "They send a copy upon request."), ("El informe sale bajo petición.", "The report is issued upon request.")]),
    ("a nombre de", "prepositional phrase", None, "in the name of", 1700, "B1", 0.5, "forms and money", "SPANISH_BREADTH_PLAN.md B1 forms/money topic", [("La factura está a nombre de Ana.", "The bill is in Ana's name."), ("La cuenta está a nombre de Luis.", "The account is in Luis's name.")]),
    ("a cargo de", "prepositional phrase", None, "in charge of", 1700, "B1", 0.5, "work and responsibility", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [("Estoy a cargo del equipo.", "I am in charge of the team."), ("Ella está a cargo del pago.", "She is in charge of payment.")]),
    ("en nombre de", "prepositional phrase", None, "on behalf of", 1800, "B2", 0.6, "legal and work", "SPANISH_BREADTH_PLAN.md B2 legal/work topic", [("Firmo en nombre de la empresa.", "I sign on behalf of the company."), ("Hablo en nombre de mi madre.", "I speak on behalf of my mother.")]),
    ("de forma urgente", "adverbial phrase", None, "urgently", 1900, "B1", 0.5, "emergencies and services", "SPANISH_BREADTH_PLAN.md B1 service urgency topic", [("Necesito ayuda de forma urgente.", "I need help urgently."), ("Lo solicito de forma urgente.", "I request it urgently.")]),
    ("de forma segura", "adverbial phrase", None, "safely", 1700, "B1", 0.5, "travel and safety", "SPANISH_BREADTH_PLAN.md B1 travel/safety topic", [("Viajo de forma segura.", "I travel safely."), ("Guarde el archivo de forma segura.", "Save the file safely.")]),
    ("mediante transferencia", "adverbial phrase", None, "by bank transfer", 2100, "B2", 0.6, "money and banking", "SPANISH_BREADTH_PLAN.md B2 banking topic", [("Pago el recibo mediante transferencia.", "I pay the bill by bank transfer."), ("Envío dinero mediante transferencia.", "I send money by bank transfer.")]),
    ("pago aplazado", "noun phrase", "M", "deferred payment", 2300, "B2", 0.6, "money and banking", "SPANISH_BREADTH_PLAN.md B2 banking topic", [("Solicito pago aplazado.", "I request deferred payment."), ("El pago aplazado cuesta más.", "Deferred payment costs more.")]),
    ("pago inicial", "noun phrase", "M", "initial payment", 1900, "B1", 0.5, "money and contracts", "SPANISH_BREADTH_PLAN.md B1 money/contracts topic", [("Hago el pago inicial.", "I make the initial payment."), ("El pago inicial vence hoy.", "The initial payment is due today.")]),
    ("saldo pendiente", "noun phrase", "M", "outstanding balance", 1900, "B1", 0.5, "money and banking", "SPANISH_BREADTH_PLAN.md B1 money topic", [("Tengo saldo pendiente.", "I have an outstanding balance."), ("El saldo pendiente baja.", "The outstanding balance goes down.")]),
    ("cobro indebido", "noun phrase", "M", "wrongful charge", 2100, "B2", 0.6, "money and complaints", "SPANISH_BREADTH_PLAN.md B2 money/complaints topic", [("Reclamo el cobro indebido.", "I dispute the wrongful charge."), ("El cobro indebido aparece hoy.", "The wrongful charge appears today.")]),
    ("recibo pendiente", "noun phrase", "M", "pending bill", 1800, "B1", 0.5, "money and bills", "SPANISH_BREADTH_PLAN.md B1 money topic", [("Tengo un recibo pendiente.", "I have a pending bill."), ("El recibo pendiente vence mañana.", "The pending bill is due tomorrow.")]),
    ("aviso de pago", "noun phrase", "M", "payment notice", 1900, "B1", 0.5, "money and bureaucracy", "SPANISH_BREADTH_PLAN.md B1 public services/money topic", [("Recibo un aviso de pago.", "I receive a payment notice."), ("El aviso de pago llega tarde.", "The payment notice arrives late.")]),
    ("límite de crédito", "noun phrase", "M", "credit limit", 2100, "B2", 0.6, "money and banking", "SPANISH_BREADTH_PLAN.md B2 banking topic", [("Suben mi límite de crédito.", "They raise my credit limit."), ("El límite de crédito baja.", "The credit limit goes down.")]),
    ("retirada de efectivo", "noun phrase", "F", "cash withdrawal", 2200, "B2", 0.6, "money and banking", "SPANISH_BREADTH_PLAN.md B2 banking topic", [("Hago una retirada de efectivo.", "I make a cash withdrawal."), ("La retirada de efectivo falla.", "The cash withdrawal fails.")]),
    ("ingreso bancario", "noun phrase", "M", "bank deposit", 2100, "B2", 0.6, "money and banking", "SPANISH_BREADTH_PLAN.md B2 banking topic", [("Hago un ingreso bancario.", "I make a bank deposit."), ("El ingreso bancario tarda.", "The bank deposit takes time.")]),
    ("número de póliza", "noun phrase", "M", "policy number", 2100, "B2", 0.6, "insurance", "SPANISH_BREADTH_PLAN.md B2 insurance topic", [("Busco el número de póliza.", "I look for the policy number."), ("El número de póliza falta.", "The policy number is missing.")]),
    ("historial médico", "noun phrase", "M", "medical history", 1900, "B2", 0.6, "medical systems", "SPANISH_BREADTH_PLAN.md B2 health systems topic", [("Reviso mi historial médico.", "I review my medical history."), ("El historial médico está completo.", "The medical history is complete.")]),
    ("receta médica", "noun phrase", "F", "medical prescription", 1600, "B1", 0.5, "medical systems", "SPANISH_BREADTH_PLAN.md B1 health systems topic", [("Necesito una receta médica.", "I need a prescription."), ("La receta médica vence mañana.", "The prescription expires tomorrow.")]),
    ("parte médico", "noun phrase", "M", "medical note", 2000, "B1", 0.6, "medical and work", "SPANISH_BREADTH_PLAN.md B1 health/work topic", [("Entrego el parte médico.", "I submit the medical note."), ("El parte médico llega hoy.", "The medical note arrives today.")]),
    ("consulta telefónica", "noun phrase", "F", "phone consultation", 1900, "B1", 0.5, "medical and phone", "SPANISH_BREADTH_PLAN.md B1 health/phone topic", [("Tengo consulta telefónica.", "I have a phone consultation."), ("La consulta telefónica empieza ahora.", "The phone consultation starts now.")]),
    ("seguro dental", "noun phrase", "M", "dental insurance", 2100, "B2", 0.6, "medical and insurance", "SPANISH_BREADTH_PLAN.md B2 health/insurance topic", [("Tengo seguro dental.", "I have dental insurance."), ("El seguro dental cubre limpieza.", "Dental insurance covers cleaning.")]),
    ("centro médico", "noun phrase", "M", "medical center", 1500, "B1", 0.5, "medical systems", "SPANISH_BREADTH_PLAN.md B1 health systems topic", [("Voy al centro médico.", "I go to the medical center."), ("El centro médico abre temprano.", "The medical center opens early.")]),
    ("médico de guardia", "noun phrase", "M", "on-call doctor", 2000, "B2", 0.6, "medical emergencies", "SPANISH_BREADTH_PLAN.md B2 health systems topic", [("Llamo al médico de guardia.", "I call the on-call doctor."), ("El médico de guardia llega pronto.", "The on-call doctor arrives soon.")]),
    ("dolor de garganta", "noun phrase", "M", "sore throat", 1500, "B1", 0.5, "medical symptoms", "SPANISH_BREADTH_PLAN.md B1 medical symptoms topic", [("Tengo dolor de garganta.", "I have a sore throat."), ("El dolor de garganta sigue.", "The sore throat continues.")]),
    ("fiebre alta", "noun phrase", "F", "high fever", 1500, "B1", 0.5, "medical symptoms", "SPANISH_BREADTH_PLAN.md B1 medical symptoms topic", [("Tengo fiebre alta.", "I have a high fever."), ("La fiebre alta preocupa.", "The high fever is worrying.")]),
    ("justificante médico", "noun phrase", "M", "medical note", 1900, "B1", 0.5, "medical and work", "SPANISH_BREADTH_PLAN.md B1 health/work topic", [("Pido un justificante médico.", "I request a medical note."), ("El justificante médico llega hoy.", "The medical note arrives today.")]),
    ("dolor muscular", "noun phrase", "M", "muscle pain", 1700, "B1", 0.5, "medical symptoms", "SPANISH_BREADTH_PLAN.md B1 medical symptoms topic", [("Tengo dolor muscular.", "I have muscle pain."), ("El dolor muscular sigue.", "The muscle pain continues.")]),
    ("prueba rápida", "noun phrase", "F", "rapid test", 1800, "B1", 0.5, "medical tests", "SPANISH_BREADTH_PLAN.md B1 medical systems topic", [("Hago una prueba rápida.", "I take a rapid test."), ("La prueba rápida sale negativa.", "The rapid test is negative.")]),
    ("informe clínico", "noun phrase", "M", "clinical report", 2100, "B2", 0.6, "medical systems", "SPANISH_BREADTH_PLAN.md B2 health systems topic", [("Solicito el informe clínico.", "I request the clinical report."), ("El informe clínico está listo.", "The clinical report is ready.")]),
    ("sala de urgencias", "noun phrase", "F", "emergency room", 1700, "B1", 0.5, "medical emergencies", "SPANISH_BREADTH_PLAN.md B1 medical emergencies topic", [("Espero en sala de urgencias.", "I wait in the emergency room."), ("La sala de urgencias está llena.", "The emergency room is full.")]),
    ("servicio urgente", "noun phrase", "M", "urgent service", 1900, "B1", 0.5, "services and emergencies", "SPANISH_BREADTH_PLAN.md B1 service urgency topic", [("Necesito servicio urgente.", "I need urgent service."), ("El servicio urgente cuesta más.", "Urgent service costs more.")]),
    ("número de reserva", "noun phrase", "M", "booking number", 1700, "B1", 0.5, "travel", "SPANISH_BREADTH_PLAN.md B1 travel topic", [("Busco el número de reserva.", "I look for the booking number."), ("El número de reserva falta.", "The booking number is missing.")]),
    ("billete de vuelta", "noun phrase", "M", "return ticket", 1600, "B1", 0.5, "travel", "SPANISH_BREADTH_PLAN.md B1 travel topic", [("Compro billete de vuelta.", "I buy a return ticket."), ("Pierdo el billete de vuelta.", "I lose the return ticket.")]),
    ("retraso del vuelo", "noun phrase", "M", "flight delay", 1900, "B1", 0.5, "travel disruptions", "SPANISH_BREADTH_PLAN.md B1 travel disruptions topic", [("Hay retraso del vuelo.", "There is a flight delay."), ("El retraso del vuelo continúa.", "The flight delay continues.")]),
    ("cambio de andén", "noun phrase", "M", "platform change", 2100, "B1", 0.6, "travel disruptions", "SPANISH_BREADTH_PLAN.md B1 travel disruptions topic", [("Anuncian cambio de andén.", "They announce a platform change."), ("El cambio de andén confunde.", "The platform change is confusing.")]),
    ("conexión perdida", "noun phrase", "F", "missed connection", 2300, "B2", 0.6, "travel disruptions", "SPANISH_BREADTH_PLAN.md B2 travel disruptions topic", [("Tengo una conexión perdida.", "I have a missed connection."), ("La conexión perdida causa retraso.", "The missed connection causes delay.")]),
    ("equipaje facturado", "noun phrase", "M", "checked luggage", 1900, "B1", 0.5, "travel", "SPANISH_BREADTH_PLAN.md B1 travel topic", [("Recojo el equipaje facturado.", "I collect the checked luggage."), ("El equipaje facturado pesa mucho.", "The checked luggage weighs a lot.")]),
    ("seguro de viaje", "noun phrase", "M", "travel insurance", 1800, "B1", 0.5, "travel", "SPANISH_BREADTH_PLAN.md B1 travel topic", [("Compro seguro de viaje.", "I buy travel insurance."), ("El seguro de viaje cubre retrasos.", "Travel insurance covers delays.")]),
    ("permiso de residencia", "noun phrase", "M", "residence permit", 1900, "B2", 0.6, "legal and bureaucracy", "SPANISH_BREADTH_PLAN.md B2 bureaucracy/legal topic", [("Renuevo el permiso de residencia.", "I renew the residence permit."), ("El permiso de residencia vence pronto.", "The residence permit expires soon.")]),
    ("permiso de trabajo", "noun phrase", "M", "work permit", 1800, "B2", 0.6, "legal and work", "SPANISH_BREADTH_PLAN.md B2 bureaucracy/work topic", [("Solicito permiso de trabajo.", "I request a work permit."), ("El permiso de trabajo llega tarde.", "The work permit arrives late.")]),
    ("turno de mañana", "noun phrase", "M", "morning shift", 1500, "B1", 0.5, "work", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [("Trabajo en turno de mañana.", "I work the morning shift."), ("El turno de mañana empieza temprano.", "The morning shift starts early.")]),
    ("turno de noche", "noun phrase", "M", "night shift", 1600, "B1", 0.5, "work", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [("Trabajo en turno de noche.", "I work the night shift."), ("El turno de noche termina tarde.", "The night shift ends late.")]),
    ("nómina mensual", "noun phrase", "F", "monthly payroll", 1900, "B1", 0.5, "work and money", "SPANISH_BREADTH_PLAN.md B1 workplace/money topic", [("Recibo la nómina mensual.", "I receive the monthly payroll."), ("La nómina mensual llega hoy.", "The monthly payroll arrives today.")]),
    ("puesto vacante", "noun phrase", "M", "vacant position", 1900, "B1", 0.5, "work", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [("Hay un puesto vacante.", "There is a vacant position."), ("Solicito el puesto vacante.", "I apply for the vacant position.")]),
    ("entrevista de trabajo", "noun phrase", "F", "job interview", 1600, "B1", 0.5, "work", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [("Tengo entrevista de trabajo.", "I have a job interview."), ("La entrevista de trabajo sale bien.", "The job interview goes well.")]),
    ("oferta de empleo", "noun phrase", "F", "job offer", 1600, "B1", 0.5, "work", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [("Recibo una oferta de empleo.", "I receive a job offer."), ("La oferta de empleo mejora.", "The job offer improves.")]),
    ("horario flexible", "noun phrase", "M", "flexible schedule", 1800, "B1", 0.5, "work", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [("Tengo horario flexible.", "I have a flexible schedule."), ("El horario flexible ayuda.", "The flexible schedule helps.")]),
    ("teletrabajo", "noun", "M", "remote work", 1700, "B1", 0.5, "work", "SPANISH_BREADTH_PLAN.md B1 workplace topic", [("Hago teletrabajo los lunes.", "I work remotely on Mondays."), ("El teletrabajo me conviene.", "Remote work suits me.")]),
    ("convenio colectivo", "noun phrase", "M", "collective agreement", 2200, "B2", 0.6, "work and legal", "SPANISH_BREADTH_PLAN.md B2 workplace/legal topic", [("Reviso el convenio colectivo.", "I review the collective agreement."), ("El convenio colectivo cambia.", "The collective agreement changes.")]),
    ("sindicato", "noun", "M", "union", 1700, "B2", 0.6, "work and legal", "SPANISH_BREADTH_PLAN.md B2 workplace/legal topic", [("Llamo al sindicato.", "I call the union."), ("El sindicato negocia el acuerdo.", "The union negotiates the agreement.")]),
    ("indemnización", "noun", "F", "compensation", 1800, "B2", 0.6, "legal and money", "SPANISH_BREADTH_PLAN.md B2 legal/money topic", [("Solicito una indemnización.", "I request compensation."), ("La indemnización llega tarde.", "The compensation arrives late.")]),
    ("recurso legal", "noun phrase", "M", "legal appeal", 2200, "B2", 0.6, "legal", "SPANISH_BREADTH_PLAN.md B2 legal topic", [("Presento un recurso legal.", "I file a legal appeal."), ("El recurso legal sigue abierto.", "The legal appeal remains open.")]),
    ("denuncia formal", "noun phrase", "F", "formal complaint", 2100, "B2", 0.6, "legal and conflict", "SPANISH_BREADTH_PLAN.md B2 legal/conflict topic", [("Presento una denuncia formal.", "I file a formal complaint."), ("La denuncia formal avanza.", "The formal complaint moves forward.")]),
    ("demanda judicial", "noun phrase", "F", "lawsuit", 2200, "B2", 0.6, "legal", "SPANISH_BREADTH_PLAN.md B2 legal topic", [("Presento una demanda judicial.", "I file a lawsuit."), ("La demanda judicial tarda meses.", "The lawsuit takes months.")]),
    ("antecedentes penales", "noun phrase", "M", "criminal record", 2400, "B2", 0.6, "legal and bureaucracy", "SPANISH_BREADTH_PLAN.md B2 legal/bureaucracy topic", [("Piden antecedentes penales.", "They request a criminal record."), ("No tengo antecedentes penales.", "I have no criminal record.")]),
    ("poder notarial", "noun phrase", "M", "notarial power", 2400, "B2", 0.6, "legal and bureaucracy", "SPANISH_BREADTH_PLAN.md B2 legal/bureaucracy topic", [("Necesito poder notarial.", "I need notarized authorization."), ("El poder notarial vence pronto.", "The notarized authorization expires soon.")]),
    ("copia compulsada", "noun phrase", "F", "certified copy", 2300, "B2", 0.6, "bureaucracy", "SPANISH_BREADTH_PLAN.md B2 bureaucracy topic", [("Entrego una copia compulsada.", "I submit a certified copy."), ("La copia compulsada cuesta cinco euros.", "The certified copy costs five euros.")]),
    ("firma digital", "noun phrase", "F", "digital signature", 1700, "B1", 0.5, "bureaucracy and technology", "SPANISH_BREADTH_PLAN.md B1 public services/technology topic", [("Uso firma digital.", "I use a digital signature."), ("La firma digital no funciona.", "The digital signature does not work.")]),
    ("certificado digital", "noun phrase", "M", "digital certificate", 1700, "B1", 0.5, "bureaucracy and technology", "SPANISH_BREADTH_PLAN.md B1 public services/technology topic", [("Instalo el certificado digital.", "I install the digital certificate."), ("El certificado digital caduca hoy.", "The digital certificate expires today.")]),
    ("cita administrativa", "noun phrase", "F", "administrative appointment", 2100, "B2", 0.6, "bureaucracy", "SPANISH_BREADTH_PLAN.md B2 public services topic", [("Tengo cita administrativa mañana.", "I have an administrative appointment tomorrow."), ("Cambio la cita administrativa.", "I change the administrative appointment.")]),
    ("tasa administrativa", "noun phrase", "F", "administrative fee", 2100, "B2", 0.6, "bureaucracy and money", "SPANISH_BREADTH_PLAN.md B2 public services/money topic", [("Pago la tasa administrativa.", "I pay the administrative fee."), ("La tasa administrativa sube.", "The administrative fee rises.")]),
    ("documento adjunto", "noun phrase", "M", "attached document", 1700, "B1", 0.5, "bureaucracy and technology", "SPANISH_BREADTH_PLAN.md B1 public services/technology topic", [("Reviso el documento adjunto.", "I review the attached document."), ("El documento adjunto no abre.", "The attached document does not open.")]),
    ("copia de seguridad", "noun phrase", "F", "backup copy", 1800, "B1", 0.5, "technology and work", "SPANISH_BREADTH_PLAN.md B1 technology/work topic", [("Hago copia de seguridad.", "I make a backup copy."), ("La copia de seguridad falla.", "The backup copy fails.")]),
    ("pantalla", "noun", "F", "screen", 1000, "B1", 0.5, "technology and listening", "SPANISH_BREADTH_PLAN.md B1 technology topic", [("La pantalla está negra.", "The screen is black."), ("Comparto la pantalla.", "I share the screen.")]),
    ("altavoz", "noun", "M", "speaker", 1700, "B1", 0.5, "listening and technology", "SPANISH_BREADTH_PLAN.md B1 listening technology topic", [("El altavoz no funciona.", "The speaker does not work."), ("Subo el volumen del altavoz.", "I raise the speaker volume.")]),
    ("micrófono", "noun", "M", "microphone", 1600, "B1", 0.5, "listening and technology", "SPANISH_BREADTH_PLAN.md B1 listening technology topic", [("El micrófono está apagado.", "The microphone is off."), ("Activo el micrófono.", "I turn on the microphone.")]),
    ("auriculares", "noun", "M", "headphones", 1800, "B1", 0.5, "listening and technology", "SPANISH_BREADTH_PLAN.md B1 listening technology topic", [("Uso auriculares.", "I use headphones."), ("Mis auriculares no funcionan.", "My headphones do not work.")]),
    ("señal", "noun", "F", "signal", 1200, "B1", 0.5, "phone and travel", "SPANISH_BREADTH_PLAN.md B1 phone/travel topic", [("La señal es débil.", "The signal is weak."), ("Pierdo la señal.", "I lose the signal.")]),
    ("ruido de fondo", "noun phrase", "M", "background noise", 2000, "B1", 0.6, "listening repair", "SPANISH_BREADTH_PLAN.md B1 listening repair topic", [("Hay ruido de fondo.", "There is background noise."), ("El ruido de fondo molesta.", "The background noise bothers me.")]),
    ("mensaje de voz", "noun phrase", "M", "voice message", 1700, "B1", 0.5, "phone and listening", "SPANISH_BREADTH_PLAN.md B1 phone repair topic", [("Dejo un mensaje de voz.", "I leave a voice message."), ("Escucho el mensaje de voz.", "I listen to the voice message.")]),
    ("llamada perdida", "noun phrase", "F", "missed call", 1600, "B1", 0.5, "phone and services", "SPANISH_BREADTH_PLAN.md B1 phone repair topic", [("Tengo una llamada perdida.", "I have a missed call."), ("Devuelvo la llamada perdida.", "I return the missed call.")]),
    ("videollamada", "noun", "F", "video call", 1800, "B1", 0.5, "phone and work", "SPANISH_BREADTH_PLAN.md B1 phone/work topic", [("Tengo una videollamada.", "I have a video call."), ("La videollamada empieza ahora.", "The video call starts now.")]),
    ("taller mecánico", "noun phrase", "M", "repair garage", 1900, "B1", 0.5, "transport and repairs", "SPANISH_BREADTH_PLAN.md B1 transport/repairs topic", [("Llevo el coche al taller mecánico.", "I take the car to the garage."), ("El taller mecánico abre temprano.", "The garage opens early.")]),
    ("pieza de repuesto", "noun phrase", "F", "spare part", 1900, "B1", 0.5, "repairs", "SPANISH_BREADTH_PLAN.md B1 repairs topic", [("Compro una pieza de repuesto.", "I buy a spare part."), ("La pieza de repuesto falta.", "The spare part is missing.")]),
    ("presupuesto previo", "noun phrase", "M", "prior estimate", 2100, "B2", 0.6, "services and money", "SPANISH_BREADTH_PLAN.md B2 services/money topic", [("Pido presupuesto previo.", "I request a prior estimate."), ("El presupuesto previo sube.", "The prior estimate rises.")]),
    ("reparación urgente", "noun phrase", "F", "urgent repair", 1800, "B1", 0.5, "household and services", "SPANISH_BREADTH_PLAN.md B1 repairs topic", [("Necesito reparación urgente.", "I need urgent repair."), ("La reparación urgente cuesta más.", "Urgent repair costs more.")]),
    ("fuga de agua", "noun phrase", "F", "water leak", 1800, "B1", 0.5, "household emergencies", "SPANISH_BREADTH_PLAN.md B1 household emergencies topic", [("Hay una fuga de agua.", "There is a water leak."), ("La fuga de agua continúa.", "The water leak continues.")]),
    ("daño material", "noun phrase", "M", "material damage", 2100, "B2", 0.6, "legal and insurance", "SPANISH_BREADTH_PLAN.md B2 legal/insurance topic", [("Reporto el daño material.", "I report the material damage."), ("El daño material es grave.", "The material damage is serious.")]),
    ("seguro obligatorio", "noun phrase", "M", "mandatory insurance", 2100, "B2", 0.6, "legal and money", "SPANISH_BREADTH_PLAN.md B2 legal/insurance topic", [("Tengo seguro obligatorio.", "I have mandatory insurance."), ("El seguro obligatorio vence pronto.", "Mandatory insurance expires soon.")]),
    ("comunidad de vecinos", "noun phrase", "F", "homeowners association", 2100, "B2", 0.6, "housing and services", "SPANISH_BREADTH_PLAN.md B2 housing topic", [("Llamo a la comunidad de vecinos.", "I call the homeowners association."), ("La comunidad de vecinos se reúne.", "The homeowners association meets.")]),
    ("contrato de alquiler", "noun phrase", "M", "rental contract", 1600, "B1", 0.5, "housing and legal", "SPANISH_BREADTH_PLAN.md B1 housing/legal topic", [("Firmo el contrato de alquiler.", "I sign the rental contract."), ("El contrato de alquiler vence pronto.", "The rental contract expires soon.")]),
    ("gastos incluidos", "noun phrase", "M", "included expenses", 1900, "B1", 0.5, "housing and money", "SPANISH_BREADTH_PLAN.md B1 housing/money topic", [("El alquiler tiene gastos incluidos.", "The rent includes utilities."), ("Busco piso con gastos incluidos.", "I want a flat with utilities included.")]),
    ("recibo de luz", "noun phrase", "M", "electric bill", 1600, "B1", 0.5, "household and money", "SPANISH_BREADTH_PLAN.md B1 household/money topic", [("Pago el recibo de luz.", "I pay the electric bill."), ("El recibo de luz sube.", "The electric bill rises.")]),
    ("lectura del contador", "noun phrase", "F", "meter reading", 2200, "B2", 0.6, "household and services", "SPANISH_BREADTH_PLAN.md B2 household/services topic", [("Envío la lectura del contador.", "I send the meter reading."), ("La lectura del contador falta.", "The meter reading is missing.")]),
    ("avería eléctrica", "noun phrase", "F", "electrical fault", 2000, "B1", 0.6, "household emergencies", "SPANISH_BREADTH_PLAN.md B1 household emergencies topic", [("Hay una avería eléctrica.", "There is an electrical fault."), ("La avería eléctrica sigue.", "The electrical fault continues.")]),
    ("entrega a domicilio", "noun phrase", "F", "home delivery", 1600, "B1", 0.5, "services and shopping", "SPANISH_BREADTH_PLAN.md B1 services/shopping topic", [("Pido entrega a domicilio.", "I request home delivery."), ("La entrega a domicilio tarda.", "Home delivery takes time.")]),
    ("libro de familia", "noun phrase", "M", "family record book", 2200, "B2", 0.6, "bureaucracy and family", "SPANISH_BREADTH_PLAN.md B2 public services topic", [("Presento el libro de familia.", "I submit the family record book."), ("El libro de familia falta.", "The family record book is missing.")]),
    ("padrón municipal", "noun phrase", "M", "municipal register", 2200, "B2", 0.6, "bureaucracy and housing", "SPANISH_BREADTH_PLAN.md B2 public services topic", [("Actualizo el padrón municipal.", "I update the municipal register."), ("El padrón municipal está listo.", "The municipal register is ready.")]),
    ("declaración de renta", "noun phrase", "F", "tax return", 2100, "B2", 0.6, "money and bureaucracy", "SPANISH_BREADTH_PLAN.md B2 taxes topic", [("Presento la declaración de renta.", "I file the tax return."), ("La declaración de renta vence pronto.", "The tax return is due soon.")]),
    ("justicia gratuita", "noun phrase", "F", "free legal aid", 2400, "B2", 0.6, "legal and public services", "SPANISH_BREADTH_PLAN.md B2 legal/public services topic", [("Solicito justicia gratuita.", "I request free legal aid."), ("La justicia gratuita tarda meses.", "Free legal aid takes months.")]),
])

AI_REVIEWED_SENTENCE_PAIRS.update({
    spanish: english
    for pack in (
        AI_ACCELERATED_PACK_A2_003,
        AI_ACCELERATED_PACK_A2_004,
        AI_ACCELERATED_PACK_A2_005,
        AI_ACCELERATED_PACK_A2_006,
        AI_ACCELERATED_PACK_A2_007,
        AI_ACCELERATED_PACK_A2_008,
        AI_ACCELERATED_PACK_A2_009,
        AI_ACCELERATED_PACK_A2_010,
        AI_ACCELERATED_PACK_A2_011,
        AI_ACCELERATED_PACK_A2_012,
        AI_ACCELERATED_PACK_A2_013,
        AI_ACCELERATED_PACK_A2_014,
        AI_ACCELERATED_PACK_A2_015,
        AI_ACCELERATED_PACK_A2_016,
    )
    for item in pack
    for _, _, spanish, english in item["sentences"]
})


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
    {"lemma": "coche", "cefrBand": "A2", "pos": "noun", "priority": 4, "reason": "transport", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 transport topic"},
    {"lemma": "autobús", "cefrBand": "A2", "pos": "noun", "priority": 4, "reason": "transport", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 transport topic"},
    {"lemma": "tienda", "cefrBand": "A2", "pos": "noun", "priority": 4, "reason": "shopping", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 shopping topic"},
    {"lemma": "precio", "cefrBand": "A2", "pos": "noun", "priority": 4, "reason": "shopping details", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 shopping/money topic"},
    {"lemma": "mano", "cefrBand": "A2", "pos": "noun", "priority": 4, "reason": "body and health", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 health/body topic"},
    {"lemma": "cabeza", "cefrBand": "A2", "pos": "noun", "priority": 4, "reason": "body and health", "sourceBasis": "SPANISH_BREADTH_PLAN.md Phase 3 health/body topic"},
    {"lemma": "bueno", "cefrBand": "A2", "pos": "adjective", "priority": 4, "reason": "common description", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine"},
    {"lemma": "malo", "cefrBand": "A2", "pos": "adjective", "priority": 4, "reason": "common description", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine"},
    {"lemma": "rápido", "cefrBand": "A2", "pos": "adjective/adverb", "priority": 4, "reason": "common manner and speed", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine"},
    {"lemma": "grande", "cefrBand": "A2", "pos": "adjective", "priority": 4, "reason": "common size description", "sourceBasis": "hermitdave/FrequencyWords high-frequency spine"},
]
A1_A2_TARGET_LEMMAS.extend([
    {
        "lemma": item["lemma"],
        "cefrBand": item["cefrBand"],
        "pos": item["pos"],
        "priority": 5,
        "reason": item["reason"],
        "sourceBasis": item["sourceBasis"],
    }
    for pack in (
        AI_ACCELERATED_PACK_A2_003,
        AI_ACCELERATED_PACK_A2_004,
        AI_ACCELERATED_PACK_A2_005,
        AI_ACCELERATED_PACK_A2_006,
        AI_ACCELERATED_PACK_A2_007,
        AI_ACCELERATED_PACK_A2_008,
        AI_ACCELERATED_PACK_A2_009,
        AI_ACCELERATED_PACK_A2_010,
        AI_ACCELERATED_PACK_A2_011,
        AI_ACCELERATED_PACK_A2_012,
        AI_ACCELERATED_PACK_A2_013,
        AI_ACCELERATED_PACK_A2_014,
        AI_ACCELERATED_PACK_A2_015,
        AI_ACCELERATED_PACK_A2_016,
    )
    for item in pack
])


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
    reviewEvidence: list[dict] = field(default_factory=list)


def append_ai_accelerated_pack(pack, pack_slug: str, exercise_id: int,
                               lexemes, sentences, accepted, sentence_lexeme, exercises) -> int:
    for item in pack:
        lexeme_id = item["lexemeId"]
        lexemes.append(Row({
            "lexemeId": lexeme_id,
            "lemma": item["lemma"],
            "pos": item["pos"],
            "gender": item["gender"],
            "englishGloss": item["englishGloss"],
            "frequencyRank": item["frequencyRank"],
            "cefrBand": item["cefrBand"],
            "difficultyPrior": item["difficultyPrior"],
        }, source="wiktionary", sourceId=item["lemma"], license="CC-BY-SA-3.0"))

        sentence_ids = []
        for sentence_id, accepted_id, spanish, english in item["sentences"]:
            sentence_ids.append(sentence_id)
            sentences.append(Row({
                "sentenceId": sentence_id,
                "spanishText": spanish,
                "englishText": english,
            }, source=AI_DRAFT_SOURCE,
                sourceId=f"ai_draft:{pack_slug}-{item['lemma']}-{len(sentence_ids)}",
                license="proprietary", vettingStatus=AI_DRAFT))
            accepted.append(Row({
                "acceptedAnswerId": accepted_id,
                "sentenceId": sentence_id,
                "direction": "ES_TO_EN",
                "answerText": normalize_answer(english),
            }, source=AI_DRAFT_SOURCE,
                sourceId=f"ai_draft:{pack_slug}-{item['lemma']}-{len(sentence_ids)}-answer",
                license="proprietary", vettingStatus=AI_DRAFT))
            sentence_lexeme.append((sentence_id, lexeme_id))

        exercises.append({"exerciseId": exercise_id, "nodeId": 1, "sentenceId": sentence_ids[0],
                          "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
                          "targetItemId": lexeme_id, "targetItemType": "LEXEME", "promptHint": None})
        exercise_id += 1
        exercises.append({"exerciseId": exercise_id, "nodeId": 1, "sentenceId": sentence_ids[1],
                          "type": "WORD_BANK", "direction": "ES_TO_EN",
                          "targetItemId": lexeme_id, "targetItemType": "LEXEME", "promptHint": None})
        exercise_id += 1
    return exercise_id


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
        Row({"lexemeId": 32, "lemma": "coche", "pos": "noun", "gender": "M",
             "englishGloss": "car", "frequencyRank": 408, "cefrBand": "A2", "difficultyPrior": 0.4},
            source="wiktionary", sourceId="coche", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 33, "lemma": "autobús", "pos": "noun", "gender": "M",
             "englishGloss": "bus", "frequencyRank": 1702, "cefrBand": "A2", "difficultyPrior": 0.5},
            source="wiktionary", sourceId="autobús", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 34, "lemma": "tienda", "pos": "noun", "gender": "F",
             "englishGloss": "store; shop", "frequencyRank": 817, "cefrBand": "A2", "difficultyPrior": 0.4},
            source="wiktionary", sourceId="tienda", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 35, "lemma": "precio", "pos": "noun", "gender": "M",
             "englishGloss": "price", "frequencyRank": 1230, "cefrBand": "A2", "difficultyPrior": 0.5},
            source="wiktionary", sourceId="precio", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 36, "lemma": "mano", "pos": "noun", "gender": "F",
             "englishGloss": "hand", "frequencyRank": 373, "cefrBand": "A2", "difficultyPrior": 0.4},
            source="wiktionary", sourceId="mano", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 37, "lemma": "cabeza", "pos": "noun", "gender": "F",
             "englishGloss": "head", "frequencyRank": 274, "cefrBand": "A2", "difficultyPrior": 0.4},
            source="wiktionary", sourceId="cabeza", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 38, "lemma": "bueno", "pos": "adjective", "gender": None,
             "englishGloss": "good", "frequencyRank": 50, "cefrBand": "A2", "difficultyPrior": 0.3},
            source="wiktionary", sourceId="bueno", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 39, "lemma": "malo", "pos": "adjective", "gender": None,
             "englishGloss": "bad", "frequencyRank": 476, "cefrBand": "A2", "difficultyPrior": 0.4},
            source="wiktionary", sourceId="malo", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 40, "lemma": "rápido", "pos": "adjective/adverb", "gender": None,
             "englishGloss": "quick; fast", "frequencyRank": 311, "cefrBand": "A2", "difficultyPrior": 0.4},
            source="wiktionary", sourceId="rápido", license="CC-BY-SA-3.0"),
        Row({"lexemeId": 41, "lemma": "grande", "pos": "adjective", "gender": None,
             "englishGloss": "big; large", "frequencyRank": 398, "cefrBand": "A2", "difficultyPrior": 0.4},
            source="wiktionary", sourceId="grande", license="CC-BY-SA-3.0"),
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
        Row({"sentenceId": 101, "spanishText": "¿Tienes coche?", "englishText": "Do you have a car?"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-coche-1", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"sentenceId": 102, "spanishText": "Quiero un coche.", "englishText": "I want a car."},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-coche-2", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"sentenceId": 103, "spanishText": "Vayamos en autobús.", "englishText": "Let's go by bus."},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-autobus-1", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"sentenceId": 104, "spanishText": "Ella viajó en autobús.", "englishText": "She traveled by bus."},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-autobus-2", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"sentenceId": 105, "spanishText": "Odio esta tienda.", "englishText": "I hate this store."},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-tienda-1", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"sentenceId": 106, "spanishText": "Cerraron la tienda.", "englishText": "They closed the shop."},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-tienda-2", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"sentenceId": 107, "spanishText": "Mira el precio.", "englishText": "Look at the price."},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-precio-1", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"sentenceId": 108, "spanishText": "El precio subió.", "englishText": "The price rose."},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-precio-2", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"sentenceId": 109, "spanishText": "Lavémonos las manos.", "englishText": "Let's wash our hands."},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-mano-1", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"sentenceId": 110, "spanishText": "Toma mi mano.", "englishText": "Take my hand."},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-mano-2", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"sentenceId": 111, "spanishText": "¡Usa la cabeza!", "englishText": "Use your head!"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-cabeza-1", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"sentenceId": 112, "spanishText": "Me duele la cabeza.", "englishText": "My head hurts."},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-cabeza-2", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"sentenceId": 113, "spanishText": "¿Es malo?", "englishText": "Is it bad?"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-malo-1", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"sentenceId": 114, "spanishText": "Son malos.", "englishText": "They're bad."},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-malo-2", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"sentenceId": 115, "spanishText": "¡Rápido!", "englishText": "Quick!"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-rapido-1", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"sentenceId": 116, "spanishText": "Comí rápido.", "englishText": "I ate quickly."},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-rapido-2", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"sentenceId": 117, "spanishText": "Es grande.", "englishText": "It's big."},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-grande-1", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"sentenceId": 118, "spanishText": "¿Son grandes?", "englishText": "Are they big?"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-grande-2", license="proprietary",
            vettingStatus=AI_DRAFT),
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
        Row({"acceptedAnswerId": 104, "sentenceId": 101, "direction": "ES_TO_EN", "answerText": "do you have a car"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-coche-1-answer", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"acceptedAnswerId": 105, "sentenceId": 102, "direction": "ES_TO_EN", "answerText": "i want a car"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-coche-2-answer", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"acceptedAnswerId": 106, "sentenceId": 103, "direction": "ES_TO_EN", "answerText": "let's go by bus"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-autobus-1-answer", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"acceptedAnswerId": 107, "sentenceId": 104, "direction": "ES_TO_EN", "answerText": "she traveled by bus"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-autobus-2-answer", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"acceptedAnswerId": 108, "sentenceId": 105, "direction": "ES_TO_EN", "answerText": "i hate this store"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-tienda-1-answer", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"acceptedAnswerId": 109, "sentenceId": 106, "direction": "ES_TO_EN", "answerText": "they closed the shop"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-tienda-2-answer", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"acceptedAnswerId": 110, "sentenceId": 107, "direction": "ES_TO_EN", "answerText": "look at the price"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-precio-1-answer", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"acceptedAnswerId": 111, "sentenceId": 108, "direction": "ES_TO_EN", "answerText": "the price rose"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-precio-2-answer", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"acceptedAnswerId": 112, "sentenceId": 109, "direction": "ES_TO_EN", "answerText": "let's wash our hands"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-mano-1-answer", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"acceptedAnswerId": 113, "sentenceId": 110, "direction": "ES_TO_EN", "answerText": "take my hand"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-mano-2-answer", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"acceptedAnswerId": 114, "sentenceId": 111, "direction": "ES_TO_EN", "answerText": "use your head"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-cabeza-1-answer", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"acceptedAnswerId": 115, "sentenceId": 112, "direction": "ES_TO_EN", "answerText": "my head hurts"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-cabeza-2-answer", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"acceptedAnswerId": 116, "sentenceId": 113, "direction": "ES_TO_EN", "answerText": "is it bad"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-malo-1-answer", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"acceptedAnswerId": 117, "sentenceId": 114, "direction": "ES_TO_EN", "answerText": "they're bad"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-malo-2-answer", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"acceptedAnswerId": 118, "sentenceId": 115, "direction": "ES_TO_EN", "answerText": "quick"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-rapido-1-answer", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"acceptedAnswerId": 119, "sentenceId": 116, "direction": "ES_TO_EN", "answerText": "i ate quickly"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-rapido-2-answer", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"acceptedAnswerId": 120, "sentenceId": 117, "direction": "ES_TO_EN", "answerText": "it's big"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-grande-1-answer", license="proprietary",
            vettingStatus=AI_DRAFT),
        Row({"acceptedAnswerId": 121, "sentenceId": 118, "direction": "ES_TO_EN", "answerText": "are they big"},
            source=AI_DRAFT_SOURCE, sourceId="ai_draft:a2-002-grande-2-answer", license="proprietary",
            vettingStatus=AI_DRAFT),
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
        (101, 32), (101, 1),
        (102, 32), (102, 7),
        (103, 33),
        (104, 33), (104, 31),
        (105, 34),
        (106, 34),
        (107, 35),
        (108, 35),
        (109, 36),
        (110, 36),
        (111, 37),
        (112, 37),
        (40, 38),
        (59, 38),
        (60, 38),
        (113, 39), (113, 4),
        (114, 39),
        (115, 40),
        (116, 40), (116, 15),
        (117, 41), (117, 4),
        (118, 41),
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
        {"exerciseId": 63, "nodeId": 1, "sentenceId": 101, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 32, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 64, "nodeId": 1, "sentenceId": 102, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 32, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 65, "nodeId": 1, "sentenceId": 103, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 33, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 66, "nodeId": 1, "sentenceId": 104, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 33, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 67, "nodeId": 1, "sentenceId": 105, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 34, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 68, "nodeId": 1, "sentenceId": 106, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 34, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 69, "nodeId": 1, "sentenceId": 107, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 35, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 70, "nodeId": 1, "sentenceId": 108, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 35, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 71, "nodeId": 1, "sentenceId": 109, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 36, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 72, "nodeId": 1, "sentenceId": 110, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 36, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 73, "nodeId": 1, "sentenceId": 111, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 37, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 74, "nodeId": 1, "sentenceId": 112, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 37, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 75, "nodeId": 1, "sentenceId": 40, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 38, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 76, "nodeId": 1, "sentenceId": 59, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 38, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 77, "nodeId": 1, "sentenceId": 113, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 39, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 78, "nodeId": 1, "sentenceId": 114, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 39, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 79, "nodeId": 1, "sentenceId": 115, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 40, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 80, "nodeId": 1, "sentenceId": 116, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 40, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 81, "nodeId": 1, "sentenceId": 117, "type": "TYPED_TRANSLATION", "direction": "ES_TO_EN",
         "targetItemId": 41, "targetItemType": "LEXEME", "promptHint": None},
        {"exerciseId": 82, "nodeId": 1, "sentenceId": 118, "type": "WORD_BANK", "direction": "ES_TO_EN",
         "targetItemId": 41, "targetItemType": "LEXEME", "promptHint": None},
    ]
    next_exercise_id = append_ai_accelerated_pack(
        AI_ACCELERATED_PACK_A2_003, "a2-003", 83,
        lexemes, sentences, accepted, sentence_lexeme, exercises,
    )
    next_exercise_id = append_ai_accelerated_pack(
        AI_ACCELERATED_PACK_A2_004, "a2-004", next_exercise_id,
        lexemes, sentences, accepted, sentence_lexeme, exercises,
    )
    next_exercise_id = append_ai_accelerated_pack(
        AI_ACCELERATED_PACK_A2_005, "a2-005", next_exercise_id,
        lexemes, sentences, accepted, sentence_lexeme, exercises,
    )
    next_exercise_id = append_ai_accelerated_pack(
        AI_ACCELERATED_PACK_A2_006, "a2-006", next_exercise_id,
        lexemes, sentences, accepted, sentence_lexeme, exercises,
    )
    next_exercise_id = append_ai_accelerated_pack(
        AI_ACCELERATED_PACK_A2_007, "a2-007", next_exercise_id,
        lexemes, sentences, accepted, sentence_lexeme, exercises,
    )
    next_exercise_id = append_ai_accelerated_pack(
        AI_ACCELERATED_PACK_A2_008, "a2-008", next_exercise_id,
        lexemes, sentences, accepted, sentence_lexeme, exercises,
    )
    next_exercise_id = append_ai_accelerated_pack(
        AI_ACCELERATED_PACK_A2_009, "a2-009", next_exercise_id,
        lexemes, sentences, accepted, sentence_lexeme, exercises,
    )
    next_exercise_id = append_ai_accelerated_pack(
        AI_ACCELERATED_PACK_A2_010, "a2-010", next_exercise_id,
        lexemes, sentences, accepted, sentence_lexeme, exercises,
    )
    next_exercise_id = append_ai_accelerated_pack(
        AI_ACCELERATED_PACK_A2_011, "a2-011", next_exercise_id,
        lexemes, sentences, accepted, sentence_lexeme, exercises,
    )
    next_exercise_id = append_ai_accelerated_pack(
        AI_ACCELERATED_PACK_A2_012, "a2-012", next_exercise_id,
        lexemes, sentences, accepted, sentence_lexeme, exercises,
    )
    next_exercise_id = append_ai_accelerated_pack(
        AI_ACCELERATED_PACK_A2_013, "a2-013", next_exercise_id,
        lexemes, sentences, accepted, sentence_lexeme, exercises,
    )
    next_exercise_id = append_ai_accelerated_pack(
        AI_ACCELERATED_PACK_A2_014, "a2-014", next_exercise_id,
        lexemes, sentences, accepted, sentence_lexeme, exercises,
    )
    next_exercise_id = append_ai_accelerated_pack(
        AI_ACCELERATED_PACK_A2_015, "a2-015", next_exercise_id,
        lexemes, sentences, accepted, sentence_lexeme, exercises,
    )
    append_ai_accelerated_pack(
        AI_ACCELERATED_PACK_A2_016, "a2-016", next_exercise_id,
        lexemes, sentences, accepted, sentence_lexeme, exercises,
    )
    return lexemes, sentences, accepted, sentence_lexeme, conj, exercises, nodes


# --------------------------------------------------------------------------------------
# Pipeline stages
# --------------------------------------------------------------------------------------
def normalize_answer(text: str) -> str:
    return re.sub(r"[^a-z0-9']+", " ", text.lower()).strip()


def add_review_evidence(row: Row, review_type: str, decision: str, notes: str) -> None:
    row.reviewEvidence.append({
        "reviewType": review_type,
        "reviewer": AUTO_REVIEW_REVIEWERS[review_type],
        "reviewedAt": AUTO_REVIEW_TS,
        "decision": decision,
        "notes": notes,
    })


def required_auto_review_types(row: Row) -> set[str]:
    if row.source != AI_DRAFT_SOURCE:
        return set()
    return {AUTO_REVIEW_SPANISH, AUTO_REVIEW_PEDAGOGY}


def approved_auto_review_types(row: Row) -> set[str]:
    return {
        evidence["reviewType"]
        for evidence in row.reviewEvidence
        if evidence.get("decision") == "APPROVED"
    }


def has_required_auto_reviews(row: Row) -> bool:
    required = required_auto_review_types(row)
    if not required:
        return True
    approved = approved_auto_review_types(row)
    reviewers = {
        evidence.get("reviewer")
        for evidence in row.reviewEvidence
        if evidence.get("decision") == "APPROVED" and evidence.get("reviewType") in required
    }
    return required.issubset(approved) and len(reviewers) >= len(required)


def local_spanish_review(row: Row, sentence_by_id: dict[int, Row]) -> tuple[bool, str]:
    sentence = row
    if "sentenceId" in row.data and "spanishText" not in row.data:
        sentence = sentence_by_id.get(row.data["sentenceId"])
    if sentence is None:
        return False, "missing linked Spanish sentence"
    spanish = sentence.data["spanishText"]
    expected_english = AI_REVIEWED_SENTENCE_PAIRS.get(spanish)
    if expected_english is None:
        return False, "Spanish sentence is not in the local approved pattern ledger"
    if not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ¿¡]", spanish):
        return False, "Spanish sentence has no Spanish alphabetic content"
    return True, "Spanish sentence matches local correctness/naturalness ledger"


def local_english_pedagogy_review(row: Row, sentence_by_id: dict[int, Row]) -> tuple[bool, str]:
    if "spanishText" in row.data:
        expected_english = AI_REVIEWED_SENTENCE_PAIRS.get(row.data["spanishText"])
        if expected_english != row.data["englishText"]:
            return False, "English sentence does not match local translation ledger"
        if len(row.data["englishText"].split()) > 8:
            return False, "English sentence is too long for this A1/A2 pack"
        return True, "English translation is ledger-matched and CEFR-appropriate"

    sentence = sentence_by_id.get(row.data["sentenceId"])
    if sentence is None:
        return False, "missing linked sentence for accepted answer"
    expected_english = AI_REVIEWED_SENTENCE_PAIRS.get(sentence.data["spanishText"])
    if normalize_answer(row.data["answerText"]) != normalize_answer(expected_english or ""):
        return False, "accepted answer does not match local translation ledger"
    return True, "accepted answer matches local translation ledger"


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
        if s.vettingStatus == AI_DRAFT:
            expected_english = AI_REVIEWED_SENTENCE_PAIRS.get(s.data["spanishText"])
            if expected_english != s.data["englishText"]:
                failures.append(f"AI_DRAFT sentence {s.data['sentenceId']} failed local translation ledger")

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
        if r.vettingStatus == AI_DRAFT and r.source != AI_DRAFT_SOURCE:
            failures.append(f"AI_DRAFT row {r.data} must use source={AI_DRAFT_SOURCE}")
        if r.vettingStatus in {UNVETTED, AI_DRAFT} and not failures:
            r.vettingStatus = AUTO_CHECKED

    if not failures:
        for r in lexemes + sentences + accepted:
            if r.vettingStatus in {UNVETTED, AI_DRAFT}:
                r.vettingStatus = AUTO_CHECKED
    return failures


def stage_auto_review(lexemes, sentences, accepted) -> list[str]:
    """Stage 4a: locally review AI_DRAFT rows with two independent automatic reviewers."""
    failures: list[str] = []
    sentence_by_id = {s.data["sentenceId"]: s for s in sentences}
    for row in sentences + accepted:
        if row.source != AI_DRAFT_SOURCE or row.vettingStatus != AUTO_CHECKED:
            continue
        spanish_ok, spanish_notes = local_spanish_review(row, sentence_by_id)
        add_review_evidence(row, AUTO_REVIEW_SPANISH, "APPROVED" if spanish_ok else "REJECTED", spanish_notes)
        pedagogy_ok, pedagogy_notes = local_english_pedagogy_review(row, sentence_by_id)
        add_review_evidence(row, AUTO_REVIEW_PEDAGOGY, "APPROVED" if pedagogy_ok else "REJECTED", pedagogy_notes)
        if spanish_ok and pedagogy_ok:
            row.vettingStatus = AUTO_REVIEWED
            row.reviewedBy = "+".join(AUTO_REVIEW_REVIEWERS[t] for t in sorted(required_auto_review_types(row)))
            row.reviewedAt = AUTO_REVIEW_TS
        else:
            failures.append(f"AI_DRAFT row {row.data} failed automatic review")
    return failures


def stage_review_gate(lexemes, sentences, accepted) -> None:
    """Stage 4b REVIEW GATE: source rows use the recorded sample sign-off; AI_DRAFT rows
    must already have both independent automatic approvals before promotion to REVIEWED."""
    REVIEWER = "wolfgang"
    REVIEW_TS = AUTO_REVIEW_TS  # fixed for determinism in the spike
    for r in lexemes + sentences + accepted:
        if r.source == AI_DRAFT_SOURCE and r.vettingStatus == AUTO_REVIEWED and has_required_auto_reviews(r):
            r.vettingStatus = REVIEWED
        elif r.vettingStatus == AUTO_CHECKED:
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
            if r.source == AI_DRAFT_SOURCE and not has_required_auto_reviews(r):
                violations.append(f"{table} row {r.data} lacks both independent automatic approvals")
    if violations:
        sys.stderr.write("CONTENT VETTING GATE FAILED (C5/§4.6/AC17):\n  " + "\n  ".join(violations) + "\n")
        raise SystemExit(2)


def attribution_rows(lexemes):
    rows = set()
    if any(r.data.get("frequencyRank") for r in lexemes):
        rows.add((FREQUENCY_ATTRIBUTION["source"], FREQUENCY_ATTRIBUTION["license"]))
    return sorted(rows)


def enforce_attribution_requirements(lexemes) -> None:
    required = {(FREQUENCY_ATTRIBUTION["source"], FREQUENCY_ATTRIBUTION["license"])}
    present = set(attribution_rows(lexemes))
    missing = sorted(required - present)
    if missing:
        failures = [f"{source} {license}" for source, license in missing]
        sys.stderr.write("ATTRIBUTION GATE FAILED:\n  missing " + "\n  missing ".join(failures) + "\n")
        raise SystemExit(5)


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
    cur.executemany("INSERT INTO content_attribution VALUES (?,?)", attribution_rows(lexemes))
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
    review_ledger = []
    for table, r in rows:
        by_status[r.vettingStatus] = by_status.get(r.vettingStatus, 0) + 1
        by_source[r.source] = by_source.get(r.source, 0) + 1
        if r.source == "authored":
            authored.append({"table": table, "id": next(iter(r.data.values())),
                             "vettingStatus": r.vettingStatus, "reviewedBy": r.reviewedBy})
        if r.source == AI_DRAFT_SOURCE:
            review_ledger.append({
                "table": table,
                "id": next(iter(r.data.values())),
                "sourceId": r.sourceId,
                "vettingStatus": r.vettingStatus,
                "reviewedBy": r.reviewedBy,
                "reviewEvidence": r.reviewEvidence,
            })
    manifest = {"schemaVersion": SCHEMA_VERSION, "totalContentRows": len(rows),
                "byVettingStatus": by_status, "bySource": by_source,
                "authoredRows": authored, "autoReviewLedger": review_ledger,
                "additionalAttributions": [
                    {"source": source, "license": license}
                    for source, license in attribution_rows(lexemes)
                ]}
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


def valid_lexeme_exercise(e: dict, lexeme_id: int, sentence_by_id: dict[int, Row],
                          sentence_ids_by_lexeme: dict[int, set[int]]) -> bool:
    """Only count exercises whose prompt sentence is reviewed and actually contains the target lexeme."""
    if e["targetItemType"] != "LEXEME" or e["targetItemId"] != lexeme_id:
        return False
    sentence_id = e["sentenceId"]
    sentence = sentence_by_id.get(sentence_id)
    return (
        sentence is not None
        and reviewed(sentence)
        and sentence_id in sentence_ids_by_lexeme.get(lexeme_id, set())
    )


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
        valid_target_exercises = [
            e for e in target_exercises
            if valid_lexeme_exercise(e, lexeme_id, sentence_by_id, sentence_ids_by_lexeme)
        ]
        exercise_kinds = sorted({exercise_kind(e["type"]) for e in valid_target_exercises})
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
            "validTargetExerciseCount": len(valid_target_exercises),
            "invalidTargetExerciseCount": len(target_exercises) - len(valid_target_exercises),
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
            "exerciseContextRequired": (
                "LEXEME exercises count only when their sentenceId exists, is REVIEWED, "
                "and is linked to the target lexeme."
            ),
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
    ap.add_argument("--inject-ai-draft-reviewed", action="store_true",
                    help="inject a locally auto-reviewed AI_DRAFT sentence pair; gate should allow it")
    ap.add_argument("--inject-ai-draft-single-review", action="store_true",
                    help="inject a REVIEWED AI_DRAFT row with only one approval; publish gate must reject it")
    ap.add_argument("--inject-malformed-exercise", action="store_true",
                    help="corrupt one critical LEXEME exercise to prove coverage readiness ignores malformed exercises")
    ap.add_argument("--fail-on-coverage-gaps", action="store_true",
                    help="exit non-zero if reviewed A1/A2 rows are not learner-ready")
    ap.add_argument("--baseline-snapshot", default=DEFAULT_BASELINE_SNAPSHOT_PATH,
                    help="reviewable compact coverage snapshot path")
    args = ap.parse_args()
    if args.inject_malformed_exercise and not args.fail_on_coverage_gaps:
        ap.error("--inject-malformed-exercise requires --fail-on-coverage-gaps")

    lexemes, sentences, accepted, sentence_lexeme, conj, exercises, nodes = vetted_sample()
    if args.inject_ai_draft_reviewed:
        sentences.append(Row({"sentenceId": 9991, "spanishText": "Necesito ayuda.", "englishText": "I need help."},
                             source=AI_DRAFT_SOURCE, sourceId="ai_draft:fixture-reviewed-sentence",
                             license="proprietary", vettingStatus=AI_DRAFT))
        accepted.append(Row({"acceptedAnswerId": 9991, "sentenceId": 9991, "direction": "ES_TO_EN",
                             "answerText": "i need help"},
                            source=AI_DRAFT_SOURCE, sourceId="ai_draft:fixture-reviewed-answer",
                            license="proprietary", vettingStatus=AI_DRAFT))

    # Stage 3: auto-check
    failures = stage_auto_check(lexemes, sentences, accepted)
    if failures:
        sys.stderr.write("AUTO-CHECK FAILED:\n  " + "\n  ".join(failures) + "\n")
        raise SystemExit(3)

    # Stage 4: independent review gate
    failures = stage_auto_review(lexemes, sentences, accepted)
    if failures:
        sys.stderr.write("AUTO-REVIEW FAILED:\n  " + "\n  ".join(failures) + "\n")
        raise SystemExit(3)
    stage_review_gate(lexemes, sentences, accepted)

    if args.inject_unvetted:
        # simulate an un-reviewed (e.g. LLM-drafted, never human-reviewed) row sneaking in
        accepted.append(Row({"acceptedAnswerId": 99, "sentenceId": 1,
                             "direction": "ES_TO_EN", "answerText": "i own a dog"},
                            source="authored", sourceId="llm:draft", license="proprietary",
                            vettingStatus=UNVETTED))
    if args.inject_ai_draft_single_review:
        evidence = [{
            "reviewType": AUTO_REVIEW_SPANISH,
            "reviewer": AUTO_REVIEW_REVIEWERS[AUTO_REVIEW_SPANISH],
            "reviewedAt": AUTO_REVIEW_TS,
            "decision": "APPROVED",
            "notes": "fixture intentionally missing English/pedagogy review",
        }]
        accepted.append(Row({"acceptedAnswerId": 9992, "sentenceId": 1,
                             "direction": "ES_TO_EN", "answerText": "i have a dog"},
                            source=AI_DRAFT_SOURCE, sourceId="ai_draft:fixture-single-review",
                            license="proprietary", vettingStatus=REVIEWED,
                            reviewedBy=AUTO_REVIEW_REVIEWERS[AUTO_REVIEW_SPANISH],
                            reviewedAt=AUTO_REVIEW_TS, reviewEvidence=evidence))
    if args.inject_malformed_exercise:
        # Regression fixture: these used to count as valid coverage for viajar solely because
        # the exercise target was lexeme 31. They must not count when the sentence is unlinked
        # to the target lexeme or dangling.
        exercises = [
            {**e, "sentenceId": 1} if e["exerciseId"] == 61 else
            {**e, "sentenceId": 999999} if e["exerciseId"] == 62 else e
            for e in exercises
        ]

    # Stage 5: publish gate (AC17) — raises SystemExit(2) if anything is unvetted/sourceless
    stage_publish_gate(lexemes, sentences, accepted)
    enforce_attribution_requirements(lexemes)

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

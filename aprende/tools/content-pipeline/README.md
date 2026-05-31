# Content pipeline (P0.3)

Dev-time tool that builds the read-only `content.db` SQLite asset the app ships via Room
`createFromAsset`. It is the **only** path learning content takes into `content.db`, and it
mechanically enforces the C5 / SPEC §4.6 content-vetting requirement: nothing sourceless,
raw-generated, or un-reviewed ships.

```bash
# Build from the vetted sample (writes generated content.db + reports next to
# the DB, and updates the committed review baseline snapshot):
python3 build_content_db.py --out ../../app/src/main/assets/database/content.db

# Demo the publish gate REJECTING un-reviewed content (non-zero exit — proves AC17):
python3 build_content_db.py --out /tmp/content.db --inject-unvetted

# Demo AI_DRAFT content that passes deterministic checks and both automatic reviewers:
python3 build_content_db.py --out /tmp/content.db --inject-ai-draft-reviewed \
  --baseline-snapshot /tmp/coverage-ai-reviewed.json

# Demo the publish gate rejecting a partially reviewed AI_DRAFT row:
python3 build_content_db.py --out /tmp/content.db --inject-ai-draft-single-review

# Demo the breadth gate surfacing current A1/A2 readiness gaps (non-zero until
# current A1/A2 lexemes meet the learner-ready budget):
python3 build_content_db.py --out /tmp/content.db --fail-on-coverage-gaps

# Regression fixture: malformed LEXEME exercises must not count as readiness coverage.
# Uses a throwaway baseline path so the committed snapshot is not overwritten by the failing run.
python3 build_content_db.py --out /tmp/content.db --inject-malformed-exercise \
  --fail-on-coverage-gaps --baseline-snapshot /tmp/coverage-malformed.json
```

## 5-stage vetting workflow

Every content row flows through these stages; `vettingStatus` is promoted at each step and
only `REVIEWED` rows are allowed to ship.

1. **Ingest** — rows originate from explicit, licensed sources (e.g. Tatoeba sentence pairs,
   a frequency list, Wiktionary glosses) or from the generated-content lane as `AI_DRAFT`.
   Each row carries provenance from the moment it enters. Sourced rows start `UNVETTED`;
   generated rows start `AI_DRAFT` and use `source=ai_draft`.
2. **Derive** — structural/derived rows are built (sentence↔lexeme joins, the
   conjugation→lemma map, generated exercises). These carry `source`/`license` where
   meaningful.
3. **Auto-check** — automated validation: every sentence has ≥1 accepted answer, accepted
   answers reference a real sentence and are normalized (trimmed/lowercased), every row has a
   license, and `AI_DRAFT` sentence pairs match the local linguistic validation ledger.
   Passing rows are promoted `UNVETTED|AI_DRAFT → AUTO_CHECKED`. Failures abort the build
   (exit 3).
4. **Independent review** — sourced rows use the recorded sample sign-off. `AI_DRAFT` rows
   must first pass two independent automatic reviewers:
   `spanish_correctness_naturalness` and `english_pedagogy_cefr`. Passing generated rows
   move `AUTO_CHECKED → AUTO_REVIEWED → REVIEWED`, recording reviewer IDs, timestamps, and
   approval evidence in `content_manifest.json`.
5. **Publish gate (AC17)** — refuses to write `content.db` if **any** content-bearing row
   (`lexeme`, `sentence`, `accepted_answer`) lacks a `source` or is not `REVIEWED`. For
   `source=ai_draft`, it also requires both automatic approvals from distinct reviewers.
   Raises a hard, non-zero exit — a CI-level gate, not a warning. This is the mechanical
   enforcement of C5: no raw-generated or un-reviewed learning material can ship.

## Provenance columns

`lexeme`, `sentence`, and `accepted_answer` each carry: `source`, `sourceId`, `license`,
`vettingStatus`, `reviewedBy` (nullable), `reviewedAt` (nullable, epoch millis). The
`conjugation_lemma_map` carries `source` + `license`. These columns are the audit trail the
publish gate inspects, and they are mirrored 1:1 by the Kotlin Room entities in
`app/src/main/java/com/magicalhippie/aprende/data/content/`.

The build also emits `content_manifest.json`: counts by `vettingStatus` and by `source`, the
review trail for every `authored` row, and an `autoReviewLedger` for every shipped
`source=ai_draft` row. The ledger is not stored in the app DB schema; it is a build artifact
for review and CI audit.

## Coverage report (Phase 0 breadth baseline)

The build emits generated artifacts next to `content.db`:

- `content_coverage.json` — full breadth report.
- `coverage_snapshot.json` — compact summary intended for review diffs.

It also updates the committed, stable review baseline:

- `tools/content-pipeline/coverage_baseline_snapshot.json`

The report is vocabulary-first and distinguishes raw rows from learner-ready content.
A lexeme is learner-ready only when it has reviewed source/license metadata, enough reviewed
sentence contexts, and both production and recognition exercise coverage.
Exercise coverage only counts when the `LEXEME` exercise points to an existing reviewed
sentence that is linked to the target lexeme; dangling or unrelated exercises are reported
but cannot satisfy readiness.

Current readiness budgets:

| Lexeme type | Reviewed sentence contexts | Exercise coverage |
|---|---:|---|
| High-value verb (`pos=verb`, `frequencyRank <= 500`) | 4 | production + recognition |
| Default lexeme | 2 | production + recognition |

The report includes counts by POS, CEFR band, frequency bucket, source, license, vetting
status, exercise type, per-lexeme readiness blockers, and the current missing A1/A2 gaps.
Those gaps are checked against a small local A1/A2 target spine in `build_content_db.py`.
That target spine is an audit list, not shipped learning content; every listed word still
needs source, license, sentence, accepted-answer, and reviewer provenance before it can ship.
Each target carries a `sourceBasis` pointing back to the spec, roadmap, or selected frequency
spine so the gap list stays source-checked rather than freehand.

Use `--baseline-snapshot <path>` to write the review baseline somewhere else. The default
path is intentionally not gitignored, so content breadth changes produce a small reviewable
diff without committing the generated `content.db` or full report artifacts.

Use `--fail-on-coverage-gaps` to turn the report into a gate. It exits with code 4 when
current A1/A2 rows are not learner-ready, while still writing the JSON reports and baseline
snapshot so the blocker list is inspectable.

## Frequency source and license decision

Phase 0 selects `hermitdave/FrequencyWords` as the canonical ordering spine for Spanish
frequency ranks. The repository documents OpenSubtitles-derived generated outputs and states:
code is MIT, content is `CC-by-sa-4.0`.

Policy for Aprende:

- Use FrequencyWords only for rank/order metadata.
- Treat redistributed rank data as `CC-BY-SA-4.0`.
- Keep frequency-derived metadata explicitly attributed and separate from authored curriculum
  text in provenance/reporting.
- Continue using Tatoeba textual sentences under `CC-BY-2.0-FR` or CC0 subset terms, depending
  on the source row.
- Continue using Wiktionary-derived gloss/conjugation checks under Wiktionary's CC-BY-SA terms.
- Render these obligations through the same in-app attribution surface used for content rows.

Source checks:

- FrequencyWords: https://github.com/hermitdave/FrequencyWords
- Tatoeba downloads/license: https://tatoeba.org/en/downloads
- Wiktionary copyrights: https://en.wiktionary.org/wiki/Wiktionary:Copyrights

## Schema contract

`SCHEMA_DDL` in `build_content_db.py` is the authoritative table definition, and the asset is
written with `PRAGMA user_version` = the Room `@Database` version (currently 1). Room exports
its schema from the entities and **fails prepopulation on any mismatch** (table/column names,
nullability, type affinity, FTS layout). When the schema changes, bump both the Room
`@Database` version and `SCHEMA_VERSION` here together, and rebuild the asset.

## Language deviation note

PLAN P0.3 nominally calls for a JVM/Kotlin tool; this spike is **Python** on purpose:
it is dev-time tooling that is never shipped in the app, it can be **run and the gate proven
here** (where no JVM/Gradle/SDK toolchain exists), and Python's `sqlite3`/data tooling fits
content processing well. It can be ported to a Gradle/Kotlin module later — the **schema** (which
the Room entities mirror) is the real contract, not the build language.

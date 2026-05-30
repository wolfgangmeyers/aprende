# Content pipeline (P0.3)

Dev-time tool that builds the read-only `content.db` SQLite asset the app ships via Room
`createFromAsset`. It is the **only** path learning content takes into `content.db`, and it
mechanically enforces the C5 / SPEC §4.6 content-vetting requirement: nothing fabricated,
sourceless, or un-reviewed ships.

```bash
# Build from the vetted sample (writes content.db + content_manifest.json next to it):
python3 build_content_db.py --out ../../app/src/main/assets/database/content.db

# Demo the publish gate REJECTING un-reviewed content (non-zero exit — proves AC17):
python3 build_content_db.py --out /tmp/content.db --inject-unvetted
```

## 5-stage vetting workflow

Every content row flows through these stages; `vettingStatus` is promoted at each step and
only `REVIEWED` rows are allowed to ship.

1. **Ingest** — rows originate from explicit, licensed sources (e.g. Tatoeba sentence pairs,
   a frequency list, Wiktionary glosses). Each row carries provenance from the moment it
   enters. Status starts `UNVETTED`.
2. **Derive** — structural/derived rows are built (sentence↔lexeme joins, the
   conjugation→lemma map, generated exercises). These carry `source`/`license` where
   meaningful.
3. **Auto-check** — automated validation: every sentence has ≥1 accepted answer, accepted
   answers reference a real sentence and are normalized (trimmed/lowercased), every row has a
   license. Passing rows are promoted `UNVETTED → AUTO_CHECKED`. Failures abort the build
   (exit 3).
4. **Human review** — a reviewer signs off, promoting `AUTO_CHECKED → REVIEWED` and recording
   `reviewedBy` + `reviewedAt`. `authored`/LLM-drafted rows (e.g. extra accepted-answer
   variants) get extra scrutiny here; in real builds a human must set this — the spike
   pre-records a deterministic sign-off for the sample.
5. **Publish gate (AC17)** — refuses to write `content.db` if **any** content-bearing row
   (`lexeme`, `sentence`, `accepted_answer`) lacks a `source` or is not `REVIEWED`. Raises a
   hard, non-zero exit — a CI-level gate, not a warning. This is the mechanical enforcement
   of C5: no invented or un-reviewed learning material can ship.

## Provenance columns

`lexeme`, `sentence`, and `accepted_answer` each carry: `source`, `sourceId`, `license`,
`vettingStatus`, `reviewedBy` (nullable), `reviewedAt` (nullable, epoch millis). The
`conjugation_lemma_map` carries `source` + `license`. These columns are the audit trail the
publish gate inspects, and they are mirrored 1:1 by the Kotlin Room entities in
`app/src/main/java/com/magicalhippie/aprende/data/content/`.

The build also emits `content_manifest.json`: counts by `vettingStatus` and by `source`, plus
the review trail for every `authored` row — an auditable summary of what shipped.

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

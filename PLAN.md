# Aprende — Implementation Plan (Phase 0 + Phase 1 MVP)

**Status:** Draft for review. Decomposes `SPEC.md` v1.1 (accepted) into dev-loop iterations.
**Date:** 2026-05-30
**Source of truth:** `SPEC.md`. This plan only sequences *how* we build it; any conflict → SPEC wins. Section refs like (§6) point at SPEC.md.
**Scope of this plan:** Phase 0 (spikes + scaffold) and Phase 1 (the offline MVP). Phases 2 (audio/speech) and 3 (polish) stay at SPEC §16 granularity and get their own plan when reached — planning them now would be speculative.

> **Note:** this file previously held the unrelated magical-hippie *subscription* Phase-1 plan; it has been replaced with the Aprende plan on this dedicated branch. The prior content remains in git history.

## How to read this

Each iteration is one **dev-loop unit**: plan → implement TDD → robot-review → fix → done, sized to a single reviewable PR. For each I give: **Goal**, **Builds (files/modules)**, **Depends on**, **Contract** (what it exposes to later iterations — the inter-iteration seam), **Tests / AC** (SPEC acceptance criteria it satisfies). Ordering is dependency-driven; the critical path is called out.

## Open decisions carried into implementation

These are unresolved in SPEC.md and explicitly tracked here so they don't get lost:

- **O1 — frequency-list & licensing choice (owner decision, needed before *full* content authoring).** Which CC-licensed list we ship (hermitdave CC BY-SA vs Leipzig CC BY 4.0 vs Wiktionary) and how ShareAlike is contained so copyleft doesn't reach our authored content (§4.5). **Does not block Phase 0/1 mechanics** — P0.3 de-risks the pipeline with a small sample slice; full authoring waits on this answer. *Owner: project owner.*
- **O2 — NPC-simulated leaderboard (later-phase decision, NOT v1).** v1 cuts leagues entirely (server-dependent, §2/§9). Whether to add a fidelity-reduced NPC leaderboard + streak-vs-self ghost is a **Phase-3** product decision; it is not a dependency of anything in this plan. Revisit at Phase 3 planning. *Owner: product.*

Neither decision blocks starting implementation (P0.1 onward).

## Greenfield note

This repo currently holds the unrelated magical-hippie storefront. The Aprende app is a **new, self-contained Android project** (new Gradle root, e.g. `aprende/`), not an extension of `/app`. Nothing here touches the storefront code. (The stack choice and RN/Expo rejection are settled in §3 — not relitigated.)

---

## Module / package layout (target)

Single Gradle app module to start (split later only if it earns it — §13). Packages mirror the §12.1 layers:

```
aprende/
  app/                      # Android app module (Gradle Kotlin DSL)
    src/main/assets/database/content.db   # pre-built, from the content pipeline (P0.3)
    src/main/java/.../
      ui/          # Compose screens + ViewModels (UiState, StateFlow)
      domain/      # use-cases + pure logic: srs/, grading/, conjugation/, session/, gamification/  (no Android deps)
      data/        # Room (content/ + progress/), DataStore, repositories (interfaces + impls)
      di/          # Hilt modules
    src/test/      # JVM unit + Robolectric Compose tests
    src/androidTest/  # instrumented (Espresso, real-DB, offline E2E)
  tools/content-pipeline/   # dev-time JVM/Kotlin tool that builds content.db (NOT shipped)
```

**Dependency direction (enforced in review):** `ui → domain → data` interfaces; domain has **no** Android/Room imports (pure Kotlin, testable on JVM); only `data` knows persistence; cross-DB joins live only in repositories (§12.1).

---

## Phase 0 — Spikes & scaffold (de-risk before building the MVP)

Goal of the phase: prove the two genuinely-novel risks (FSRS correctness, content-DB pipeline + size) and stand up a buildable skeleton. Resolves O4; informs O1; measures the O5 size question.

### P0.1 — Project scaffold + DI + CI
- **Goal:** a buildable app with the layered skeleton, DI graph, and JVM test harness.
- **Builds:** Gradle Kotlin DSL (`minSdk 24`, `targetSdk 35`), Compose+Material 3, Hilt, Room, DataStore, coroutines/Flow deps; `@HiltAndroidApp`; one trivial screen + ViewModel; test deps (JUnit4, `kotlinx-coroutines-test`, Turbine, Robolectric, Room-testing); GitHub Actions running JVM tests.
- **Depends on:** nothing (first).
- **Contract:** DI boots; `collectAsStateWithLifecycle` wiring pattern established; CI green on a trivial test.
- **Tests / AC:** a smoke ViewModel `StateFlow` test (Turbine) + a Robolectric Compose render test. No SPEC AC yet (scaffolding).

### P0.2 — FSRS-6 engine spike  ⟵ **critical path / highest risk**
- **Goal:** correct, fully-local FSRS-6 in pure Kotlin with shipped default weights, proven against reference vectors. Resolves **O4**.
- **Builds:** `domain/srs/` — FSRS-6 functions (R(t,S), interval for retention r, D/S update, initial D0/S0 per §6.2), the 21-weight default constant vector, and `ScheduleReviewUseCase(itemState, grade, now: via Clock) → newState` with grade derivation (§6.4). No `SrsScheduler` interface (D1). Inject `java.time.Clock`.
- **Depends on:** P0.1.
- **Contract:** `ScheduleReviewUseCase` + an `SrsItemState` value type (`D, S, lastReview, dueAt`) — the seam every later SRS consumer uses. Pure domain, no persistence yet.
- **Tests / AC:** **AC5** (correct→later `dueAt` than wrong; formulas match known FSRS-6 reference vectors within tolerance), plus `Clock.fixed()` determinism. **Timebox:** if reference vectors can't be matched within the spike budget, switch to the Leitner contingency (§6.1) behind the same use-case and record it.

### P0.3 — Content pipeline + two-DB load spike (with the vetting workflow baked in)
- **Goal:** prove we can assemble a **vetted, source-checked** content slice into a pre-built `content.db` that Room loads via `createFromAsset`, with FTS, and measure AAB size. Establishes the C5 content-vetting workflow (§4.6) as the *only* path into `content.db`. Measures **O5**, informs **O1**.
- **Builds:** `tools/content-pipeline/` (dev-time, not shipped) implemented as the **staged vetting workflow** below; each content row carries provenance (`source`, `sourceId`, `license`, `vettingStatus`, `reviewedBy/At`). Emits lexemes/sentences/accepted-answers/conjugation-map + course/section/unit/node/lesson/exercise + `sentence_fts`, into a SQLite file whose schema matches the Room `@Database` (schema exported, §10). Wire `createFromAsset("database/content.db")`; build an AAB and record size.
- **Depends on:** P0.1. (Independent of P0.2 — can run in parallel.)
- **Contract:** the **content schema (incl. provenance columns)** + the staged pipeline + a working `createFromAsset` load. Later iterations and all future content authoring go through this pipeline — there is no other way to add content.
- **Tests / AC:** instrumented test loading the bundled `content.db` + FTS `MATCH`; **AC17** (build *fails* on an `UNVETTED`/sourceless row — seed one and assert rejection); recorded AAB size vs the ~200 MB base cap (per §11.0 the v1 Path stays in the base module).
- **Owner input:** O1 (licensing) needed before *full* content authoring; the spike uses a small **vetted** sample slice to de-risk both mechanics and the gate.

#### Content-vetting workflow (C5 / SPEC §4.6) — the pipeline stages
This is the multi-stage content pipeline `tools/content-pipeline/` implements; it is the design's answer to "content is a vetted, source-checked risk." **No learning content reaches `content.db` except through these stages**, and the publish step is a hard gate, not advisory.

1. **Ingest (sets `source`/`sourceId`/`license`, status `UNVETTED`)** — pull only from vetted sources (Tatoeba pairs, frequency lists, Wiktionary glosses — §4.5). Fabrication is structurally impossible: a row cannot exist without a source record. *LLM/hand drafting of `authored` rows (e.g. grammar tips, extra accepted variants) is allowed here but lands as `source=authored, status=UNVETTED`.*
2. **Derive** — filter to short sentences, pick target lemmas, build accepted-answer sets, generate conjugations from the §5.2 rule tables (deterministic, not invented), assemble the Path. Transform-only; never invent facts.
3. **Auto-check (`AUTO_CHECKED`)** — automated validators: ≥1 accepted answer per prompt; translation bidirectionally consistent with the source pair; accepted sets pass the §5.5 normalizer; conjugations match the generator; no orphans/dupes; license present. Failures bounce the row back, never silently pass.
4. **Human review gate (`REVIEWED`)** — reviewer sign-off (`reviewedBy`/`reviewedAt`) before ship, with extra scrutiny on `authored` rows and semantic calls (ser/estar, idioms). LLM output stays `UNVETTED` until a human reviews it.
5. **Publish (the gate)** — the `content.db` build step **fails hard** (CI-level) if any to-be-shipped row is not `REVIEWED` or lacks a `source`. This is AC17 and the mechanical enforcement of C5.

A reviewable **content manifest** (counts by `source`/`vettingStatus`, list of `authored` rows + reviewers) is emitted each build so coverage and the review trail are auditable — and surfaces what's still `UNVETTED` rather than letting it pass silently.

---

## Phase 1 — Core offline loop (the MVP)

Goal of the phase: the entire Tier-0 offline loop (§11.0) — take a lesson, get graded, schedule reviews, earn XP/streak, review weak items — fully offline, no audio. Meets **AC1–AC8, AC11–AC15**.

### P1.1 — Data layer: two Room DBs + repositories
- **Goal:** persistence foundation per D2 — `content.db` (read-only) and `progress.db` (read-write, explicit migrations).
- **Builds:** `data/content/` DAOs over the P0.3 schema; `data/progress/` entities (`srs_item` with composite PK `(itemId, itemType)`, `node_progress`, `mistake_queue`, `daily_activity`, `user_stats`, `achievement`) + migrations; DataStore (Proto) for settings; repository **interfaces** (in domain) + Room implementations (in data); the conjugation→lemma lookup with **unknown-surface-form fallback** (§12.1); cross-DB join confined to the repo.
- **Depends on:** P0.1, P0.3 (content schema). P0.2 defines the `SrsItemState` shape stored in `srs_item`.
- **Contract:** repository interfaces consumed by all domain use-cases (`ContentRepository`, `ProgressRepository`); `progress.db` migration baseline.
- **Tests / AC:** in-memory DAO tests; **progress.db migration test**; **AC15** (simulated `content.db` version bump leaves `progress.db` intact); unknown-form fallback test (credits target item + logs, never silently drops — §12.1).

### P1.2 — Answer-checking + conjugation (pure domain)
- **Goal:** the deterministic grading core and form generation.
- **Builds:** `domain/grading/` — normalize (NFC, lowercase, trim, strip terminal punct), accent-insensitive compare, Damerau-Levenshtein threshold, multi-accepted-answer-set match, and equality for tiles/matching/choice (§5.5); `domain/conjugation/` — regular ending tables (3 classes × 6 tenses) + irregular/stem-change override map → form generator (§5.2).
- **Depends on:** P0.1. (Pure logic — parallelizable with P1.1.)
- **Contract:** `GradeAnswerUseCase(input, exercise) → GradeResult{correct, usedHint, typoFlag}` feeding §6.4; `Conjugator`.
- **Tests / AC:** **AC2** (missing accent accepted/soft-typo; single-char typo accepted; wrong word rejected), **AC3** (any accepted-set member passes), **AC4** (regular verb across six tenses + ser/estar/tener overrides, test vectors).

### P1.3 — SRS integration + strength
- **Goal:** wire the P0.2 engine to persisted state with lazy decay and the fan-out rule.
- **Builds:** connect `ScheduleReviewUseCase` to `progress.db.srs_item` via `ProgressRepository`; lazy due-query (`clock.now() ≥ dueAt`); per-exercise→**target item** fan-out (§6.4a); current-`R` strength computation for the Words list (§6.6).
- **Depends on:** P0.2, P1.1.
- **Contract:** `DueItemsQuery` (due = `now ≥ dueAt`), a **separate `SeenItemsByStrengthQuery`** (all seen items sorted by ascending current `R`, for the weakest-first review/Words surfaces — §8 weak ≠ §6.5 due), `RecordAnswerUseCase` (applies grade to the target `srs_item`), per-item strength accessor.
- **Tests / AC:** **AC6** (advance injected `Clock` → items become due with no background job); fan-out test (one exercise updates only its target item, not incidental lexemes).

### P1.4 — Lesson session generator + flow
- **Goal:** assemble and run a lesson session end-to-end (logic layer).
- **Builds:** `domain/session/` — `GenerateLessonUseCase` (select new+review items, mix exercise types per §7.3, target ~15–17, interleave review); in-session **mistake re-queue** (dynamic length) + append to persistent `mistake_queue`; on-complete orchestration of XP/streak/SRS updates.
- **Depends on:** P1.1, P1.2, P1.3.
- **Contract:** `LessonSession` model + `GenerateLessonUseCase` consumed by the lesson UI (P1.6); **`mistake_queue` enqueue operation** (the drain side is consumed by P1.7); session state kept small (§12.3).
- **Tests / AC:** session-composition tests; wrong-answer re-queue forces correct-before-complete; **captures the AC7 mistakes (AC7 is closed in P1.7 once the drain/review path exists)**.

### P1.5 — Gamification
- **Goal:** XP, daily goal, streak, hearts, gems, achievements — all lazy-from-`Clock`, local.
- **Builds:** `domain/gamification/` — `UpdateStreakUseCase` (epoch-day local-date, grace window, freeze auto-consume — §9/§12.3), hearts (lazy regen via `Clock`, refill on practice, gem spend), XP/daily-goal, gems ledger, achievement evaluation; persisted in `user_stats`/`daily_activity`.
- **Depends on:** P1.1.
- **Contract:** use-cases consumed by lesson-complete (P1.4) and the home/profile UI.
- **Tests / AC:** **AC8** (5 wrong → hearts gate; lazy regen; practice refill), **AC13** (streak survives a missed day iff a freeze was equipped, and the freeze is consumed); achievement-threshold tests.

### P1.6 — UI: Path, lesson, navigation, delight
- **Goal:** the playable surface — Compose screens + ViewModels + navigation + "whimsy/magic/delight" animations.
- **Builds:** `ui/` — Path/home (positional unlock), lesson session screen rendering each Tier-0 exercise type + accent bar (§5.4), profile/stats, settings; ViewModels exposing `UiState` via `stateIn(WhileSubscribed)`, collected with `collectAsStateWithLifecycle`; **`SavedStateHandle` session-state rehydration** (current exercise index + small re-queue, §12.3 — the mechanism AC12 verifies); Navigation Compose; spring/`AnimatedContent`/`rememberInfiniteTransition` for feedback + strength crystals (§12.1).
- **Depends on:** P1.4, P1.5.
- **Contract:** the runnable app for the offline E2E.
- **Tests / AC:** Compose UI tests per exercise type; **AC1** (fresh install, **airplane mode**, full Tier-0 lesson → graded → XP → streak, zero TTS/STT); **AC12** (process death mid-lesson resumes/clean-restarts without corrupting progress).

### P1.7 — Review phases UI + session types
- **Goal:** reinforcement surfaces distinct from learning new (§8).
- **Builds:** review hub; due-review session (lowest-`R` first), mistakes review (drains `mistake_queue`), vocabulary practice (untimed matching), Words screen (strength, weakest-first).
- **Depends on:** P1.3, P1.4, P1.6.
- **Contract:** completes the §8 review loop.
- **Tests / AC:** **AC7** (lesson mistakes reappear in Mistakes review and leave the queue when answered correctly).

### P1.8 — Backup/restore + attribution
- **Goal:** satisfy C3 (no-server portability) and C4 (licensing).
- **Builds:** SAF export/import of `progress.db`↔versioned JSON (`CreateDocument`/`OpenDocument`, §11); `dataExtractionRules` + `allowBackup` for Auto Backup; in-app **credits/attribution** screen listing bundled-content licenses (§4.5).
- **Depends on:** P1.1, P1.6.
- **Contract:** MVP complete.
- **Tests / AC:** **AC11** (export → wipe → import restores streak/XP/SRS), **AC14** (attribution visible).

---

## Critical path & parallelism

```
P0.1 ─┬─► P0.2 (FSRS, riskiest) ─────────────┐
      └─► P0.3 (content pipeline) ─► P1.1 ────┼─► P1.3 ─► P1.4 ─► P1.6 ─► P1.7 ─► P1.8
                  P1.2 (grading, parallel) ───┘            P1.5 ─────────┘
```
- **Start P0.2 and P0.3 in parallel** after P0.1 — independent, and they de-risk the two unknowns. P0.2 is highest-risk; resolve its timebox/contingency early.
- P1.2 (pure grading/conjugation) builds in parallel with P1.1.
- P1.3 needs both P0.2 and P1.1; everything funnels through P1.4 → P1.6.

## Definition of done (Phase 1 / MVP)

All of **AC1–AC8, AC11–AC15** pass (per CLAUDE.md: 100% green, including the airplane-mode E2E AC1 and the content-update-preserves-progress AC15). Tier-0 loop is fully offline. Then Phase 2 (audio/speech, AC9/AC10/AC16) gets its own plan.

## Risks carried from SPEC (planning view)

- **FSRS correctness (P0.2)** — the one real unknown; timeboxed with a Leitner contingency. Front-loaded deliberately.
- **O1 licensing (P0.3/owner)** — blocks *full* content authoring, not the pipeline mechanics; sample slice de-risks first.
- **Content size (P0.3)** — measured in the spike; if over the base cap, Play Asset Delivery install-time pack (keeps offline guarantee; §11.0 Path invariant: v1 Path stays in base module).
- **Content correctness / fabrication (C5, SPEC §4.6 / R4)** — mistranslations or invented content actively mis-teach and can't be hotfixed without an app update. Mitigated by building the **vetting workflow into P0.3 from day one** (provenance on every row, auto-checks, human review gate, publish gate that fails on unvetted/sourceless rows — AC17). The gate exists before any real content is authored, so content can never accrete un-reviewed.

---

## Implementation readiness

P0.1 is unblocked and needs no open-question answers — implementation can start immediately on approval. O1 is only required before *full* content authoring (mid-P0.3 → P1.x); O2 is a Phase-3 product decision and blocks nothing here.

*Plan covers Phase 0 + Phase 1. Status: reviewed (plan-consistency + scope); content-vetting workflow (C5) folded into P0.3. P0.1 scaffold built (see `aprende/`). Next: P0.2 (FSRS spike) + P0.3 (content pipeline incl. the vetting gate), parallelizable.*

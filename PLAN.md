# Aprende Spanish Curriculum Rebalance Plan

**Status:** Draft for dev-loop review.
**Source of truth:** `SPEC.md`.
**Scope:** Implementation plan only. This planning task does not implement code, change curriculum content, commit, or push.

## Goals

Repair Aprende's curriculum shape so a native English speaker can start from zero Spanish, move through a coherent A1/A2 on-ramp, and continue into the existing intermediate phrase-heavy curriculum without the current blanket-B1 noun-phrase mislabeling.

The implementation must handle three separate fixes:

1. Replace the noun-phrase blanket-B1 assignment with a deterministic phrase CEFR rubric.
2. Re-band the existing B1 noun-phrase rows with audit evidence.
3. Backfill and sequence a 300-500 item A1/A2 beginner on-ramp, including 100-200 phrase/chunk frames.

## Design Decisions

### Rubric Shape

Add a rubric function used by `build_phrase_pack_specs` and any future phrase/chunk pack builder. The function should accept the available phrase metadata already present in the content pipeline: lemma/phrase text, POS, English gloss, domain/reason, source basis, frequency rank when available, and optional manually supplied rubric hints. It returns:

- `cefrBand`
- `difficultyPrior`
- `rubricReason`
- `rubricSignals`

The rubric should be deterministic and auditable. It should not call an LLM, inspect runtime learner data, or depend on row order.

Banding rules:

- A1: one short concrete routine phrase, survival/courtesy/classroom/home/food/place/time topic, high-frequency head noun, no abstract/institutional/formal domain signal, no idiom, no multi-clause structure.
- A2: concrete daily-life phrase with one common modifier or collocation, routine errands/health/family/travel/shopping/school/work topic, still teachable with A1/A2 grammar and common sentence frames.
- B1+: formal, institutional, abstract, legal/medical-administrative in a specialized sense, idiomatic, low-frequency, multi-step, multi-modifier, or phrase chains requiring narration, negotiation, explanation, advice, planning, or specialized interpretation.

Manual overrides are allowed only as explicit data in the pack source, not hidden special cases. Each override must include a reason and still appear in validator/audit output.

### Re-Banding Safety

Re-banding should update CEFR metadata over existing rows, not rebuild identities. Stable IDs, source/license, reviewed status, accepted answers, and exercise links stay intact.

Use a two-pass process:

1. Dry-run report: apply the rubric to existing B1 noun phrases and emit before/after counts, changed-row manifest, rubric signals, and audit buckets.
2. Apply pass: persist the new `cefrBand`, `difficultyPrior`, and rubric metadata only after the dry-run report passes validation.

The audit sample must include at least 150 changed rows or 5% of changed rows, whichever is larger, covering A1 moves, A2 moves, and B1+ stays. Implementation can satisfy this with a checked-in deterministic sample manifest plus review annotations, or with a generated audit report if the project already has a review-evidence format by then. The gate fails above 10% unresolved sample disagreement.

### On-Ramp Structure

Create the on-ramp as its own content phase. It should use reviewed, source-checked rows and the existing publish gate. Re-banded existing A1/A2 phrase rows may be threaded into beginner nodes when they fit the sequence, but the on-ramp must be deliberately ordered rather than just counted.

Target shape:

| Unit | Focus | Approx. Items | Phrase/Chunk Frames |
|---|---:|---:|---:|
| 1 | Greetings, courtesy, classroom/app commands, yes/no, names | 35-55 | 15-25 |
| 2 | Articles, gender, people, family, basic adjectives | 35-55 | 10-20 |
| 3 | `ser` for identity/description, subject pronouns | 35-55 | 10-20 |
| 4 | `estar`, location, home, places, here/there | 35-55 | 15-25 |
| 5 | `tener`, needs, food, objects, age | 40-60 | 15-25 |
| 6 | `ir`, places, time, routines, near-future-ready chunks | 40-60 | 15-25 |
| 7 | `querer`, `poder`, requests, shopping, travel, school/work | 45-70 | 20-30 |
| 8 | `hacer`, health, weather, routines, mixed A2 review questions | 45-70 | 20-30 |

On-ramp floors:

- At least 300 total A1/A2 on-ramp reviewables.
- At least 100 A1/A2 on-ramp phrase/chunk items.
- At least 120 A1 on-ramp reviewables.
- At least 120 A2 on-ramp reviewables.
- At least 8 ordered beginner units.

Node sequencing rules:

- No more than 8 new targets per node.
- At least 30% of non-introductory exercises recycle previously introduced targets.
- Each unit after Unit 1 includes review coverage for targets introduced in earlier units.
- Every A1/A2 target has `introducedInUnit`, `introducedInNode`, and subsequent review appearances in reporting.
- Every introduction node has reviewed exercise coverage for each target it introduces.
- A node cannot use a target item before its introduction node.

### Distribution Metrics

Keep two separate metric concepts:

- On-ramp floor: the beginner path has enough ordered A1/A2 content to teach a zero-knowledge learner.
- Post-reband total distribution: the whole reviewable corpus after applying the rubric to existing rows.

The validator should fail if A1+A2 phrase/chunk totals remain below 1,500 after re-banding without reviewed audit justification, or if B1 remains above 6,000 after re-banding. These gates catch the current blanket-B1 failure while allowing actual post-reband totals to reflect the corpus.

The steady-state target remains a product trajectory, not a first milestone gate: roughly 10-15% A1, 15-20% A2, 40-50% B1, 20-30% B2, and 5-10% C1+ once C1+ content exists.

### C1+ Lane

Do not backfill C1+ in the first implementation. Do make C1+ visible in reports so zero is an explicit gap. Reserve future C1+ categories:

- Argumentation, nuance, and stance.
- Abstract professional/academic vocabulary.
- Idioms, register, and pragmatic tone.
- Long-form connectors, discourse markers, and complex clause patterns.

The future sequencing boundary is after B2 reviewables that cover routine narration, explanation, planning, and opinion. C1+ nodes must not appear before B2 bridge content is complete.

## Phased Implementation

### Phase 1 - Validator Baseline And Reporting Contracts

Files likely touched:

- `aprende/tools/content-pipeline/lemma_count_sanity.py`
- Existing content-pipeline test files or new tests under `aprende/tools/content-pipeline/`

Work:

- Extend the current sanity report to include phrase/chunk counts by CEFR, noun-phrase counts by CEFR, on-ramp counts, path sequencing summary fields, C1+ lane reporting, and post-reband gate placeholders.
- Preserve the current `--assert-current` reporting contract until the rubric/reband phases intentionally update expected counts.
- Add an assertion mode for target gates, separate from `--assert-current`, so workers can distinguish "known current skew" from "post-repair required shape."
- Represent the review-gate contract explicitly: an item counts as reviewed for AI-drafted or AI-re-banded content only when it has at least two independent approved reviews. The Phase 1 validator must report that status and be able to assert it, even before later phases add new drafted/re-banded rows.

Integration tests:

- `lemma_count_sanity` loads `build_content_db.py`, runs the real stage checks/review gate, builds the real coverage report, and asserts the current skew in `--assert-current`.
- A target-gate test uses the real sanity report object and fails when A1/A2 phrase/chunk counts are zero.
- A C1+ reporting test verifies the C1+ lane/report section appears even when count is zero and includes the future-lane categories and B2-to-C1 boundary.
- A review-gate test verifies an AI-drafted or AI-re-banded item with fewer than two independent approved reviews is not counted as reviewed, and that the target assertion fails on insufficient independent reviews.

Spec mapping: Requirements 12-19, 21.

### Phase 2 - Deterministic Phrase CEFR Rubric

Files likely touched:

- `aprende/tools/content-pipeline/build_content_db.py`
- Content-pipeline tests for phrase pack construction
- Optional rubric fixture data under the content-pipeline tools directory

Work:

- Add a single rubric helper for phrase/chunk CEFR assignment.
- Replace the hard-coded `"B1"` in `build_phrase_pack_specs` with the helper.
- Emit `rubricReason` or equivalent audit data in the pack report if the schema/reporting path supports it. If the schema cannot carry it yet, emit it in a named build-time `phrase_cefr_rubric_report.json` artifact without changing content row identity.
- Add representative fixture cases:
  - A1: `entrada principal`, `agua fría`, `mi casa`.
  - A2: `cita médica`, `mesa reservada`, `billete de ida`, `tienda abierta`.
  - B1+: `reclamación formal`, `procedimiento administrativo`, `responsabilidad legal`, `informe detallado`.

Integration tests:

- Build a phrase pack through the real pack builder and assert fixture phrases land in expected CEFR bands.
- Regression test that a mixed phrase pack produces at least two CEFR bands, so blanket-B1 assignment fails.
- Test manual override requires a reason and appears in rubric audit output.

Spec mapping: Requirements 1-3, 18-19, 21.

### Phase 3 - Existing B1 Noun-Phrase Re-Banding

Files likely touched:

- `aprende/tools/content-pipeline/build_content_db.py`
- `aprende/tools/content-pipeline/lemma_count_sanity.py`
- Reband audit manifest/report fixtures

Work:

- AI-assisted drafting/re-banding is allowed for this phase's proposed CEFR updates, but proposed changes remain non-shippable until deterministic checks pass and at least two independent correctness reviews approve the item/re-band decision.
- Apply the new rubric to existing B1 noun-phrase rows during content construction.
- Generate a deterministic changed-row manifest with old band, new band, reason, source pack, and rubric signals.
- Preserve stable IDs and all source/review/exercise linkage.
- Add the audit sample mechanism and gate.
- Update `--assert-current` only after the reband phase intentionally changes the known count contract.

Integration tests:

- Full content-pipeline sanity run shows noun phrases no longer all land in B1.
- Stable identity test compares selected re-banded rows before/after and verifies IDs, source/license, reviewed status, accepted answers, and exercise links are preserved.
- Audit-gate test injects excessive unresolved sample disagreements and asserts the gate fails.
- Distribution test fails if B1 remains above 6,000 or A1+A2 phrase/chunk total remains below 1,500 without reviewed audit justification.

Spec mapping: Requirements 4-6, 15, 18-19, 21.

### Phase 4 - A1/A2 On-Ramp Content Backfill

Files likely touched:

- Extracted content pack modules, manifest files, or data files under `aprende/tools/content-pipeline/`.
- Minimal orchestration hooks in `aprende/tools/content-pipeline/build_content_db.py`.
- On-ramp manifest/fixture files if introduced.
- `lemma_count_sanity.py` target thresholds.

Work:

- On-ramp source rows may be AI-drafted, but AI-drafted content remains non-shippable and must not count as reviewed until deterministic checks pass and at least two independent correctness reviews approve the row.
- Build the 8-unit A1/A2 on-ramp in source-checked batches.
- Represent each batch in an on-ramp manifest that includes target item, CEFR band, item type, source/review status, unit/node placement, and topic/core-verb category.
- Prefer reviewed existing/re-banded phrase rows when they fit early units.
- Add new reviewed rows only through the existing source/license/review gate.
- Include the required core verbs and topic sequence.
- Keep batch size reviewable: each pack should be independently source-checkable and manifest-clean before the next pack.
- Maintain item inventory mix: 300-500 candidate on-ramp reviewables, 100-200 phrase/chunk frames, with at least 120 A1 and 120 A2 items.
- Do not treat on-ramp inventory counts as final passing on-ramp gates until Phase 5 path-qualified sequencing checks also pass.

Integration tests:

- On-ramp inventory test asserts the required candidate counts and planned unit count from the manifest.
- Core-verb/topic test asserts each required verb/topic category appears in the on-ramp manifest.
- Publish-gate test proves unreviewed or sourceless on-ramp rows cannot count toward on-ramp totals.
- Full sanity assertion fails if A1/A2 phrase/chunk inventory count regresses to zero.

Spec mapping: Requirements 7-11, 14, 18-19, 21.

### Phase 5 - Sequencing And Path Integrity

Files likely touched:

- Path/course construction in the content pipeline.
- `lemma_count_sanity.py`
- Path integrity tests.

Work:

- Add introduction metadata for every A1/A2 target item.
- Add path checks for no future dependencies.
- Add node checks for max 8 new targets and at least 30% recycle coverage in non-introductory exercises.
- Add introduction checks that every introduced target has reviewed exercise coverage in its introduction node.
- Add unit checks that each unit after Unit 1 reviews targets introduced in earlier units.
- Thread re-banded and newly added on-ramp items into the beginner path before B1 content.
- Promote Phase 4 on-ramp inventory counts to final on-ramp gate counts only after the items are path-qualified by these sequencing checks.

Integration tests:

- Build the real path and assert every A1/A2 on-ramp target has an introduction unit/node.
- Introduction-coverage test fails when an introduced target lacks a reviewed exercise in its introduction node.
- Dependency-order test fails on a fixture node that uses a target before introduction.
- Node-budget test fails when a node introduces more than 8 new targets.
- Recycle test fails when a non-introductory node has less than 30% prior-target practice.
- Prior-unit review test fails when a unit after Unit 1 contains no review coverage for targets introduced in earlier units.
- Final on-ramp gate test asserts only path-qualified items count toward the 300 total, 100 phrase/chunk, 120 A1, 120 A2, and 8-unit floors.

Spec mapping: Requirements 10-12, 18-19, 21.

### Phase 6 - Final Gate Consolidation

Files likely touched:

- `lemma_count_sanity.py`
- CI or local validation docs/scripts if present

Work:

- Consolidate `--assert-current` into the new accepted post-repair baseline.
- Add or document the command sequence future workers must run from `<worktree>/aprende/`.
- Ensure the report includes total reviewables, item-type breakdown, CEFR distribution, phrase/chunk distribution by CEFR, on-ramp counts, sequencing integrity, re-banding audit result, C1+ lane reporting, and threshold pass/fail summary.

Integration tests:

- End-to-end content sanity command runs the real build module, real review gates, real coverage report, and all target assertions.
- Regression fixture or monkeypatch test proves the old hard-coded-all-B1 behavior would fail.
- Snapshot/update test verifies future intentional count changes require updating a reviewed expected baseline.

Spec mapping: Requirements 13-21.

## Requirement Mapping

| Spec Requirement | Plan Coverage |
|---:|---|
| 1 | Rubric shape, Phase 2, Phase 4 |
| 2 | Rubric shape, Phase 2 |
| 3 | Rubric shape, Phase 2 fixture cases |
| 4 | Re-banding safety, Phase 3 |
| 5 | Re-banding safety, Phase 3 audit gate |
| 6 | Re-banding safety, Phase 3 stable identity test |
| 7 | On-ramp structure, Phase 4 |
| 8 | On-ramp structure, Phase 4 |
| 9 | On-ramp structure, Phase 4 topic/core-verb test |
| 10 | On-ramp structure, Phase 5 sequencing checks |
| 11 | On-ramp floors, Phase 4 |
| 12 | Sequencing rules, Phase 5 |
| 13 | Distribution metrics, Phase 6 |
| 14 | On-ramp floors, Phase 4 |
| 15 | Distribution metrics, Phase 3 |
| 16 | Distribution metrics, Phase 6 |
| 17 | C1+ lane, Phase 1 and Phase 6 |
| 18 | Phase 1 through Phase 6 validator work |
| 19 | Phase 1 through Phase 6 failing gates |
| 20 | Phased implementation |
| 21 | Integration tests listed in every phase |

## Validation Commands

Later implementation workers should confirm the exact test runner names after inspecting the content-pipeline test setup. The intended validation command sequence is:

```bash
cd /home/wolfgang/code/aprende-spanish-breadth/aprende
python3 tools/content-pipeline/lemma_count_sanity.py --assert-current
python3 tools/content-pipeline/lemma_count_sanity.py --assert-target-shape
python3 -m pytest tools/content-pipeline
```

If the project does not currently use `pytest`, Phase 1 should add the smallest local Python test harness consistent with the repo rather than relying only on manual script output.

## Non-Goals

- No deletion or deduplication of phrase/chunk content.
- No runtime-generated learning content.
- No C1+ content backfill in the first implementation.
- No app UI redesign as part of the curriculum repair.
- No commits or pushes from this planning task.

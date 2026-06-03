# Aprende Spanish Curriculum Rebalance Spec

## Problem

Aprende's current Spanish curriculum cannot serve its stated product mission: take a native English speaker from zero Spanish through fluent use with contextual sentence, phrase, and chunk practice. The current content set has 7,431 reviewable items, but its CEFR distribution is badly skewed: A1=23, A2=103, B1=7,057, B2=248, C1=0. Of those items, 755 are single words and 6,676 are phrase/chunk items.

The skew is not only a volume problem. The content pipeline currently hard-codes every noun phrase as B1 in `aprende/tools/content-pipeline/build_content_db.py`, so simple routine phrases such as "mesa reservada", "cita médica", and "entrada principal" are mislabeled above their real learner level. A prior audit found that roughly 34% of B1 noun phrases are really A1/A2 while roughly 66% are genuinely B1. The beginner on-ramp is also structurally missing: there are only 126 A1/A2 items total and zero A1/A2 phrase/chunk items, so a zero-knowledge learner has no coherent path into the app's core content.

This work defines the desired end state for repairing the curriculum distribution, sequencing, and validation gates. It is a planning task only; implementation and content changes happen later.

## Requirements

1. The curriculum must remain contextual: phrase and chunk items are first-class reviewable content, must not be deleted, and must not be deduplicated away to make CEFR counts look cleaner.

2. The content pipeline must use a deterministic, auditable CEFR decision procedure for phrase/chunk items instead of assigning all noun phrases to B1.

3. The phrase/chunk rubric must distinguish at least these bands:
   - A1: concrete, high-frequency, routine survival phrases that a zero-to-A1 learner can use without subordinate clauses, abstract nouns, formal register, or domain-specific institutional vocabulary.
   - A2: routine daily-life phrases that combine familiar concrete nouns with common modifiers, places, times, errands, health, family, food, home, travel, shopping, work, or school contexts, and may require simple collocation knowledge but not B1 grammar.
   - B1+: formal, institutional, abstract, multi-step, low-frequency, idiomatic, or domain-specific phrase chains whose use requires explaining, narrating, planning, advising, negotiating, or interpreting specialized contexts.

4. Existing B1 noun-phrase data must be re-banded by applying the new rubric to the existing approximately 6,300 B1 noun-phrase rows, with verification that prevents over-correcting genuinely B1 material.

5. Re-banding verification must include deterministic before/after counts, audit buckets by rubric reason, and a sampled review of at least 150 changed rows or 5% of changed rows, whichever is larger. The sampled review must separately cover rows moved to A1, rows moved to A2, and rows left at B1+, and the re-banding cannot pass while more than 10% of the sample has an uncorrected reviewer/rubric disagreement.

6. Re-banding must preserve every existing row's stable identity, provenance fields, reviewed status, source/license metadata, accepted answers, and exercise links unless a later implementation phase explicitly changes those fields for a validated reason.

7. The repaired curriculum must add a deliberately sequenced A1/A2 on-ramp of 300-500 newly introduced or explicitly path-threaded reviewable items for zero-knowledge English speakers. Re-banded existing rows may count toward the on-ramp only when they are assigned to beginner units/nodes with reviewed exercises and do not depend on later content.

8. The A1/A2 on-ramp must include 100-200 phrase/chunk frames, not just single-word vocabulary.

9. The A1/A2 on-ramp must cover, in order, greetings and classroom/app commands; pronouns, articles, gender, and basic noun/adjective agreement; core verbs `ser`, `estar`, `tener`, `ir`, `hacer`, `querer`, and `poder` in short sentence frames; family, food, home, time, places, health, shopping, travel, school/work, wants/needs, routine questions, and common courtesy chunks.

10. The on-ramp must sequence from zero to A2 without requiring B1 grammar, B1-only vocabulary, or unintroduced phrase patterns. Each lesson node must introduce no more than 8 new target items, at least 30% of non-introductory exercises in each node must recycle previously introduced targets, and each unit must include review coverage for targets introduced in earlier units.

11. "Zero-to-A2 on-ramp" means a learner can start with no Spanish and progress through at least 8 ordered beginner units containing at least 300 A1/A2 reviewables, at least 100 A1/A2 phrases/chunks, and explicit coverage of the core verbs and topics in Requirement 9.

12. "Coherent sequencing" means every A1/A2 target item is assigned to an introduction unit/node, every introduction has reviewed exercise coverage, no node depends on a target item whose introduction appears later in the path, and validator output can list each beginner target's first introduction and subsequent review appearances.

13. "Fluent product trajectory" means the validator reports a planned CEFR distribution that supports all levels instead of collapsing into B1: A1/A2 must be large enough for onboarding, B1/B2 must remain broad enough for practical fluency, and C1+ must have an explicit future lane rather than remaining absent.

14. The first implementation milestone's on-ramp floor must be measurable and unambiguous:
   - At least 300 total A1/A2 on-ramp reviewables.
   - At least 100 A1/A2 on-ramp phrase/chunk items.
   - At least 120 A1 on-ramp reviewables.
   - At least 120 A2 on-ramp reviewables.
   - At least 8 ordered beginner units.

15. The post-reband total CEFR distribution must be measured separately from the on-ramp floor. Because the existing audit predicts many B1 noun phrases will move to A1/A2, the validator must report actual post-reband totals rather than forcing them into the on-ramp-size range. The first post-reband gate must fail only if A1+A2 phrase/chunk totals remain below 1,500 without an explicit reviewed audit explaining why the prior 34% estimate did not hold, or if B1 remains above 6,000 after re-banding.

16. The steady-state curriculum target must be documented as a shape, not a false exact count: roughly 10-15% A1, 15-20% A2, 40-50% B1, 20-30% B2, and 5-10% C1+ once the product actually covers zero-to-fluent breadth.

17. The C1+ future lane must be measurable even before C1+ content is backfilled: the plan must reserve a validator/report section for C1+ counts, define at least four future C1+ content categories, define the B2-to-C1 sequencing boundary, and keep C1+ at zero as an explicit reported gap rather than omitting the band.

18. `aprende/tools/content-pipeline/lemma_count_sanity.py` must remain the validation gate and must be extended in the later implementation to report and assert total reviewable items, item-type breakdown, CEFR distribution, phrase/chunk distribution by CEFR, on-ramp counts, sequencing integrity, re-banding audit results, C1+ lane reporting, and current-vs-target thresholds.

19. Validation must fail loudly when the curriculum regresses below the accepted A1/A2 on-ramp thresholds, assigns every noun phrase to one band, introduces unreviewed or sourceless content, creates path nodes that depend on not-yet-introduced targets, or fails the re-banding audit threshold.

20. The implementation plan must be phased so the rubric fix, existing-data re-banding, and A1/A2 on-ramp backfill are separable work packages. The on-ramp generation/backfill phase must be its own phase because it is the largest content effort.

21. The plan must name regression-prevention integration tests that run the content pipeline through its real in-service collaborators: content generation/pack construction, review gates, coverage report building, and sanity assertion.

## Constraints

- This task writes planning artifacts only: `SPEC.md` and `PLAN.md`. It must not implement code, change curriculum content, commit, or push.
- The established diagnostic findings in `TASK.md` are accepted inputs and must not be re-litigated as part of this task.
- Python content-pipeline tools live under `<worktree>/aprende/`; later implementation commands must run from that nested package path when appropriate.
- Existing phrase/chunk content is core product material and must be preserved.
- The validator gate in `lemma_count_sanity.py` must be kept and built on, not bypassed or replaced by ad hoc reports.
- New and re-banded content must continue to respect the existing source, license, review, and publish-gate model.
- CEFR labels are approximate curricular bands, not claims of an authoritative open Spanish word-to-CEFR dataset.
- The plan may recommend AI-assisted drafting only if generated rows remain non-shippable until deterministic checks and human or approved review gates promote them to reviewed content.

## Acceptance Criteria

1. `SPEC.md` defines measurable desired end-state requirements for the phrase/chunk rubric, B1 noun-phrase re-banding, A1/A2 on-ramp, sequencing, target CEFR distribution, and validator gates.

2. `PLAN.md` maps every numbered requirement in this spec to an implementation phase or validation gate.

3. `PLAN.md` describes the three required fix areas: rubric fix, existing-data re-banding, and A1/A2 on-ramp backfill plus sequencing.

4. `PLAN.md` defines how the rubric decides A1/A2 versus B1+ for concrete routine phrases versus formal, institutional, abstract, or complex phrase chains.

5. `PLAN.md` defines how existing B1 noun phrases are re-banded safely and verifiably without deleting rows or over-correcting genuine B1 content.

6. `PLAN.md` defines the on-ramp's categories, ordering, approximate counts, single-word versus phrase/chunk mix, and path-threading into the existing curriculum.

7. `PLAN.md` names integration tests and validation commands that would fail if the current blanket-B1 noun-phrase behavior or zero A1/A2 phrase/chunk on-ramp regressed.

8. Robot reviewers sign off on the spec, and independent `pr-validate` validation finds no remaining blocking or should-address spec issues.

9. Robot reviewers sign off on the plan, and independent `pr-validate` validation finds no remaining blocking or should-address plan issues.

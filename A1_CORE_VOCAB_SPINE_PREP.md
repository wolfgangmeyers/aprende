# A1 Core Vocabulary Spine Prep

**Status:** Phase 1 implementation prep.
**Date:** 2026-05-31
**Depends on:** `SPANISH_BREADTH_PLAN.md` Phase 1 and `aprende/tools/content-pipeline/coverage_baseline_snapshot.json`.
**Scope:** Derive the first source-checked A1 pack plan from the Phase 0 coverage report and identify the smallest independently shippable content slice.

## Baseline

The Phase 0 coverage baseline is intentionally honest:

- Raw lexemes: 3
- Learner-ready lexemes: 0
- Reviewed sentences: 2
- Reviewed accepted answers: 3
- Exercises: 2
- Missing A1/A2 gaps: 30

Current rows that exist but are not learner-ready:

| Lemma | Current state | Blockers |
|---|---|---|
| `tener` | reviewed lexeme + 1 reviewed sentence + production exercise | needs 4 reviewed contexts, needs recognition exercise |
| `agua` | reviewed lexeme + 1 reviewed sentence + recognition exercise | needs 2 reviewed contexts, needs production exercise |
| `perro` | reviewed lexeme + 1 reviewed sentence, incidental only | needs 2 reviewed contexts, needs production exercise, needs recognition exercise |

Top missing priority-1 A1 gaps:

| Lemma | Why first | Source basis |
|---|---|---|
| `ser` | identity and description | `SPEC.md` §5.6 A1 `ser`/`estar` |
| `estar` | state and location | `SPEC.md` §5.6 A1 `ser`/`estar` |
| `tener` | possession and needs | `SPEC.md` §5.2 irregular verb table |
| `ir` | movement and near future | `SPEC.md` §5.2 irregular verb table |
| `hacer` | daily actions and weather | `SPEC.md` §5.2 irregular verb table |
| `querer` | wants | `SPEC.md` §5.2 irregular verb table |
| `poder` | ability and permission | `SPEC.md` §5.2 irregular verb table |
| `decir` | reported speech basics | `SPEC.md` §5.2 irregular verb table |
| `saber` | knowledge | `SPEC.md` §5.2 irregular verb table |
| `venir` | movement | `SPEC.md` §5.2 irregular verb table |

## Source Policy

No learning row in this pack is invented. Each shipped row must pass the existing pipeline gate:

- Lexeme/gloss/POS/gender: source from Wiktionary or another explicit redistributable dictionary source.
- Frequency rank/order: source from `hermitdave/FrequencyWords`; treat redistributed rank metadata as `CC-BY-SA-4.0`.
- Sentence pairs and translations: source from Tatoeba `spa-eng` pairs, preferably CC0 where available; otherwise `CC-BY-2.0-FR` with attribution.
- Accepted answers: use source translation first. Authored variants are allowed only as `source=authored`, reviewed by a human, and tracked in the manifest.
- Exercises: derived from reviewed sentences and reviewed target lexemes; no runtime generation.

## A1 Pack Order

This is the implementation order for the first A1 spine. It starts with rows that are already present because completing partially-covered words gives the fastest learner-ready count without schema work.

| Batch | Theme | Target lemmas | Why this order |
|---|---|---|---|
| A1-001 | Existing Basics readiness | `tener`, `agua`, `perro` | Converts existing reviewed rows into learner-ready rows with the smallest content delta. |
| A1-002 | Identity and location | `ser`, `estar`, `persona`, `casa` | Establishes the highest-value A1 distinction and supports basic descriptions. |
| A1-003 | Wants and needs | `querer`, `poder`, `necesitar`, `comida` | Adds usable request/need patterns tied to daily vocabulary. |
| A1-004 | Movement | `ir`, `venir`, `salir`, `llegar` | Supports places, routines, and near-future phrases later. |
| A1-005 | Time and routines | `día`, `tiempo`, `vivir`, `hacer` | Supports daily life and weather/action patterns. |
| A1-006 | Communication | `hablar`, `decir`, `saber`, `ver` | Adds common classroom/question and perception verbs. |
| A1-007 | Family and people | `familia`, `persona` plus kinship nouns after source selection | Expands people topic after core verb coverage is stable. |

Each batch is shippable if every included lexeme becomes learner-ready and the coverage baseline snapshot updates cleanly.

## Learner-Ready Budget

For this Phase 1 prep, use the Phase 0 budget unchanged:

- High-value verb (`pos=verb`, `frequencyRank <= 500`): 4 reviewed sentence contexts plus production and recognition exercises.
- Default lexeme: 2 reviewed sentence contexts plus production and recognition exercises.
- Every sentence must have at least one reviewed accepted answer.
- Every exercise must target exactly one `srs_item` identity.

Do not lower this bar to make a small pack pass. If a word is too expensive to source now, defer the word rather than weakening the readiness definition.

## Smallest Shippable Content Slice

**Slice:** `A1-001 Existing Basics readiness`

**Goal:** turn the current sample's 3 reviewed lexemes into the first 3 learner-ready A1 lexemes.

**Target lemmas:**

| Lemma | Required to ship |
|---|---|
| `tener` | Add 3 more reviewed Tatoeba sentence contexts and at least 1 recognition exercise. |
| `agua` | Add 1 more reviewed Tatoeba sentence context and at least 1 production exercise. |
| `perro` | Add 1 more reviewed Tatoeba sentence context, at least 1 production exercise, and at least 1 recognition exercise. |

**Implemented content delta:**

- 3 new reviewed sentence rows; overlapping `tener`/`perro` and `tener`/`agua` contexts were enough to meet the budget.
- Reviewed accepted answers for every new sentence.
- 4 new exercises:
  - `tener` recognition exercise
  - `agua` production exercise
  - `perro` production exercise
  - `perro` recognition exercise
- Updated `sentence_lexeme` joins for all sentence contexts.
- Updated `coverage_baseline_snapshot.json`.

Source rows used:

| Spanish sentence | Tatoeba Spanish ID | Accepted English answer(s) | English source ID(s) |
|---|---:|---|---|
| `Tengo un perro.` | 755342 | `i have a dog` | 378502 |
| `El agua está fría.` | 1987699 | `the water is cold` | 3422364 |
| `¿Tienes un perro?` | 1195274 | `do you have a dog` | 1195261 |
| `Tiene un perro.` | 5051233 | `he has a dog`; `she has a dog` | 288121; 7425744 |
| `Tengo el agua.` | 3515639 | `i have the water` | 12068868 |

**Dependencies:**

- No schema change.
- No app UI change.
- No grading change.
- No new grammar engine requirement if all exercises use reviewed sentences and existing exercise types.

**Acceptance criteria:**

- `learnerReadyLexemes` increases from 0 to 3.
- `tener`, `agua`, and `perro` have no readiness blockers in `content_coverage.json`.
- `missingA1A2GapCount` decreases by at least 3.
- `--fail-on-coverage-gaps` exits 0 because all currently present A1/A2 lexemes are learner-ready.
- The publish gate still rejects unreviewed rows.

## Next Worker Task

Implement `A1-004 Wants: querer` in the content pipeline sample.

Concrete steps:

1. Add the next smallest priority-1 verb, `querer`, from Wiktionary using the FrequencyWords rank.
2. Find reviewed Tatoeba contexts for the verb.
3. Add the missing `sentence_lexeme` joins and derived exercises.
4. Run the normal pipeline and inspect `content_coverage.json`.
5. Update `coverage_baseline_snapshot.json`.
6. Keep `--inject-unvetted` and `--fail-on-coverage-gaps` behavior intact.

## A1-002 Identity And Location

**Status:** implemented locally after A1-001.

**Goal:** add the two highest-value A1 `to be` verbs, `ser` and `estar`, without schema or UI changes.

**Target lemmas:**

| Lemma | FrequencyWords rank | Source basis | Required to ship |
|---|---:|---|---|
| `ser` | 63 | `SPEC.md` §5.6 A1 `ser`/`estar` | 4 reviewed contexts, production + recognition exercises |
| `estar` | 131 | `SPEC.md` §5.6 A1 `ser`/`estar` | 4 reviewed contexts, production + recognition exercises |

Source rows used:

| Lemma | Spanish sentence | Tatoeba Spanish ID | Accepted English answer | English source ID |
|---|---|---:|---|---:|
| `ser` | `Soy estudiante.` | 574254 | `i'm a student` | 567368 |
| `ser` | `Eres mi amigo.` | 585066 | `you are my friend` | 370562 |
| `ser` | `Esta es mi casa.` | 955676 | `this is my house` | 955157 |
| `ser` | `Soy feliz.` | 627075 | `i'm happy` | 1872056 |
| `estar` | `Estoy en casa.` | 1013884 | `i'm at home` | 404046 |
| `estar` | `Ella está en casa.` | 4848556 | `she is at home` | 4848413 |
| `estar` | `Estoy bien.` | 455952 | `i'm fine` | 257272 |
| `estar` | `Está aquí.` | 2532719 | `it's here` | 2123598 |

Implemented content delta:

- 2 reviewed Wiktionary lexeme rows.
- 8 reviewed Tatoeba sentence rows.
- 8 reviewed Tatoeba accepted-answer rows.
- 8 `sentence_lexeme` joins.
- 4 derived exercises:
  - `ser` production exercise
  - `ser` recognition exercise
  - `estar` production exercise
  - `estar` recognition exercise
- Updated `coverage_baseline_snapshot.json`.

Acceptance result:

- `learnerReadyLexemes` increases from 3 to 5.
- `ser` and `estar` have no readiness blockers in `content_coverage.json`.
- `missingA1A2GapCount` decreases from 28 to 26.
- `--fail-on-coverage-gaps` exits 0.
- The publish gate still rejects unreviewed rows.

## A1-003 Movement: Ir

**Status:** implemented locally after A1-002.

**Goal:** add the next smallest priority-1 verb slice, `ir`, without schema or UI changes.

**Target lemma:**

| Lemma | FrequencyWords rank | Source basis | Required to ship |
|---|---:|---|---|
| `ir` | 128 | `SPEC.md` §5.2 irregular verb table | 4 reviewed contexts, production + recognition exercises |

Source rows used:

| Lemma | Spanish sentence | Tatoeba Spanish ID | Accepted English answer | English source ID |
|---|---|---:|---|---:|
| `ir` | `Vamos a casa.` | 748478 | `we're going home` | 430024 |
| `ir` | `Voy contigo.` | 1050137 | `i am going with you` | 894729 |
| `ir` | `Voy al parque.` | 450251 | `i go to the park` | 257353 |
| `ir` | `Voy a la escuela.` | 473450 | `i go to school` | 472089 |

Implemented content delta:

- 1 reviewed Wiktionary lexeme row.
- 4 reviewed Tatoeba sentence rows.
- 4 reviewed Tatoeba accepted-answer rows.
- 4 `sentence_lexeme` joins.
- 2 derived exercises:
  - `ir` production exercise
  - `ir` recognition exercise
- Updated `coverage_baseline_snapshot.json`.

Acceptance result:

- `learnerReadyLexemes` increases from 5 to 6.
- `ir` has no readiness blockers in `content_coverage.json`.
- `missingA1A2GapCount` decreases from 26 to 25.
- `--fail-on-coverage-gaps` exits 0.
- The publish gate still rejects unreviewed rows.

## A1-004 Wants: Querer

**Status:** implemented locally after A1-003.

**Goal:** add the smallest clean remaining priority-1 verb slice, `querer`, without schema or UI changes.

**Target lemma:**

| Lemma | FrequencyWords rank | Source basis | Required to ship |
|---|---:|---|---|
| `querer` | 1557 | `SPEC.md` §5.2 irregular verb table | 2 reviewed contexts, production + recognition exercises |

Source rows used:

| Lemma | Spanish sentence | Tatoeba Spanish ID | Accepted English answer | English source ID |
|---|---|---:|---|---:|
| `querer` | `Quiero agua.` | 584596 | `i want water` | 5085314 |
| `querer` | `¿Quieres agua?` | 12291005 | `do you want water` | 13225760 |

Implemented content delta:

- 1 reviewed Wiktionary lexeme row.
- 2 reviewed Tatoeba sentence rows.
- 2 reviewed Tatoeba accepted-answer rows.
- 4 `sentence_lexeme` joins (`querer` + existing `agua`).
- 2 derived exercises:
  - `querer` production exercise
  - `querer` recognition exercise
- Updated `coverage_baseline_snapshot.json`.

Acceptance result:

- `learnerReadyLexemes` increases from 6 to 7.
- `querer` has no readiness blockers in `content_coverage.json`.
- `missingA1A2GapCount` decreases from 25 to 24.
- `--fail-on-coverage-gaps` exits 0.
- The publish gate still rejects unreviewed rows.

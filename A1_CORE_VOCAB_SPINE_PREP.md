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

After the `A1-009 Home Food And Family` batch is reviewed and committed, continue with the remaining priority-2 gaps.

Concrete steps:

1. Prefer a 5-10 lexeme source-checked A1 topic pack from the current top gaps: `día`, `hablar`, `persona`, `tiempo`, `ver`, `vivir`.
2. Use Tatoeba/Wiktionary rows where source material is straightforward; keep AI-drafted rows out of learner-ready content unless the AI draft lane is wired and reviewed.
3. Add enough reviewed sentence coverage, accepted answers, `sentence_lexeme` joins, and derived exercises for each included lexeme.
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

## A1-005 Ability: Poder

**Status:** implemented locally after A1-004.

**Goal:** add the next clean priority-1 verb slice, `poder`, without schema or UI changes.

**Target lemma:**

| Lemma | FrequencyWords rank | Source basis | Required to ship |
|---|---:|---|---|
| `poder` | 362 | `SPEC.md` §5.2 irregular verb table | 4 reviewed contexts, production + recognition exercises |

Source rows used:

| Lemma | Spanish sentence | Tatoeba Spanish ID | Accepted English answer | English source ID |
|---|---|---:|---|---:|
| `poder` | `Puedo ir.` | 4521968 | `i can go` | 3092548 |
| `poder` | `Puedo hacerlo.` | 1686297 | `i can do it` | 254742 |
| `poder` | `Puedo venir.` | 10128973 | `i can come` | 2245638 |
| `poder` | `Podemos ir.` | 6811033 | `we can go` | 2241036 |

Implemented content delta:

- 1 reviewed Wiktionary lexeme row.
- 4 reviewed Tatoeba sentence rows.
- 4 reviewed Tatoeba accepted-answer rows.
- 6 `sentence_lexeme` joins (`poder` plus existing `ir` on two rows).
- 2 derived exercises:
  - `poder` production exercise
  - `poder` recognition exercise
- Updated `coverage_baseline_snapshot.json`.

Acceptance result:

- `learnerReadyLexemes` increases from 7 to 8.
- `poder` has no readiness blockers in `content_coverage.json`.
- `missingA1A2GapCount` decreases from 24 to 23.
- `--fail-on-coverage-gaps` exits 0.
- The publish gate still rejects unreviewed rows.

## A1-006 Knowledge: Saber

**Status:** implemented locally after A1-005.

**Goal:** add the next clean priority-1 verb slice, `saber`, without schema or UI changes.

**Target lemma:**

| Lemma | FrequencyWords rank | Source basis | Required to ship |
|---|---:|---|---|
| `saber` | 236 | `SPEC.md` §5.2 irregular verb table | 4 reviewed contexts, production + recognition exercises |

Source rows used:

| Lemma | Spanish sentence | Tatoeba Spanish ID | Accepted English answer | English source ID |
|---|---|---:|---|---:|
| `saber` | `Lo sé.` | 435153 | `i know` | 319990 |
| `saber` | `No sé.` | 376608 | `i don't know` | 349064 |
| `saber` | `Quiero saberlo.` | 961279 | `i want to know` | 961147 |
| `saber` | `Sabemos.` | 5265434 | `we know` | 1556167 |

Implemented content delta:

- 1 reviewed Wiktionary lexeme row.
- 4 reviewed Tatoeba sentence rows.
- 4 reviewed Tatoeba accepted-answer rows.
- 5 `sentence_lexeme` joins (`saber` plus existing `querer` on one row).
- 2 derived exercises:
  - `saber` production exercise
  - `saber` recognition exercise
- Updated `coverage_baseline_snapshot.json`.

Acceptance result:

- `learnerReadyLexemes` increases from 8 to 9.
- `saber` has no readiness blockers in `content_coverage.json`.
- `missingA1A2GapCount` decreases from 23 to 22.
- `--fail-on-coverage-gaps` exits 0.
- The publish gate still rejects unreviewed rows.

## A1-007 Movement: Venir

**Status:** implemented locally after A1-006.

**Goal:** add the next clean priority-1 movement verb slice, `venir`, without schema or UI changes.

**Target lemma:**

| Lemma | FrequencyWords rank | Source basis | Required to ship |
|---|---:|---|---|
| `venir` | 339 | `SPEC.md` §5.2 irregular verb table | 4 reviewed contexts, production + recognition exercises |

Source rows used:

| Lemma | Spanish sentence | Tatoeba Spanish ID | Accepted English answer | English source ID |
|---|---|---:|---|---:|
| `venir` | `Ven aquí.` | 374136 | `come here` | 39944 |
| `venir` | `¿Vienes?` | 2194085 | `are you coming` | 1417464 |
| `venir` | `Vienen.` | 2008142 | `they're coming` | 1898128 |
| `venir` | `Ven a casa.` | 3873833 | `come home` | 413767 |

Implemented content delta:

- 1 reviewed Wiktionary lexeme row.
- 4 reviewed Tatoeba sentence rows.
- 4 reviewed Tatoeba accepted-answer rows.
- 4 `sentence_lexeme` joins.
- 2 derived exercises:
  - `venir` production exercise
  - `venir` recognition exercise
- Updated `coverage_baseline_snapshot.json`.

Acceptance result:

- `learnerReadyLexemes` increases from 9 to 10.
- `venir` has no readiness blockers in `content_coverage.json`.
- `missingA1A2GapCount` decreases from 22 to 21.
- `--fail-on-coverage-gaps` exits 0.
- The publish gate still rejects unreviewed rows.

## A1-008 Priority-1 Verb Closeout: Hacer And Decir

**Status:** implemented locally after A1-007.

**Goal:** add the remaining clean priority-1 verb slice, `hacer` and `decir`, without schema or UI changes.

**Target lemmas:**

| Lemma | FrequencyWords rank | Source basis | Required to ship |
|---|---:|---|---|
| `hacer` | 68 | `SPEC.md` §5.2 irregular verb table | 4 reviewed contexts, production + recognition exercises |
| `decir` | 111 | `SPEC.md` §5.2 irregular verb table | 4 reviewed contexts, production + recognition exercises |

Source rows used:

| Lemma | Spanish sentence | Tatoeba Spanish ID | Accepted English answer | English source ID |
|---|---|---:|---|---:|
| `hacer` | `¿Qué haces?` | 4052592 | `what are you doing` | 16492 |
| `hacer` | `Puedo hacerlo.` | 1686297 | `i can do it` | 254742 |
| `hacer` | `Hace frío.` | 2926 | `it's cold` | 1813 |
| `hacer` | `Hace calor.` | 456142 | `it's hot` | 423405 |
| `decir` | `Dime.` | 5044120 | `tell me` | 1913090 |
| `decir` | `Dime todo.` | 1216387 | `tell me everything` | 1216330 |
| `decir` | `¿Qué dices?` | 941802 | `what do you say` | 1174872 |
| `decir` | `Dígame la verdad.` | 571886 | `tell me the truth` | 321441 |

Implemented content delta:

- 2 reviewed Wiktionary lexeme rows.
- 8 reviewed Tatoeba sentence rows.
- 8 reviewed Tatoeba accepted-answer rows.
- 9 `sentence_lexeme` joins (`hacer` plus existing `poder` on one row).
- 4 derived exercises:
  - `hacer` production exercise
  - `hacer` recognition exercise
  - `decir` production exercise
  - `decir` recognition exercise
- Updated `coverage_baseline_snapshot.json`.

Acceptance result:

- `learnerReadyLexemes` increases from 10 to 12.
- `hacer` and `decir` have no readiness blockers in `content_coverage.json`.
- `missingA1A2GapCount` decreases from 21 to 19.
- `--fail-on-coverage-gaps` exits 0.
- The publish gate still rejects unreviewed rows.

## A1-009 Home Food And Family

**Status:** implemented locally after A1-008.

**Goal:** add the first larger source-checked A1 topic pack from priority-2 gaps, without AI-drafted shipping rows.

**Target lemmas:**

| Lemma | FrequencyWords rank | Source basis | Required to ship |
|---|---:|---|---|
| `casa` | 91 | `SPANISH_BREADTH_PLAN.md` Phase 1 home topic | 2+ reviewed contexts, production + recognition exercises |
| `comida` | 483 | `SPANISH_BREADTH_PLAN.md` Phase 1 food topic | 2+ reviewed contexts, production + recognition exercises |
| `comer` | 488 | `SPANISH_BREADTH_PLAN.md` Phase 1 food topic | 4 reviewed contexts, production + recognition exercises |
| `beber` | 1053 | `SPANISH_BREADTH_PLAN.md` Phase 1 food topic | 4 reviewed contexts, production + recognition exercises |
| `familia` | 254 | `SPANISH_BREADTH_PLAN.md` Phase 1 people topic | 2+ reviewed contexts, production + recognition exercises |

Source rows used:

| Lemma | Spanish sentence | Tatoeba Spanish ID | Accepted English answer | English source ID |
|---|---|---:|---|---:|
| `casa` | `Esta es mi casa.` | 955676 | `this is my house` | 955157 |
| `casa` | `Estoy en casa.` | 1013884 | `i'm at home` | 404046 |
| `casa` | `Vamos a casa.` | 748478 | `we're going home` | 430024 |
| `casa` | `Ven a casa.` | 3873833 | `come home` | 413767 |
| `comida` | `La comida está buena.` | 2002676 | `the food is good` | 2002528 |
| `comida` | `No tengo comida.` | 3600572 | `i have no food` | 2549665 |
| `comer` | `Come.` | 6702001 | `he eats` | 6702018 |
| `comer` | `Comemos.` | 6702002 | `we eat` | 3845194 |
| `comer` | `Comen.` | 6702004 | `they eat` | 3845203 |
| `comer` | `¿Quieres comer?` | 1493376 | `do you want to eat` | 773323 |
| `beber` | `Bebo agua.` | 5745781 | `i drink water` | 7932256 |
| `beber` | `Bebemos agua.` | 4386719 | `we drink water` | 4385215 |
| `beber` | `Bebes agua.` | 10496384 | `you drink water` | 7189457 |
| `beber` | `Bebe agua.` | 7562545 | `he drinks water` | 4870686 |
| `familia` | `Son familia.` | 6600079 | `they're family` | 2242977 |
| `familia` | `¿Tienes familia?` | 730296 | `do you have a family` | 54499 |

Implemented content delta:

- 5 reviewed Wiktionary lexeme rows.
- 12 reviewed Tatoeba sentence rows, plus 4 reused reviewed Tatoeba `casa` contexts.
- 12 reviewed Tatoeba accepted-answer rows.
- 25 `sentence_lexeme` joins, including existing-word joins for `estar`, `tener`, `querer`, and `agua`.
- 10 derived exercises:
  - production and recognition exercises for `casa`, `comida`, `comer`, `beber`, and `familia`
- Updated `coverage_baseline_snapshot.json`.

Acceptance result:

- `learnerReadyLexemes` increases from 12 to 17.
- `casa`, `comida`, `comer`, `beber`, and `familia` have no readiness blockers in `content_coverage.json`.
- `missingA1A2GapCount` decreases from 19 to 14.
- `--fail-on-coverage-gaps` exits 0.
- The publish gate still rejects unreviewed rows.
- No `AI_DRAFT` rows are included in shipped content.

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

After the `A2-001 Shopping School Work And Travel` batch is reviewed and committed, expand the audited target list before the next content pack.

Concrete steps:

1. Add the next reviewed target lemmas to `A1_A2_TARGET_LEMMAS` from the canonical frequency spine and Phase 1/3 topics.
2. Prefer a 5-10 lexeme source-checked pack where Tatoeba/Wiktionary material is straightforward.
3. Keep AI-drafted rows out of learner-ready content unless the AI draft lane is wired and reviewed.
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

## A1-010 Time People Communication And Living

**Status:** implemented locally after A1-009.

**Goal:** close the remaining priority-2 A1 gaps with a larger source-checked topic pack, without AI-drafted shipping rows.

**Target lemmas:**

| Lemma | FrequencyWords rank | Source basis | Required to ship |
|---|---:|---|---|
| `día` | 134 | `SPANISH_BREADTH_PLAN.md` Phase 1 time topic | 2+ reviewed contexts, production + recognition exercises |
| `hablar` | 154 | `SPANISH_BREADTH_PLAN.md` Phase 1 questions topic | 4 reviewed contexts, production + recognition exercises |
| `persona` | 310 | `SPANISH_BREADTH_PLAN.md` Phase 1 people topic | 2+ reviewed contexts, production + recognition exercises |
| `tiempo` | 95 | `SPANISH_BREADTH_PLAN.md` Phase 1 time/weather topic | 2+ reviewed contexts, production + recognition exercises |
| `ver` | 120 | hermitdave/FrequencyWords high-frequency spine | 4 reviewed contexts, production + recognition exercises |
| `vivir` | 454 | `SPANISH_BREADTH_PLAN.md` Phase 1 home/routines topic | 4 reviewed contexts, production + recognition exercises |

Source rows used:

| Lemma | Spanish sentence | Tatoeba Spanish ID | Accepted English answer | English source ID |
|---|---|---:|---|---:|
| `día` | `¡Buen día!` | 855394 | `good day` | 855284 |
| `día` | `Buenos días.` | 2258235 | `good morning` | 2258234 |
| `hablar` | `Hablo español.` | 2011085 | `i speak spanish` | 1755331 |
| `hablar` | `¿Hablas español?` | 1550980 | `do you speak spanish` | 719306 |
| `hablar` | `Todos hablamos español.` | 6003088 | `we all speak spanish` | 6003093 |
| `hablar` | `También hablo español.` | 10480474 | `i also speak spanish` | 10573599 |
| `persona` | `¿Cuántas personas?` | 3582800 | `how many people` | 24515 |
| `persona` | `Somos personas.` | 1408294 | `we are people` | 671753 |
| `persona` | `Eres buena persona.` | 4958553 | `you're a good person` | 2547447 |
| `tiempo` | `Hace buen tiempo.` | 1215730 | `the weather is good` | 1766700 |
| `tiempo` | `Tengo tiempo.` | 4859590 | `i have time` | 2245901 |
| `tiempo` | `Necesitamos tiempo.` | 9706925 | `we need time` | 2241424 |
| `ver` | `Veo algo.` | 9706879 | `i see something` | 2247403 |
| `ver` | `Veo esto.` | 1732156 | `i see this` | 871792 |
| `ver` | `Quiero ver tu casa.` | 9884000 | `i want to see your house` | 2396149 |
| `ver` | `¿Puedes ver?` | 1748229 | `can you see` | 1553530 |
| `vivir` | `Vivo cerca.` | 11160801 | `i live nearby` | 3565068 |
| `vivir` | `Vive aquí.` | 11035294 | `he lives here` | 5143986 |
| `vivir` | `Vivimos aquí.` | 6694248 | `we live here` | 2549740 |
| `vivir` | `¿Viven aquí?` | 894294 | `do you live here` | 15882 |

Implemented content delta:

- 6 reviewed Wiktionary lexeme rows.
- 20 reviewed Tatoeba sentence rows.
- 20 reviewed Tatoeba accepted-answer rows.
- 25 `sentence_lexeme` joins, including existing-word joins for `ser`, `hacer`, `tener`, `querer`, `casa`, and `poder`.
- 12 derived exercises:
  - production and recognition exercises for `día`, `hablar`, `persona`, `tiempo`, `ver`, and `vivir`
- Updated `coverage_baseline_snapshot.json`.

Acceptance result:

- `learnerReadyLexemes` increases from 17 to 23.
- `día`, `hablar`, `persona`, `tiempo`, `ver`, and `vivir` have no readiness blockers in `content_coverage.json`.
- `missingA1A2GapCount` decreases from 14 to 8.
- `--fail-on-coverage-gaps` exits 0.
- The publish gate still rejects unreviewed rows.
- No `AI_DRAFT` rows are included in shipped content.

## A2-001 Shopping School Work And Travel

**Status:** implemented locally after A1-010.

**Goal:** close the current A2 priority-3 gaps with a source-checked pack, without AI-drafted shipping rows.

**Target lemmas:**

| Lemma | FrequencyWords rank | Source basis | Required to ship |
|---|---:|---|---|
| `comprar` | 818 | `SPANISH_BREADTH_PLAN.md` Phase 3 shopping topic | 4 reviewed contexts, production + recognition exercises |
| `dinero` | 164 | `SPANISH_BREADTH_PLAN.md` Phase 3 shopping/money topic | 2+ reviewed contexts, production + recognition exercises |
| `escuela` | 463 | `SPANISH_BREADTH_PLAN.md` Phase 3 work/school topic | 2+ reviewed contexts, production + recognition exercises |
| `llegar` | 400 | `SPANISH_BREADTH_PLAN.md` Phase 3 travel/time topic | 4 reviewed contexts, production + recognition exercises |
| `necesitar` | 1692 | `SPANISH_BREADTH_PLAN.md` Phase 3 wants/needs topic | 4 reviewed contexts, production + recognition exercises |
| `salir` | 265 | `SPANISH_BREADTH_PLAN.md` Phase 3 travel/plans topic | 4 reviewed contexts, production + recognition exercises |
| `trabajo` | 142 | `SPANISH_BREADTH_PLAN.md` Phase 3 work/school topic | 2+ reviewed contexts, production + recognition exercises |
| `viajar` | 2530 | `SPANISH_BREADTH_PLAN.md` Phase 3 travel topic | 4 reviewed contexts, production + recognition exercises |

Source rows used:

| Lemma | Spanish sentence | Tatoeba Spanish ID | Accepted English answer | English source ID |
|---|---|---:|---|---:|
| `comprar` | `Compramos.` | 7947364 | `we buy` | 5617573 |
| `comprar` | `¡Compra!` | 7936806 | `buy` | 6046859 |
| `comprar` | `Compraré comida.` | 13917468 | `i'll buy food` | 8918033 |
| `comprar` | `Quiero comprar comida.` | 2707615 | `i want to buy food` | 2669111 |
| `dinero` | `Tenemos dinero.` | 9943356 | `we have money` | 9943118 |
| `dinero` | `Tienes dinero.` | 7931127 | `you have money` | 9311597 |
| `dinero` | `Quiero dinero.` | 4456338 | `i want money` | 64620 |
| `escuela` | `Esta es mi escuela.` | 1258453 | `this is my school` | 1255406 |
| `escuela` | `Odio la escuela.` | 9443867 | `i hate school` | 4747564 |
| `escuela` | `Voy a la escuela.` | 473450 | `i go to school` | 472089 |
| `llegar` | `Llegaré.` | 9763982 | `i will arrive` | 12556195 |
| `llegar` | `Llegué.` | 6161281 | `i've arrived` | 4008734 |
| `llegar` | `Llegamos.` | 6063763 | `we've arrived` | 410594 |
| `llegar` | `Llegó.` | 6063762 | `she arrived` | 6917619 |
| `necesitar` | `Necesito miel.` | 13665656 | `i need honey` | 11900237 |
| `necesitar` | `Necesita practicar.` | 13660778 | `he needs to practice` | 9182157 |
| `necesitar` | `¿Necesitas descansar?` | 13711743 | `do you need to rest` | 13711740 |
| `necesitar` | `Necesitamos expertos.` | 13789665 | `we need experts` | 2241414 |
| `salir` | `Salgo.` | 10262252 | `i'm leaving` | 350133 |
| `salir` | `Salgamos.` | 2008990 | `let's go out` | 2007927 |
| `salir` | `Nunca salgo.` | 7160137 | `i never go out` | 3728879 |
| `salir` | `Salí.` | 630772 | `i left` | 2307509 |
| `trabajo` | `Odio mi trabajo.` | 858287 | `i hate my job` | 874052 |
| `trabajo` | `Es mi trabajo.` | 1306030 | `it's my job` | 433521 |
| `trabajo` | `Mi trabajo es seguro.` | 11405515 | `my job is safe` | 3238932 |
| `viajar` | `Viajé.` | 5028966 | `i traveled` | 10954562 |
| `viajar` | `¿Viajas mucho?` | 10459407 | `do you travel a lot` | 29911 |
| `viajar` | `Viajé a Boston.` | 5752610 | `i traveled to boston` | 2280316 |
| `viajar` | `Viajo a menudo.` | 995130 | `i travel often` | 465459 |

Implemented content delta:

- 8 reviewed Wiktionary lexeme rows.
- 29 reviewed Tatoeba sentence rows.
- 29 reviewed Tatoeba accepted-answer rows.
- 38 `sentence_lexeme` joins, including existing-word joins for `comida`, `querer`, `tener`, `ser`, and `ir`.
- 16 derived exercises:
  - production and recognition exercises for `comprar`, `dinero`, `escuela`, `llegar`, `necesitar`, `salir`, `trabajo`, and `viajar`
- Updated `coverage_baseline_snapshot.json`.

Acceptance result:

- `learnerReadyLexemes` increases from 23 to 31.
- All current `A1_A2_TARGET_LEMMAS` have no readiness blockers in `content_coverage.json`.
- `missingA1A2GapCount` decreases from 8 to 0.
- `--fail-on-coverage-gaps` exits 0.
- The publish gate still rejects unreviewed rows.
- No `AI_DRAFT` rows are included in shipped content.

## A2-002 Practical Transport Shopping Body And Descriptors

**Status:** implemented locally after coverage-readiness exercise validation.

**Goal:** expand everyday fluency breadth with a larger generated-content pack, using the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane instead of live Tatoeba
validation.

**Target lemmas:**

| Lemma | FrequencyWords rank | Source basis | Required to ship |
|---|---:|---|---|
| `coche` | 408 | `SPANISH_BREADTH_PLAN.md` Phase 3 transport topic | 2+ reviewed contexts, production + recognition exercises |
| `autobús` | 1702 | `SPANISH_BREADTH_PLAN.md` Phase 3 transport topic | 2+ reviewed contexts, production + recognition exercises |
| `tienda` | 817 | `SPANISH_BREADTH_PLAN.md` Phase 3 shopping topic | 2+ reviewed contexts, production + recognition exercises |
| `precio` | 1230 | `SPANISH_BREADTH_PLAN.md` Phase 3 shopping/money topic | 2+ reviewed contexts, production + recognition exercises |
| `mano` | 373 | `SPANISH_BREADTH_PLAN.md` Phase 3 health/body topic | 2+ reviewed contexts, production + recognition exercises |
| `cabeza` | 274 | `SPANISH_BREADTH_PLAN.md` Phase 3 health/body topic | 2+ reviewed contexts, production + recognition exercises |
| `bueno` | 50 | `hermitdave/FrequencyWords` high-frequency spine | 2+ reviewed contexts, production + recognition exercises |
| `malo` | 476 | `hermitdave/FrequencyWords` high-frequency spine | 2+ reviewed contexts, production + recognition exercises |
| `rápido` | 311 | `hermitdave/FrequencyWords` high-frequency spine | 2+ reviewed contexts, production + recognition exercises |
| `grande` | 398 | `hermitdave/FrequencyWords` high-frequency spine | 2+ reviewed contexts, production + recognition exercises |

Generated rows and automatic review evidence:

| Lemma | Spanish sentence | Draft source ID | Accepted English answer | Review evidence |
|---|---|---|---|---|
| `coche` | `¿Tienes coche?` | `ai_draft:a2-002-coche-1` | `do you have a car` | `spanish_correctness_naturalness`, `english_pedagogy_cefr` |
| `coche` | `Quiero un coche.` | `ai_draft:a2-002-coche-2` | `i want a car` | `spanish_correctness_naturalness`, `english_pedagogy_cefr` |
| `autobús` | `Vayamos en autobús.` | `ai_draft:a2-002-autobus-1` | `let's go by bus` | `spanish_correctness_naturalness`, `english_pedagogy_cefr` |
| `autobús` | `Ella viajó en autobús.` | `ai_draft:a2-002-autobus-2` | `she traveled by bus` | `spanish_correctness_naturalness`, `english_pedagogy_cefr` |
| `tienda` | `Odio esta tienda.` | `ai_draft:a2-002-tienda-1` | `i hate this store` | `spanish_correctness_naturalness`, `english_pedagogy_cefr` |
| `tienda` | `Cerraron la tienda.` | `ai_draft:a2-002-tienda-2` | `they closed the shop` | `spanish_correctness_naturalness`, `english_pedagogy_cefr` |
| `precio` | `Mira el precio.` | `ai_draft:a2-002-precio-1` | `look at the price` | `spanish_correctness_naturalness`, `english_pedagogy_cefr` |
| `precio` | `El precio subió.` | `ai_draft:a2-002-precio-2` | `the price rose` | `spanish_correctness_naturalness`, `english_pedagogy_cefr` |
| `mano` | `Lavémonos las manos.` | `ai_draft:a2-002-mano-1` | `let's wash our hands` | `spanish_correctness_naturalness`, `english_pedagogy_cefr` |
| `mano` | `Toma mi mano.` | `ai_draft:a2-002-mano-2` | `take my hand` | `spanish_correctness_naturalness`, `english_pedagogy_cefr` |
| `cabeza` | `¡Usa la cabeza!` | `ai_draft:a2-002-cabeza-1` | `use your head` | `spanish_correctness_naturalness`, `english_pedagogy_cefr` |
| `cabeza` | `Me duele la cabeza.` | `ai_draft:a2-002-cabeza-2` | `my head hurts` | `spanish_correctness_naturalness`, `english_pedagogy_cefr` |
| `bueno` | `La comida está buena.` | `tatoeba:2002676` | `the food is good` | previously reviewed source row |
| `bueno` | `Eres buena persona.` | `tatoeba:4958553` | `you're a good person` | previously reviewed source row |
| `bueno` | `Hace buen tiempo.` | `tatoeba:1215730` | `the weather is good` | previously reviewed source row |
| `malo` | `¿Es malo?` | `ai_draft:a2-002-malo-1` | `is it bad` | `spanish_correctness_naturalness`, `english_pedagogy_cefr` |
| `malo` | `Son malos.` | `ai_draft:a2-002-malo-2` | `they're bad` | `spanish_correctness_naturalness`, `english_pedagogy_cefr` |
| `rápido` | `¡Rápido!` | `ai_draft:a2-002-rapido-1` | `quick` | `spanish_correctness_naturalness`, `english_pedagogy_cefr` |
| `rápido` | `Comí rápido.` | `ai_draft:a2-002-rapido-2` | `i ate quickly` | `spanish_correctness_naturalness`, `english_pedagogy_cefr` |
| `grande` | `Es grande.` | `ai_draft:a2-002-grande-1` | `it's big` | `spanish_correctness_naturalness`, `english_pedagogy_cefr` |
| `grande` | `¿Son grandes?` | `ai_draft:a2-002-grande-2` | `are they big` | `spanish_correctness_naturalness`, `english_pedagogy_cefr` |

Implemented content delta:

- 10 reviewed Wiktionary lexeme rows.
- 18 new `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers, plus existing reviewed rows reused for `bueno`.
- 18 new `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 25 `sentence_lexeme` joins, including existing-word joins for `tener`, `querer`, `viajar`, `ser`, and `comer`.
- 20 derived exercises:
  - production and recognition exercises for `coche`, `autobús`, `tienda`, `precio`, `mano`, `cabeza`, `bueno`, `malo`, `rápido`, and `grande`

Acceptance result:

- `learnerReadyLexemes` increases from 31 to 41.
- All current `A1_A2_TARGET_LEMMAS` have no readiness blockers in `content_coverage.json`.
- `missingA1A2GapCount` remains 0 after adding the priority-4 pack.
- `--fail-on-coverage-gaps` exits 0.
- The publish gate still rejects unreviewed rows.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 36 generated content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s `autoReviewLedger`.

## A2-003 Accelerated Practical Fluency Pack

**Status:** implemented locally after A2-002.

**Goal:** use the `AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane for a larger
high-frequency practical batch, emphasizing verbs, adjectives/adverbs, and daily-life nouns.

**Target lemmas:**

| Lemma | FrequencyWords rank | POS | Domain |
|---|---:|---|---|
| `ayudar` | 1088 | verb | help and requests |
| `trabajar` | 846 | verb | work routines |
| `aprender` | 1788 | verb | learning |
| `escuchar` | 1037 | verb | communication |
| `pagar` | 1007 | verb | shopping and errands |
| `abrir` | 664 | verb | daily actions |
| `cerrar` | 1105 | verb | daily actions |
| `fácil` | 814 | adjective | common description |
| `difícil` | 938 | adjective | common description |
| `cerca` | 433 | adverb | location |
| `lejos` | 1565 | adverb | location |
| `siempre` | 171 | adverb | frequency and routines |
| `nunca` | 446 | adverb | frequency and routines |
| `ahora` | 92 | adverb | time and immediacy |
| `luego` | 505 | adverb | time sequencing |
| `calle` | 590 | noun | directions and errands |
| `puerta` | 852 | noun | home and errands |
| `mesa` | 1443 | noun | home and food |
| `teléfono` | 1856 | noun | daily communication |
| `pregunta` | 760 | noun | learning and clarification |

Generated rows and automatic review evidence:

| Lemma | Spanish sentence 1 | Spanish sentence 2 |
|---|---|---|
| `ayudar` | `Quiero ayudar.` | `¿Puedes ayudarme?` |
| `trabajar` | `Trabajo hoy.` | `Ella trabaja aquí.` |
| `aprender` | `Aprendo español.` | `Quiero aprender más.` |
| `escuchar` | `Escucho música.` | `¿Puedes escuchar?` |
| `pagar` | `Pago ahora.` | `Quiero pagar.` |
| `abrir` | `Abre la puerta.` | `Quiero abrir la puerta.` |
| `cerrar` | `Cierra la puerta.` | `Necesito cerrar la tienda.` |
| `fácil` | `Es fácil.` | `La pregunta es fácil.` |
| `difícil` | `Es difícil.` | `El trabajo es difícil.` |
| `cerca` | `La tienda está cerca.` | `Estoy cerca.` |
| `lejos` | `Vivo lejos.` | `La escuela está lejos.` |
| `siempre` | `Siempre trabajo.` | `Siempre quiero agua.` |
| `nunca` | `Nunca pago tarde.` | `Nunca trabajo aquí.` |
| `ahora` | `Necesito agua ahora.` | `Estoy aquí ahora.` |
| `luego` | `Te veo luego.` | `Trabajo luego.` |
| `calle` | `Vivo en esta calle.` | `La tienda está en esta calle.` |
| `puerta` | `La puerta está abierta.` | `La puerta está cerrada.` |
| `mesa` | `La comida está en la mesa.` | `La mesa es grande.` |
| `teléfono` | `Necesito mi teléfono.` | `El teléfono está en la mesa.` |
| `pregunta` | `Tengo una pregunta.` | `La pregunta es importante.` |

Implemented content delta:

- 20 reviewed Wiktionary lexeme rows.
- 40 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 40 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 40 `sentence_lexeme` joins.
- 40 derived exercises:
  - production and recognition exercises for all 20 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 41 to 61.
- `reviewedSentences` increases from 118 to 158.
- `reviewedAcceptedAnswers` increases from 121 to 161.
- `exerciseCount` increases from 82 to 122.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 80 generated content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s `autoReviewLedger`.
- FrequencyWords rank metadata is exposed in the shipped `content.db` attribution path via
  `content_attribution` as `frequencywords` / `CC-BY-SA-4.0`, so the app credits screen can
  render the frequency-spine license alongside row-level content sources.

## A2-004 Accelerated Daily Fluency Pack

**Status:** implemented locally after A2-003.

**Goal:** expand practical fluency with a larger generated pack of high-frequency daily verbs,
adjectives/adverbs, and life nouns. Rows use the `AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED ->
REVIEWED` lane with two independent automatic reviewers.

**Target lemmas:**

| Lemma | POS | Domain |
|---|---|---|
| `buscar` | verb | finding and errands |
| `encontrar` | verb | finding and errands |
| `pensar` | verb | thoughts and opinions |
| `entender` | verb | clarification and learning |
| `recordar` | verb | memory and plans |
| `esperar` | verb | waiting and plans |
| `mirar` | verb | perception and directions |
| `llevar` | verb | movement and possessions |
| `tomar` | verb | food, drink, and transport |
| `entrar` | verb | movement and errands |
| `pasar` | verb | movement and events |
| `volver` | verb | movement and routines |
| `empezar` | verb | time sequencing |
| `terminar` | verb | time sequencing |
| `cambiar` | verb | daily changes and plans |
| `pequeño` | adjective | common description |
| `nuevo` | adjective | common description |
| `viejo` | adjective | common description |
| `mismo` | adjective | comparison |
| `primero` | adjective/adverb | sequencing |
| `último` | adjective | sequencing |
| `mejor` | adjective/adverb | comparison and health state |
| `peor` | adjective/adverb | comparison and health state |
| `temprano` | adverb | time and routines |
| `tarde` | adverb/noun | time and routines |
| `ciudad` | noun | places and travel |
| `país` | noun | places and identity |
| `amigo` | noun | relationships |
| `niño` | noun | people and family |
| `mujer` | noun | people and relationships |

Implemented content delta:

- 30 reviewed Wiktionary lexeme rows.
- 74 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 74 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 74 `sentence_lexeme` joins.
- 60 derived exercises:
  - production and recognition exercises for all 30 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 61 to 91.
- `reviewedSentences` increases from 158 to 232.
- `reviewedAcceptedAnswers` increases from 161 to 235.
- `exerciseCount` increases from 122 to 182.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 148 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-005 Accelerated Fluency Pack

**Status:** implemented locally after A2-004.

**Goal:** expand practical travel, health, social, household, and work fluency with a larger
generated pack. Rows use the `AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with
two independent automatic reviewers.

**Target lemmas:**

| Lemma | POS | Domain |
|---|---|---|
| `reservar` | verb | travel bookings |
| `cancelar` | verb | travel and appointment changes |
| `llamar` | verb | phone and health communication |
| `preguntar` | verb | questions and help |
| `responder` | verb | communication |
| `enviar` | verb | work and social communication |
| `recibir` | verb | work and household communication |
| `usar` | verb | tools and daily tasks |
| `limpiar` | verb | household routines |
| `cocinar` | verb | food and household routines |
| `descansar` | verb | health and routines |
| `dormir` | verb | health and routines |
| `sentir` | verb | health and feelings |
| `doler` | verb | health symptoms |
| `cuidar` | verb | health, home, and family care |
| `visitar` | verb | travel and social plans |
| `conocer` | verb | people, places, and introductions |
| `compartir` | verb | social and household interaction |
| `preparar` | verb | work, food, and travel preparation |
| `seguir` | verb | directions and continuing actions |
| `cerca` | adverb | location and travel |
| `lejos` | adverb | location and travel |
| `ocupado` | adjective | work and availability |
| `libre` | adjective | availability and plans |
| `enfermo` | adjective | health state |
| `sano` | adjective | health state |
| `limpio` | adjective | household description |
| `sucio` | adjective | household description |
| `seguro` | adjective | travel safety and confidence |
| `listo` | adjective | readiness and routines |
| `hotel` | noun | travel lodging |
| `aeropuerto` | noun | travel transit |
| `tren` | noun | transport |
| `médico` | noun | health services |
| `oficina` | noun | workplace |

Implemented content delta:

- 35 reviewed Wiktionary lexeme rows.
- 76 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 76 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 76 `sentence_lexeme` joins.
- 70 derived exercises:
  - production and recognition exercises for all 35 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 91 to 126.
- `reviewedSentences` increases from 232 to 308.
- `reviewedAcceptedAnswers` increases from 235 to 311.
- `exerciseCount` increases from 182 to 252.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 152 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-006 Accelerated B1-Bridge Fluency Pack

**Status:** implemented locally after A2-005.

**Goal:** extend breadth toward B1 with opinions, emotions, errands, appointments, food prep,
directions, services, and problem-solving language. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:**

| Lemma | POS | Domain |
|---|---|---|
| `creer` | verb | opinions and uncertainty |
| `opinar` | verb | opinions |
| `preferir` | verb | preferences and choices |
| `decidir` | verb | plans and choices |
| `explicar` | verb | clarifying problems |
| `avisar` | verb | appointments and problems |
| `confirmar` | verb | appointments and bookings |
| `arreglar` | verb | problems and repairs |
| `quejarse` | verb | services and problems |
| `solucionar` | verb | problems |
| `elegir` | verb | choices and services |
| `probar` | verb | food and testing solutions |
| `añadir` | verb | food preparation and details |
| `mezclar` | verb | food preparation |
| `calentar` | verb | food preparation |
| `freír` | verb | food preparation |
| `hervir` | verb | food preparation |
| `girar` | verb | directions |
| `cruzar` | verb | directions and travel |
| `subir` | verb | directions and transport |
| `bajar` | verb | directions and transport |
| `perder` | verb | travel and problems |
| `olvidar` | verb | problems and appointments |
| `dejar` | verb | errands, permission, and problems |
| `importante` | adjective | opinions and priorities |
| `posible` | adjective | plans and problem solving |
| `necesario` | adjective | needs and services |
| `urgente` | adjective | health and service problems |
| `grave` | adjective | health and problems |
| `fácil` | adjective | opinions and difficulty |
| `difícil` | adjective | opinions and difficulty |
| `molesto` | adjective | emotions and complaints |
| `claramente` | adverb | explaining opinions |
| `problema` | noun | problems and services |
| `cita` | noun | appointments |
| `servicio` | noun | services and complaints |
| `receta` | noun | food prep and health |
| `ingrediente` | noun | food preparation |
| `esquina` | noun | directions |
| `puente` | noun | directions and travel |

Implemented content delta:

- 40 reviewed Wiktionary lexeme rows.
- 84 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 84 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 84 `sentence_lexeme` joins.
- 80 derived exercises:
  - production and recognition exercises for all 40 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 126 to 166.
- `reviewedSentences` increases from 308 to 392.
- `reviewedAcceptedAnswers` increases from 311 to 395.
- `exerciseCount` increases from 252 to 332.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 168 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-007 Accelerated B1 Breadth Pack

**Status:** implemented locally after A2-006.

**Goal:** expand B1 practical breadth for experiences, plans, reasons, preferences, requests,
complaints, health, travel, work, household tasks, and services. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:**

| Lemma | POS | Domain |
|---|---|---|
| `lavar` | verb | household and health routines |
| `secar` | verb | household and health routines |
| `ordenar` | verb | household and errands |
| `recoger` | verb | errands and household tasks |
| `tirar` | verb | household and problems |
| `apagar` | verb | household and services |
| `encender` | verb | household and services |
| `reparar` | verb | services and problems |
| `atender` | verb | services and appointments |
| `cobrar` | verb | services and money |
| `firmar` | verb | appointments and services |
| `solicitar` | verb | requests and services |
| `aceptar` | verb | requests and decisions |
| `rechazar` | verb | requests and complaints |
| `recomendar` | verb | preferences and services |
| `prometer` | verb | plans and social commitments |
| `planificar` | verb | plans and work |
| `proponer` | verb | opinions and plans |
| `justificar` | verb | reasons and explanations |
| `depender` | verb | reasons and conditions |
| `causar` | verb | reasons and problems |
| `disfrutar` | verb | experiences and preferences |
| `sufrir` | verb | health and difficult experiences |
| `respirar` | verb | health symptoms |
| `toser` | verb | health symptoms |
| `curar` | verb | health and recovery |
| `medir` | verb | health and practical services |
| `pesar` | verb | health and shopping |
| `alquilar` | verb | travel and services |
| `conducir` | verb | travel and transport |
| `alojarse` | verb | travel lodging |
| `embarcar` | verb | travel transit |
| `aterrizar` | verb | travel transit |
| `facturar` | verb | travel and services |
| `contratar` | verb | work and services |
| `ahorrar` | verb | work and money plans |
| `ganar` | verb | work and outcomes |
| `disponible` | adjective | appointments and services |
| `cómodo` | adjective | travel and household preferences |
| `tranquilo` | adjective | emotions and places |
| `preocupado` | adjective | emotions and problems |
| `satisfecho` | adjective | preferences and services |
| `amable` | adjective | social and service interactions |
| `reciente` | adjective | experiences and work updates |
| `común` | adjective | reasons and explanations |
| `experiencia` | noun | experiences and opinions |
| `plan` | noun | plans and decisions |
| `razón` | noun | reasons and explanations |
| `solicitud` | noun | requests and services |
| `queja` | noun | complaints and services |

Implemented content delta:

- 50 reviewed Wiktionary lexeme rows.
- 100 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 100 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 100 `sentence_lexeme` joins.
- 100 derived exercises:
  - production and recognition exercises for all 50 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 166 to 216.
- `reviewedSentences` increases from 392 to 492.
- `reviewedAcceptedAnswers` increases from 395 to 495.
- `exerciseCount` increases from 332 to 432.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 200 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-008 Accelerated B1 Real-Life Breadth Pack

**Status:** implemented locally after A2-007.

**Goal:** add learner-ready B1 breadth for feelings, obligations, advice, comparisons, planning,
conflict, repairs, medical visits, banking, lodging, and transit. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:**

| Lemma | POS | Domain |
|---|---|---|
| `alegrarse` | verb | feelings |
| `enfadarse` | verb | feelings and conflict |
| `asustarse` | verb | feelings and medical situations |
| `animar` | verb | feelings and advice |
| `calmar` | verb | feelings and conflict |
| `obligar` | verb | obligations |
| `permitir` | verb | permission and obligations |
| `aconsejar` | verb | advice |
| `advertir` | verb | advice and problems |
| `insistir` | verb | requests and conflict |
| `comparar` | verb | comparisons |
| `superar` | verb | experiences and problems |
| `adaptarse` | verb | planning and experiences |
| `organizar` | verb | planning and work |
| `programar` | verb | appointments and planning |
| `aplazar` | verb | appointments and planning |
| `anticipar` | verb | planning and problems |
| `coordinar` | verb | planning and work |
| `discutir` | verb | conflict and opinions |
| `negociar` | verb | conflict and services |
| `acordar` | verb | conflict and planning |
| `romper` | verb | repairs and problems |
| `dañar` | verb | repairs and problems |
| `instalar` | verb | repairs and services |
| `reemplazar` | verb | repairs and services |
| `revisar` | verb | services and medical checks |
| `examinar` | verb | medical |
| `recetar` | verb | medical |
| `vacunarse` | verb | medical |
| `sangrar` | verb | medical |
| `depositar` | verb | banking |
| `retirar` | verb | banking and services |
| `transferir` | verb | banking |
| `prestar` | verb | banking and requests |
| `abonar` | verb | banking and services |
| `mudarse` | verb | lodging and household |
| `registrarse` | verb | lodging and services |
| `reclamar` | verb | complaints and services |
| `transbordar` | verb | transit |
| `abordar` | verb | transit |
| `obligatorio` | adjective | obligations |
| `recomendable` | adjective | advice |
| `comparable` | adjective | comparisons |
| `pendiente` | adjective | planning and services |
| `mensual` | adjective | banking and planning |
| `temporal` | adjective | lodging and work |
| `doloroso` | adjective | medical and feelings |
| `descontento` | adjective | complaints and services |
| `obligación` | noun | obligations |
| `consejo` | noun | advice |
| `conflicto` | noun | conflict |
| `reparación` | noun | repairs |
| `factura` | noun | banking and services |
| `cuenta` | noun | banking |
| `banco` | noun | banking |
| `tarjeta` | noun | banking and services |
| `habitación` | noun | lodging |
| `equipaje` | noun | travel |
| `estación` | noun | transit |
| `emergencia` | noun | medical and services |

Implemented content delta:

- 60 reviewed Wiktionary lexeme rows.
- 120 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 120 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 120 `sentence_lexeme` joins.
- 120 derived exercises:
  - production and recognition exercises for all 60 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 216 to 276.
- `reviewedSentences` increases from 492 to 612.
- `reviewedAcceptedAnswers` increases from 495 to 615.
- `exerciseCount` increases from 432 to 552.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 240 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

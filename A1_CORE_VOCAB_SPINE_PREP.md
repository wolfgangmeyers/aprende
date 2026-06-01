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

## A2-024 Accelerated B1/B2 Culture, Sports, Care, Accessibility, Taxes, Immigration, Insurance, Finance, Legal, and Digital Security Pack

**Status:** implemented locally after A2-023.

**Goal:** add learner-ready B1/B2 breadth for culture and events, sports, childcare and eldercare,
accessibility, taxes, immigration, insurance, personal finance, legal documents, digital forms, and
account security. Rows use the `AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with
two independent automatic reviewers.

**Target lemmas:** `entrada anticipada al museo`, `visita guiada`, `audioguía disponible`,
`exposición temporal`, `obra original`, `copia artística autorizada`, `función agotada`,
`butaca reservada`, `entrada reducida`, `descuento joven`, `competición local`, `partido
amistoso`, `entrenamiento semanal`, `lesión leve`, `lesión grave`, `calentamiento previo`,
`equipo rival`, `resultado final`, `árbitro principal`, `norma del juego`, `guardería cercana`,
`cuidador disponible`, `recogida del niño`, `autorización de salida`, `merienda preparada`,
`pañales suficientes`, `silla infantil`, `carrito plegable`, `juguete perdido`, `cita
pediátrica`, `acompañamiento familiar`, `cuidador nocturno`, `ayuda a domicilio`, `movilidad
reducida`, `acceso adaptado`, `ascensor averiado`, `rampa disponible`, `silla de ruedas`, `baño
adaptado`, `ayuda auditiva`, `subtítulos disponibles`, `intérprete disponible`, `declaración
anual`, `borrador fiscal`, `deducción aplicable`, `ingreso declarado`, `gasto deducible`,
`recibo fiscal`, `notificación tributaria`, `deuda tributaria`, `abono diferido`, `certificado
tributario`, `cita consular`, `trámite migratorio`, `autorización de residencia`, `tarjeta de
residencia`, `copia del pasaporte`, `foto de carnet`, `huella registrada`, `cita de huellas`,
`resolución favorable`, `resolución denegada`, `seguro del hogar`, `póliza activa`, `póliza
vencida`, `siniestro abierto`, `parte de accidente`, `perito asignado`, `cobertura parcial`,
`cobertura completa`, `prima anual`, `franquicia alta`, `franquicia baja`, `reclamación al
seguro`, `daño cubierto`, `daño excluido`, `carta de renovación`, `cuota del seguro`,
`beneficiario registrado`, `cobro pendiente`, `ingreso pendiente`, `ahorros disponibles`,
`presupuesto ajustado`, `gasto previsto`, `gasto imprevisto`, `préstamo aprobado`, `préstamo
rechazado`, `cuota vencida`, `comprobante pendiente`, `contrato digital`, `cláusula principal`,
`condición especial`, `firma obligatoria`, `copia legal`, `traducción jurada`, `sello
consular`, `registro consular`, `documento apostillado`, `certificado traducido`, `cita de
renovación`, `solicitud renovada`, `formulario actualizado`, `archivo rechazado`, `archivo
aceptado`, `tamaño máximo`, `formato permitido`, `documento pesado`, `imagen borrosa`, `foto
nítida`, `pantalla de error`, `aviso emergente`, `botón desactivado`, `campo obligatorio`,
`captcha incorrecto`, `verificación fallida`, `autenticación segura`, `doble factor`, `código
de respaldo`, `sesión segura`, `alerta de seguridad`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived exercises:
  - production and recognition exercises for all 120 target lemmas.

Acceptance target:

- `learnerReadyLexemes` is 2065.
- `reviewedSentences` is 4190 after restoring the non-fixture strict build.
- `reviewedAcceptedAnswers` is 4193 after restoring the non-fixture strict build.
- `exerciseCount` is 4130.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-025 Accelerated B1/B2 Housing, Medical, Work, Travel, Banking, Conversation, and Digital Pack

**Status:** implemented locally after A2-024.

**Goal:** add learner-ready B1/B2 breadth for housing paperwork and repairs, medical referrals and
work notes, workplace logistics, travel disruption vocabulary, banking/money documents,
conversation repair, and digital access states. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:** `actualización del padrón`, `justificante de domicilio`, `contrato extendido`,
`fianza retenida`, `inquilino ruidoso`, `reparación pendiente`, `humedad visible`, `persiana rota`,
`cerradura cambiada`, `llave duplicada`, `duplicado de llaves`, `aviso de lanzamiento`, `visita
del técnico`, `revisión de caldera`, `certificado energético`, `limpieza comunitaria`, `cuota
comunitaria`, `seguro de alquiler`, `inventario del piso`, `acta de entrega`, `resumen clínico`,
`derivación médica`, `volante médico`, `cita con especialista`, `lista de espera médica`, `síntoma
persistente`, `molestia aguda`, `reacción alimentaria`, `consentimiento informado`, `antecedente
médico`, `control médico periódico`, `medicina preventiva`, `llamada médica`, `receta actualizada`,
`farmacia de guardia`, `tratamiento continuado`, `baja médica renovada`, `justificante sanitario`,
`minuta de reunión`, `evaluación anual`, `aumento salarial`, `horario comprimido`, `trabajo remoto
parcial`, `jornada reducida`, `hora extra`, `permiso pagado`, `disputa laboral`, `mediación
laboral`, `carga laboral alta`, `encargo urgente`, `prioridad crítica`, `informe final`, `propuesta
comercial`, `cliente difícil`, `llamada pendiente`, `mensaje laboral urgente`, `archivo
compartido`, `acceso interno`, `embarque prioritario`, `plaza asignada`, `maleta documentada`,
`cancelación confirmada`, `informe de equipaje`, `mostrador cerrado`, `puerta cambiada`, `escala
prolongada`, `hotel alternativo`, `transporte sustituto`, `bono de viaje`, `documento de viaje`,
`visado vigente`, `paso fronterizo cerrado`, `control fronterizo`, `declaración aduanera`, `tasa
turística`, `cuenta conjunta`, `cuenta nómina`, `tarjeta virtual`, `tarjeta desactivada`, `tope de
crédito`, `importe retenido`, `ingreso recurrente`, `gasto mensual`, `recibo devuelto`, `plan de
pagos`, `interés fijo`, `cuota reducida`, `financiación aprobada`, `aval bancario`, `certificado
bancario`, `extracto digital`, `autorización bancaria`, `opinión contraria`, `argumento sólido`,
`dato importante`, `contexto adicional`, `explicación completa`, `respuesta evasiva`, `registro
formal`, `trato injusto`, `acuerdo firmado`, `compromiso claro`, `límite personal`, `error común`,
`sospecha razonable`, `cambio de opinión`, `decisión difícil`, `preferencia personal`, `comparación
justa`, `consejo práctico`, `propuesta alternativa`, `plan realista`, `enlace seguro`, `fichero
adjunto`, `copia local`, `carpeta compartida`, `permiso denegado`, `acceso concedido`, `usuario
bloqueado`, `sesión vencida`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived production and recognition exercises for all 120 target lemmas.

Acceptance target:

- `learnerReadyLexemes` is 2185.
- `reviewedSentences` is 4430 after restoring the non-fixture strict build.
- `reviewedAcceptedAnswers` is 4433 after restoring the non-fixture strict build.
- `exerciseCount` is 4370.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-026 Accelerated B1/B2 Services, Public Admin, Education, Food, Household, Social, Health, Directions, and Transport Pack

**Status:** implemented locally after A2-025.

**Goal:** add learner-ready B1/B2 breadth for delivery and service counters, public administration,
education logistics, food ordering, household routines, social plans, emotional/health language,
directions, and transport/legal incidents. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:** `servicio de mensajería`, `retiro programado`, `entrega incompleta`, `paquete
asegurado`, `punto de recogida`, `horario de apertura`, `franja disponible`, `agenda modificada`,
`confirmación automática`, `recordatorio enviado`, `espera estimada`, `cola virtual`, `servicio
presencial`, `ventanilla única`, `número de turno`, `formulario firmado`, `solicitud archivada`,
`expediente completo`, `registro actualizado`, `certificado emitido`, `permiso concedido`,
`licencia temporal`, `autorización especial`, `recurso presentado`, `contestación oficial`,
`prórroga concedida`, `sello electrónico`, `copia autenticada`, `firma electrónica`,
`notificación recibida`, `clase de apoyo`, `programa intensivo`, `material de estudio`, `práctica
oral`, `corrección escrita`, `nivel intermedio`, `objetivo del curso`, `progreso semanal`,
`asistencia obligatoria`, `constancia de asistencia`, `mesa reservada`, `menú ejecutivo`, `plato
sin carne`, `opción sin gluten`, `alergia declarada`, `pago separado`, `servicio incluido`,
`pedido confirmado`, `pedido retrasado`, `reclamación del pedido`, `servicio doméstico`, `limpieza
profunda`, `ropa planchada`, `lavadora averiada`, `secadora disponible`, `frigorífico vacío`,
`cocina equipada`, `vajilla completa`, `basura separada`, `bolsa de tela`, `encuentro familiar`,
`invitación aceptada`, `invitación rechazada`, `celebración privada`, `regalo compartido`,
`mensaje de felicitación`, `visita inesperada`, `plan cancelado`, `excusa válida`, `malentendido
resuelto`, `ansiedad leve`, `estrés acumulado`, `ánimo bajo`, `apoyo emocional`, `pausa
necesaria`, `descanso suficiente`, `insomnio leve`, `molestia muscular`, `respiración profunda`,
`ejercicio moderado`, `camino alternativo`, `vía cortada`, `tráfico denso`, `señal confusa`,
`salida equivocada`, `entrada principal`, `paso peatonal`, `zona caminable`, `vía ciclista`,
`casco obligatorio`, `control policial`, `sanción administrativa`, `cobertura obligatoria`,
`matrícula provisional`, `revisión técnica`, `combustible caro`, `cargador disponible`, `batería
baja`, `neumático pinchado`, `grúa solicitada`.

Implemented content delta:

- 100 reviewed Wiktionary lexeme rows.
- 200 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 200 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 200 `sentence_lexeme` joins.
- 200 derived production and recognition exercises for all 100 target lemmas.

Acceptance target:

- `learnerReadyLexemes` is 2285.
- `reviewedSentences` is 4630 after restoring the non-fixture strict build.
- `reviewedAcceptedAnswers` is 4633 after restoring the non-fixture strict build.
- `exerciseCount` is 4570.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 400 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-027 Accelerated B1/B2 Weather, Pets, Repairs, Digital Media, Planning, Complaints, Health, Documents, and Meetings Pack

**Status:** implemented locally after A2-026.

**Goal:** add learner-ready B1/B2 breadth for weather, pets, repairs, device/media workflows,
planning language, complaints and warranties, dental/eye/skin health, identity documents, and
meeting participation. Rows use the `AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane
with two independent automatic reviewers.

**Target lemmas:** `pronóstico actualizado`, `lluvia intensa`, `viento fuerte`, `calor extremo`,
`frío repentino`, `aviso de tormenta`, `cielo despejado`, `temperatura estable`, `ropa adecuada`,
`paraguas disponible`, `mascota registrada`, `perro vacunado`, `gato perdido`, `collar
identificado`, `veterinario disponible`, `cita veterinaria`, `vacuna anual`, `comida para
mascotas`, `paseo diario`, `transportín homologado`, `herramienta adecuada`, `tornillo suelto`,
`enchufe quemado`, `cable dañado`, `pintura fresca`, `pared rayada`, `cristal roto`, `mueble
montado`, `manual de instrucciones`, `garantía vigente`, `pantalla táctil`, `volumen bajo`,
`auricular apagado`, `videollamada activa`, `paquete comprimido`, `almacenamiento lleno`,
`actualización instalada`, `virus detectado`, `copia cifrada`, `contraseña segura`, `noticia
reciente`, `origen fiable`, `rumor falso`, `artículo compartido`, `grabación breve`, `audio claro`,
`subtítulo automático`, `mensaje público`, `cuenta privada`, `publicación eliminada`, `plan
semanal`, `meta alcanzable`, `hábito saludable`, `rutina diaria`, `avance pequeño`, `resultado
esperado`, `intento fallido`, `segunda oportunidad`, `cambio gradual`, `mejora visible`, `reclamo
formal`, `respuesta tardía`, `compensación justa`, `cobertura extendida`, `artículo defectuoso`,
`pieza faltante`, `manual perdido`, `soporte remoto`, `servicio posventa`, `caso escalado`, `cita
dental`, `limpieza dental`, `dolor de muelas`, `encía inflamada`, `revisión ocular`, `graduación
ocular`, `lente roto`, `audífono ajustado`, `piel irritada`, `crema recetada`, `traducción
oficial`, `apellido correcto`, `nombre completo`, `fecha exacta`, `lugar de nacimiento`, `estado
civil`, `dirección actual`, `nacionalidad doble`, `contacto autorizado`, `rúbrica manual`, `copia
legible`, `sala disponible`, `proyector encendido`, `presentación breve`, `pregunta abierta`,
`respuesta parcial`, `turno de palabra`, `acuerdo parcial`, `riesgo calculado`, `decisión
colectiva`.

Implemented content delta:

- 100 reviewed Wiktionary lexeme rows.
- 200 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 200 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 200 `sentence_lexeme` joins.
- 200 derived production and recognition exercises for all 100 target lemmas.

Acceptance target:

- `learnerReadyLexemes` is 2385.
- `reviewedSentences` is 4830 after restoring the non-fixture strict build.
- `reviewedAcceptedAnswers` is 4833 after restoring the non-fixture strict build.
- `exerciseCount` is 4770.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 400 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-028 Accelerated B1/B2 Emergency, Medical, Housing, Work, Banking, Travel, Services, and Conversation Pack

**Status:** implemented locally after A2-027.

**Goal:** add learner-ready B1/B2 breadth for emergency and medical logistics, housing repairs,
workplace/service interactions, banking and bureaucracy, travel disruptions, delivery/services, and
conversation repair. Rows use the `AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane
with two independent automatic reviewers.

**Target lemmas:** `llamada de emergencia`, `pulsera médica`, `oxígeno portátil`, `intérprete médico`, `segunda opinión`, `ingreso urgente`, `radiografía pendiente`, `azúcar alta`, `vacuna recomendada`, `mascarilla disponible`, `higiene de manos`, `boletín eléctrico`, `contador compartido`, `techo manchado`, `gotera activa`, `tubería antigua`, `desagüe atascado`, `suelo resbaladizo`, `ventana abierta`, `puerta blindada`, `timbre roto`, `portero automático`, `inventario firmado`, `agencia inmobiliaria`, `recibo de renta`, `reforma autorizada`, `agenda compartida`, `objetivo trimestral`, `indicador clave`, `correo pendiente`, `copia oculta`, `cliente molesto`, `proveedor externo`, `presupuesto inicial`, `entrega parcial`, `retraso asumido`, `responsabilidad compartida`, `permiso parental`, `pausa activa`, `justificante bancario`, `clave temporal`, `cajero cercano`, `operación rechazada`, `recibo escaneado`, `trámite urgente`, `archivo cerrado`, `identidad verificada`, `mostrador abierto`, `fila prioritaria`, `puerta de salida`, `retraso anunciado`, `tren nocturno`, `andén cambiado`, `coche compartido`, `peaje electrónico`, `maleta dañada`, `habitación interior`, `llave magnética`, `mapa descargado`, `billete combinado`, `oficina turística`, `frase hecha`, `broma pesada`, `comentario fuera de lugar`, `gesto amable`, `respuesta directa`, `pregunta difícil`, `explicación sencilla`, `matiz importante`, `desacuerdo respetuoso`, `postura clara`, `propuesta razonable`, `prioridad común`, `solución intermedia`, `plan de acción`, `seguimiento posterior`, `recordatorio amable`, `llamada breve`, `conversación pendiente`, `confianza mutua`, `turno digital`, `pantalla informativa`, `aviso sonoro`, `máquina expendedora`, `ticket impreso`, `etiqueta adhesiva`, `paquete abierto`, `mensajero asignado`, `horario reducido`, `servicio mínimo`, `permiso activado`, `triaje inicial`, `camilla disponible`, `vendaje limpio`, `muleta prestada`, `consulta virtual`, `riesgo moderado`, `contacto de emergencia`, `pared húmeda`, `termo averiado`, `instalación eléctrica`, `cerrajero urgente`, `plaga doméstica`, `ventilación adecuada`, `revisión de gas`, `contador de agua`, `corte programado`, `reunión híbrida`, `versión actual`, `comentario pendiente`, `objetivo común`, `clave bancaria`, `extracto mensual`, `movimiento sospechoso`, `aviso fiscal`, `tren perdido`, `tarifa flexible`, `turno de preguntas`, `idea principal`, `contexto necesario`, `malentendido frecuente`, `acuerdo mínimo`, `respuesta honesta`, `tono neutral`, `pausa breve`, `explicación adicional`.

Implemented content delta:

- 126 reviewed Wiktionary lexeme rows.
- 252 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 252 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 252 `sentence_lexeme` joins.
- 252 derived production and recognition exercises for all 126 target lemmas.

Acceptance target:

- `learnerReadyLexemes` is 2511.
- `reviewedSentences` is 5082 after restoring the non-fixture strict build.
- `reviewedAcceptedAnswers` is 5085 after restoring the non-fixture strict build.
- `exerciseCount` is 5022.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 504 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-029 Accelerated B1/B2 Education, Environment, Civic Services, Shopping, Food, Health, Digital, and Community Pack

**Status:** implemented locally after A2-028.

**Goal:** add learner-ready B1/B2 breadth for education workflows, environmental and civic services,
shopping and food interactions, health language, digital access, and community participation. Rows
use the `AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:** `clase grabada`, `material descargable`, `foro abierto`, `tutoría virtual`, `certificado pendiente`, `práctica guiada`, `nota provisional`, `horario lectivo`, `aula virtual`, `beca renovada`, `matrícula parcial`, `recurso didáctico`, `lectura obligatoria`, `resumen entregado`, `plazo académico`, `consulta docente`, `proyecto final`, `grupo reducido`, `sesión práctica`, `nivel avanzado`, `punto limpio móvil`, `contenedor marrón`, `residuo orgánico`, `ahorro energético`, `consumo de agua`, `ruido ambiental`, `calidad del aire`, `sendero señalizado`, `playa vigilada`, `zona inundable`, `incendio controlado`, `refugio climático`, `sombra natural`, `fuente pública`, `huerto urbano`, `compost doméstico`, `recogida selectiva`, `emisión reducida`, `riesgo ambiental`, `campaña municipal`, `biblioteca móvil`, `registro municipal`, `padrón actualizado`, `permiso especial`, `inspección rutinaria`, `multa recurrida`, `notificación pendiente`, `archivo histórico`, `asesoría gratuita`, `mediación familiar`, `acceso autorizado`, `norma interna`, `requisito mínimo`, `cesta de compra`, `talla disponible`, `color elegido`, `probador libre`, `cola rápida`, `cupón aplicado`, `devolución aceptada`, `garantía ampliada`, `pedido mínimo`, `bolsa reciclada`, `recargo pequeño`, `caja automática`, `receta casera`, `ingrediente fresco`, `salsa picante`, `ración pequeña`, `mesa exterior`, `vaso reutilizable`, `agua con gas`, `postre compartido`, `cuenta dividida`, `propina voluntaria`, `reserva nocturna`, `menú infantil`, `plato recomendado`, `pan integral`, `salud mental`, `terapia grupal`, `apoyo psicológico`, `crisis nerviosa`, `cansancio extremo`, `ritmo cardíaco`, `presión baja`, `mareo repentino`, `visión borrosa`, `cuidado preventivo`, `control anual`, `medida preventiva`, `aplicación móvil`, `modo oscuro`, `notificación silenciosa`, `pantalla bloqueada`, `código QR`, `archivo temporal`, `red pública`, `batería externa`, `cargador rápido`, `descarga lenta`, `comentario fijado`, `canal privado`, `acuerdo comunitario`, `ayuda mutua`, `conflicto abierto`, `participación activa`, `opinión pública`, `protesta pacífica`, `campaña solidaria`, `voto anticipado`, `asamblea local`, `debate público`, `turno vecinal`, `centro electoral`, `acta pública`, `plan urbano`, `calle peatonal`, `carril bus`, `alumbrado nuevo`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived production and recognition exercises for all 120 target lemmas.

Acceptance target:

- `learnerReadyLexemes` is 2631.
- `reviewedSentences` is 5322 after restoring the non-fixture strict build.
- `reviewedAcceptedAnswers` is 5325 after restoring the non-fixture strict build.
- `exerciseCount` is 5262.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-030 Accelerated B1/B2 Legal, Money, Work, Family, School, Pets, Transport, Media, and Digital Pack

**Status:** implemented locally after A2-029.

**Goal:** add learner-ready B1/B2 breadth for legal and tax paperwork, personal finance, workplace
processes, family and school logistics, pet care, transport incidents, media literacy, and digital
security/reliability. Rows use the `AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane
with two independent automatic reviewers.

**Target lemmas:** `pasaporte provisional`, `permiso caducado`, `aduana abierta`, `impuesto local`, `deducción fiscal`, `recargo aplicado`, `multa pendiente`, `reclamación fiscal`, `asesor financiero`, `cuenta de ahorro`, `interés variable`, `riesgo financiero`, `compra impulsiva`, `deuda pequeña`, `préstamo familiar`, `recibo atrasado`, `cláusula clara`, `copia privada`, `prueba documental`, `asesoría laboral`, `despido improcedente`, `nómina revisada`, `vacante interna`, `ascenso posible`, `objetivo anual`, `reunión individual`, `evaluación pendiente`, `formación interna`, `manual actualizado`, `protocolo nuevo`, `riesgo operativo`, `pausa obligatoria`, `familia numerosa`, `custodia compartida`, `permiso escolar`, `autorización paterna`, `cuidado infantil`, `actividad extraescolar`, `reunión escolar`, `uniforme obligatorio`, `nota informativa`, `boletín escolar`, `apoyo educativo`, `orientación familiar`, `mascota enferma`, `vacuna pendiente`, `collar nuevo`, `jaula limpia`, `paseador disponible`, `residencia canina`, `peluquería canina`, `juguete seguro`, `arena limpia`, `microchip registrado`, `parada provisional`, `transbordo gratuito`, `billete sencillo`, `abono joven`, `horario especial`, `ruta circular`, `vehículo eléctrico`, `punto de carga`, `límite de velocidad`, `control de alcoholemia`, `accidente leve`, `parte amistoso`, `coche de sustitución`, `rueda de repuesto`, `llave del coche`, `noticia local`, `boletín informativo`, `fuente oficial`, `entrevista grabada`, `programa en directo`, `señal en vivo`, `repetición disponible`, `archivo sonoro`, `imagen nítida`, `texto legible`, `artículo destacado`, `titular exagerado`, `comentario moderado`, `perfil verificado`, `inicio seguro`, `sesión activa`, `ventana emergente`, `permiso de cámara`, `micrófono silenciado`, `archivo pesado`, `espacio libre`, `servidor caído`, `conexión estable`, `actualización pendiente`, `modo avión`, `pantalla compartida`, `mensaje cifrado`, `visado urgente`, `aduana digital`, `control migratorio`, `seguro internacional`, `resguardo fiscal`, `base imponible`, `interés compuesto`, `fondo común`, `saldo previsto`, `pago recurrente`, `cheque bancario`, `aval familiar`, `contrato mercantil`, `anexo firmado`, `copia confidencial`, `prueba escrita`, `citación judicial`, `turno presencial`, `ventanilla fiscal`, `asesor jurídico`, `mediador neutral`, `acta firmada`, `permiso sindical`, `calendario laboral`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived production and recognition exercises for all 120 target lemmas.

Acceptance target:

- `learnerReadyLexemes` is 2751.
- `reviewedSentences` is 5562 after restoring the non-fixture strict build.
- `reviewedAcceptedAnswers` is 5565 after restoring the non-fixture strict build.
- `exerciseCount` is 5502.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-031 Accelerated B1/B2 Health, Housing, Work, Delivery, Transport, Conversation, and Digital Support Pack

**Status:** implemented locally after A2-030.

**Goal:** add learner-ready B1/B2 breadth for health logistics, housing details, workplace tools,
delivery and shopping flows, transport navigation, conversation repair, and digital support. Rows use
the `AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:** `agenda médica`, `sala pediátrica`, `vacuna infantil`, `cartilla sanitaria`, `seguimiento remoto`, `síntoma leve`, `tratamiento alternativo`, `farmacéutico disponible`, `medicina genérica`, `pastillero semanal`, `crema hidratante`, `protector solar`, `picadura leve`, `corte superficial`, `vendaje adhesivo`, `cocina comunitaria`, `vecindario seguro`, `patio interior`, `balcón soleado`, `terraza cubierta`, `trastero pequeño`, `plaza de garaje`, `calle tranquila`, `portal iluminado`, `escalera estrecha`, `suelo laminado`, `baño reformado`, `ducha accesible`, `grifo nuevo`, `caldera revisada`, `termostato inteligente`, `consumo eléctrico`, `factura de gas`, `cliente potencial`, `reunión comercial`, `objetivo cumplido`, `informe mensual`, `lista de tareas`, `correo automático`, `firma corporativa`, `carpeta privada`, `permiso temporal`, `acceso remoto`, `pantalla principal`, `sesión formativa`, `manual interno`, `proceso aprobado`, `pedido internacional`, `entrega urgente`, `seguimiento del paquete`, `número de envío`, `dirección incompleta`, `paquete frágil`, `reparto nocturno`, `tienda asociada`, `stock limitado`, `impuesto incluido`, `pago seguro`, `recibo digital`, `compra recurrente`, `servicio contratado`, `viaje compartido`, `carril rápido`, `zona escolar`, `semáforo averiado`, `peatón distraído`, `bicicleta pública`, `patinete eléctrico`, `casco ajustado`, `freno delantero`, `mapa interactivo`, `ubicación actual`, `ruta guardada`, `parada solicitada`, `conductor amable`, `viajero frecuente`, `opinión personal`, `idea equivocada`, `respuesta corta`, `pregunta sencilla`, `comentario útil`, `sugerencia práctica`, `crítica constructiva`, `acuerdo definitivo`, `duda frecuente`, `matiz cultural`, `ejemplo típico`, `frase común`, `palabra clave`, `pronunciación clara`, `escucha activa`, `turno respetado`, `silencio necesario`, `mensaje resumido`, `notificación urgente`, `copia automática`, `contraseña antigua`, `usuario invitado`, `archivo eliminado`, `historial reciente`, `búsqueda avanzada`, `filtro activo`, `resultado relevante`, `página cargada`, `pantalla secundaria`, `botón principal`, `menú lateral`, `formato válido`, `ayuda contextual`, `soporte técnico`, `chat en línea`, `llamada programada`, `consulta resuelta`, `reclamo abierto`, `plazo extendido`, `servicio interrumpido`, `sección visible`, `archivo recuperado`, `cuenta reactivada`, `correo verificado`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived production and recognition exercises for all 120 target lemmas.

Acceptance target:

- `learnerReadyLexemes` is 2871.
- `reviewedSentences` is 5802 after restoring the non-fixture strict build.
- `reviewedAcceptedAnswers` is 5805 after restoring the non-fixture strict build.
- `exerciseCount` is 5742.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-032 Accelerated B1/B2 Health, Legal, Money, Food, Travel, Culture, Conversation, and Planning Pack

**Status:** implemented locally after A2-031.

**Goal:** add learner-ready B1/B2 breadth for health appointments and diet, legal/bureaucratic
documents, banking and shopping flows, restaurant/culture/travel details, conversation repair, and
practical planning. Rows use the `AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane
with two independent automatic reviewers.

**Target lemmas:** `reserva médica`, `consulta presencial`, `turno asignado`, `sala de rayos`, `laboratorio abierto`, `muestra recogida`, `tratamiento suspendido`, `control de peso`, `plan nutricional`, `comida saludable`, `bebida isotónica`, `menú sin sal`, `receta baja en azúcar`, `ejercicio suave`, `estiramiento diario`, `masaje terapéutico`, `terapia ocupacional`, `descanso activo`, `contrato vigente`, `cláusula pendiente`, `anexo digital`, `copia escaneada`, `aviso legal`, `plazo judicial`, `ventanilla abierta`, `trámite presencial`, `clave permanente`, `carpeta ciudadana`, `notificación electrónica`, `servicio tributario`, `consulta fiscal`, `pago telemático`, `transferencia programada`, `comisión oculta`, `tipo fijo`, `tipo variable`, `interés mensual`, `plan de ahorro`, `fondo de emergencia`, `compra aplazada`, `factura simplificada`, `ticket electrónico`, `entrega certificada`, `mensajería urgente`, `repartidor local`, `ruta de reparto`, `almacén temporal`, `producto devuelto`, `artículo reservado`, `pedido personalizado`, `stock actualizado`, `precio unitario`, `carrito lleno`, `caja cerrada`, `sistema caído`, `terminal activo`, `camarero atento`, `pedido equivocado`, `plato frío`, `bebida caliente`, `sopa casera`, `ensalada mixta`, `carne hecha`, `pescado fresco`, `postre casero`, `cuenta correcta`, `código de mesa`, `turno de cocina`, `servicio rápido`, `cita cultural`, `visita nocturna`, `guía local`, `mapa turístico`, `sendero corto`, `mirador abierto`, `museo gratuito`, `taller creativo`, `concierto acústico`, `fila delantera`, `sonido claro`, `luz tenue`, `programa impreso`, `opinión sincera`, `debate tranquilo`, `pregunta pendiente`, `respuesta completa`, `comentario breve`, `argumento central`, `razón principal`, `conclusión clara`, `acuerdo posible`, `conflicto resuelto`, `malentendido pequeño`, `disculpa aceptada`, `promesa cumplida`, `prioridad personal`, `objetivo compartido`, `paso siguiente`, `recordatorio pendiente`, `turno médico`, `consulta privada`, `sala silenciosa`, `muestra de sangre`, `informe urgente`, `terapia familiar`, `dieta blanda`, `agua mineral`, `merienda saludable`, `contrato ampliado`, `cláusula adicional`, `archivo notarial`, `registro abierto`, `cita tributaria`, `declaración pendiente`, `cuenta familiar`, `comisión reducida`, `fondo reservado`, `entrega programada`, `paquete devuelto`, `almacén abierto`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived production and recognition exercises for all 120 target lemmas.

Acceptance target:

- `learnerReadyLexemes` is 2991.
- `reviewedSentences` is 6042 after restoring the non-fixture strict build.
- `reviewedAcceptedAnswers` is 6045 after restoring the non-fixture strict build.
- `exerciseCount` is 5982.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-033 Accelerated B1/B2 Health, Housing, Banking, Bureaucracy, Travel, Repairs, and Digital Support Pack

**Status:** implemented locally after A2-032.

**Goal:** add learner-ready B1/B2 breadth for health and accessibility support, housing and
repairs, banking and insurance, documents and bureaucracy, lodging and travel disruptions,
transport navigation, and digital support. Rows use the `AI_DRAFT -> AUTO_CHECKED ->
AUTO_REVIEWED -> REVIEWED` lane with two independent automatic reviewers.

**Target lemmas:** `consulta cancelada`, `urgencia menor`, `ambulancia privada`, `pastilla partida`, `jarabe infantil`, `termómetro digital`, `mareo leve`, `herida limpia`, `venda estéril`, `rampa accesible`, `puerta automática`, `llave maestra`, `cerradura nueva`, `vecino responsable`, `derroche de agua`, `parte de daños`, `factura pendiente`, `pago anticipado`, `recargo bancario`, `cuota fija`, `cuota variable`, `crédito aprobado`, `clave olvidada`, `oficina bancaria`, `gestor disponible`, `contrato revisado`, `documento válido`, `permiso renovado`, `declaración jurada`, `cita modificada`, `cola larga`, `atención lenta`, `casilla obligatoria`, `justificante válido`, `reserva hotelera`, `cama supletoria`, `recepción abierta`, `maleta perdida`, `reclamación aérea`, `vuelo retrasado`, `andén correcto`, `billete impreso`, `aparcamiento libre`, `cruce peligroso`, `señal visible`, `obra cercana`, `pieza original`, `repuesto disponible`, `manual de uso`, `avería cubierta`, `instalación rápida`, `revisión gratuita`, `videollamada estable`, `micrófono abierto`, `contraseña nueva`, `soporte disponible`, `chat cerrado`, `incidencia registrada`, `solución parcial`, `ejemplo claro`, `aclaración necesaria`, `ambulancia municipal`, `tarjeta europea`, `informe radiológico`, `pastilla efervescente`, `jarabe natural`, `termómetro fiable`, `herida profunda`, `venda limpia`, `muleta ajustable`, `andador ligero`, `rampa portátil`, `baño seguro`, `llavero perdido`, `alarma silenciosa`, `vecino nuevo`, `junta ordinaria`, `consumo excesivo`, `avería común`, `luz intermitente`, `póliza vigente`, `parte abierto`, `pago atrasado`, `recargo mínimo`, `crédito disponible`, `tarjeta vencida`, `cajero vacío`, `sucursal abierta`, `gestor asignado`, `firma digitalizada`, `documento oficial`, `visado temporal`, `oficina consular`, `portal electrónico`, `turno rápido`, `fila ordenada`, `mostrador libre`, `número asignado`, `formulario digital`, `casilla marcada`, `justificante impreso`, `plazo corto`, `recurso aceptado`, `respuesta provisional`, `hotel céntrico`, `cama cómoda`, `recepción nocturna`, `salida anticipada`, `desayuno caliente`, `tasa incluida`, `maleta rota`, `vuelo cancelado`, `puerta cerrada`, `asiento libre`, `equipaje perdido`, `control rápido`, `aduana llena`, `andén vacío`, `billete móvil`, `bus lanzadera`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived production and recognition exercises for all 120 target lemmas.

Acceptance target:

- `learnerReadyLexemes` is 3111.
- `reviewedSentences` is 6282 after restoring the non-fixture strict build.
- `reviewedAcceptedAnswers` is 6285 after restoring the non-fixture strict build.
- `exerciseCount` is 6222.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-034 Accelerated B1/B2 Transport, Repairs, Digital Support, Health, Services, Work, and Travel Pack

**Status:** implemented locally after A2-033.

**Goal:** add learner-ready B1/B2 breadth for transport navigation, repair logistics, digital
support, health symptoms and appointments, public services, work administration, everyday
conversation, and practical travel. Rows use the `AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED ->
REVIEWED` lane with two independent automatic reviewers.

**Target lemmas:** `abono turístico`, `parada final`, `calle estrecha`, `ruta segura`, `tráfico ligero`, `parking cubierto`, `cruce señalizado`, `señal borrosa`, `obra municipal`, `taller autorizado`, `pieza compatible`, `repuesto original`, `herramienta básica`, `manual ilustrado`, `avería grave`, `reparación cubierta`, `instalación pendiente`, `revisión completa`, `llamada entrante`, `correo recibido`, `respuesta manual`, `archivo privado`, `videollamada corta`, `micrófono externo`, `cámara frontal`, `cuenta segura`, `chat disponible`, `incidencia cerrada`, `explicación breve`, `ejemplo práctico`, `aclaración final`, `sala llena`, `médico suplente`, `enfermera amable`, `muestra válida`, `tratamiento largo`, `molestia leve`, `hinchazón visible`, `respiración lenta`, `pulso regular`, `reposo recomendado`, `dieta ligera`, `comida blanda`, `sopa caliente`, `mesa libre`, `pedido pendiente`, `anexo pendiente`, `copia válida`, `archivo firmado`, `acuse digital`, `plazo vencido`, `trámite rápido`, `ventanilla ocupada`, `clave caducada`, `notificación leída`, `consulta gratuita`, `recibo impreso`, `transferencia enviada`, `ahorro familiar`, `ticket perdido`, `mensajería local`, `repartidor externo`, `ruta confirmada`, `almacén cerrado`, `artículo agotado`, `pedido urgente`, `stock mínimo`, `carrito vacío`, `caja rápida`, `terminal lento`, `sistema actualizado`, `museo lleno`, `taller abierto`, `concierto gratuito`, `sonido fuerte`, `luz natural`, `programa cultural`, `opinión razonable`, `debate abierto`, `pregunta directa`, `comentario amable`, `razón válida`, `conclusión provisional`, `disculpa formal`, `promesa pendiente`, `prioridad urgente`, `objetivo concreto`, `paso final`, `agenda laboral`, `acta provisional`, `propuesta clara`, `proveedor local`, `pedido interno`, `entrega interna`, `pausa corta`, `sueldo neto`, `permiso aprobado`, `vacación pendiente`, `cita psicológica`, `prueba auditiva`, `hombro rígido`, `rodilla inflamada`, `piel seca`, `spray nasal`, `gota ocular`, `radiografía dental`, `cobertura básica`, `ayuda urgente`, `centro social`, `oficina pública`, `silla disponible`, `baño público`, `entrada lateral`, `salida principal`, `mapa local`, `folleto gratuito`, `guía impresa`, `excursión corta`, `alojamiento rural`, `zona de picnic`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived production and recognition exercises for all 120 target lemmas.

Acceptance target:

- `learnerReadyLexemes` is 3231.
- `reviewedSentences` is 6522 after restoring the non-fixture strict build.
- `reviewedAcceptedAnswers` is 6525 after restoring the non-fixture strict build.
- `exerciseCount` is 6462.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-035 Accelerated B1/B2 Travel, Services, Money, Repairs, Digital, Work, Health, and Conversation Pack

**Status:** implemented locally after A2-034.

**Goal:** add learner-ready B1/B2 breadth for travel and public spaces, service forms and
documents, banking and insurance, repairs, digital support, workplace administration, health
appointments, and practical conversation. Rows use the `AI_DRAFT -> AUTO_CHECKED ->
AUTO_REVIEWED -> REVIEWED` lane with two independent automatic reviewers.

**Target lemmas:** `playa cercana`, `montaña nevada`, `ruta rural`, `visita libre`, `guía turística`, `horario ampliado`, `oficina abierta`, `sala reservada`, `puesto libre`, `silla plegable`, `mesa redonda`, `panel informativo`, `cartel visible`, `puerta principal`, `pasillo estrecho`, `escalera mecánica`, `ascensor libre`, `rampa exterior`, `servicio nocturno`, `consulta en línea`, `formulario simple`, `casilla vacía`, `archivo enviado`, `firma válida`, `contrato nuevo`, `cláusula especial`, `anexo final`, `recibo válido`, `factura digital`, `saldo bajo`, `cuenta compartida`, `código seguro`, `transferencia fallida`, `comisión mensual`, `ahorro pequeño`, `fondo seguro`, `crédito rechazado`, `seguro básico`, `póliza nueva`, `cobertura limitada`, `parte cerrado`, `avería menor`, `repuesto caro`, `herramienta limpia`, `manual claro`, `instalación segura`, `reparación lenta`, `técnico puntual`, `servicio garantizado`, `llamada saliente`, `correo archivado`, `respuesta guardada`, `archivo visible`, `pantalla apagada`, `micrófono nuevo`, `cámara externa`, `conexión lenta`, `red segura`, `contraseña fuerte`, `cuenta activa`, `soporte lento`, `chat abierto`, `incidencia pendiente`, `solución rápida`, `explicación larga`, `ejemplo sencillo`, `aclaración breve`, `respuesta razonable`, `comentario oportuno`, `argumento débil`, `razón suficiente`, `conclusión definitiva`, `conflicto pequeño`, `promesa clara`, `plan detallado`, `paso intermedio`, `recordatorio útil`, `agenda semanal`, `turno completo`, `reunión breve`, `acta final`, `propuesta formal`, `presupuesto reducido`, `cliente habitual`, `pedido semanal`, `entrega puntual`, `informe diario`, `correo interno`, `pausa larga`, `sueldo bruto`, `permiso pendiente`, `vacación aprobada`, `cita médica privada`, `prueba visual`, `hombro dolorido`, `rodilla rígida`, `piel sensible`, `gota nasal`, `spray bucal`, `radiografía urgente`, `oficina cerrada`, `silla cómoda`, `baño limpio`, `entrada trasera`, `salida rápida`, `mapa actualizado`, `folleto impreso`, `guía oficial`, `excursión larga`, `alojamiento barato`, `zona tranquila`, `costa tranquila`, `puerto pequeño`, `billete barato`, `reserva flexible`, `maleta ligera`, `mochila segura`, `farmacia nocturna`, `consulta familiar`, `diagnóstico claro`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived production and recognition exercises for all 120 target lemmas.

Acceptance target:

- `learnerReadyLexemes` is 3351.
- `reviewedSentences` is 6762 after restoring the non-fixture strict build.
- `reviewedAcceptedAnswers` is 6765 after restoring the non-fixture strict build.
- `exerciseCount` is 6702.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-023 Accelerated B1/B2 Education, Community, Environment, Media, Family, Civic, Shopping, Delivery, and Money Pack

**Status:** implemented locally after A2-022.

**Goal:** add learner-ready B1/B2 breadth for education, community services, civic events,
environmental issues, media literacy, family logistics, school communication, municipal services,
transport access, digital payments, shopping, delivery, and customs language. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:** `matrícula abierta`, `plaza disponible`, `lista provisional`, `nota final`,
`examen aprobado`, `examen suspendido`, `clase cancelada`, `clase recuperada`, `tarea
entregada`, `tarea atrasada`, `curso intensivo`, `curso gratuito`, `beca parcial`, `beca
completa`, `tutor asignado`, `orientación académica`, `biblioteca abierta`, `sala de estudio`,
`centro cultural`, `actividad gratuita`, `inscripción previa`, `aforo limitado`, `entrada
gratuita`, `entrada agotada`, `evento aplazado`, `evento suspendido`, `voluntariado local`,
`apoyo comunitario`, `ayuda social`, `comedor social`, `albergue temporal`, `donación puntual`,
`recogida solidaria`, `zona verde`, `parque cerrado`, `árbol caído`, `rama peligrosa`, `aire
contaminado`, `olor fuerte`, `agua potable`, `agua no potable`, `residuo peligroso`, `punto
limpio`, `bolsa reutilizable`, `consumo responsable`, `noticia falsa`, `fuente fiable`,
`titular engañoso`, `artículo completo`, `comentario público`, `perfil privado`, `perfil
público`, `foto compartida`, `video corto`, `audio enviado`, `mensaje reenviado`, `grupo
familiar`, `cuidado compartido`, `permiso familiar`, `emergencia familiar`, `reunión familiar`,
`visita familiar`, `cita escolar`, `reunión de padres`, `autorización escolar`, `comedor
escolar`, `transporte escolar`, `material escolar`, `uniforme escolar`, `ausencia justificada`,
`ausencia injustificada`, `retraso justificado`, `justificación escrita`, `cita de
orientación`, `consulta vecinal`, `reunión vecinal`, `ruido nocturno`, `fiesta autorizada`,
`permiso de obra`, `obra menor`, `licencia municipal`, `tasa municipal`, `recibo municipal`,
`servicio municipal`, `zona peatonal`, `carril bici`, `aparcamiento gratuito`, `aparcamiento
reservado`, `zona azul`, `parquímetro roto`, `carga eléctrica`, `vehículo compartido`, `boleto
válido`, `boleto vencido`, `pago móvil`, `monedero digital`, `saldo digital`, `recarga
automática`, `pago sin contacto`, `código promocional`, `descuento caducado`, `oferta
limitada`, `precio rebajado`, `producto agotado`, `producto disponible`, `talla agotada`,
`color disponible`, `cambio gratuito`, `devolución parcial`, `reembolso parcial`, `envío
urgente`, `entrega nocturna`, `paquete retenido`, `aduana pendiente`, `documento aduanero`,
`valor declarado`, `firma de entrega`, `prueba de entrega`, `recibo de compra`, `historial de
compras`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived exercises:
  - production and recognition exercises for all 120 target lemmas.

Acceptance target:

- `learnerReadyLexemes` increases from 1825 to 1945.
- `reviewedSentences` increases from 3710 to 3950.
- `reviewedAcceptedAnswers` increases from 3713 to 3953.
- `exerciseCount` increases from 3650 to 3890.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-022 Accelerated B1/B2 Emergencies, Transport, Shopping, Food, Household, Digital, Planning, and Argument Pack

**Status:** implemented locally after A2-021.

**Goal:** add learner-ready B1/B2 breadth for emergencies and safety, transport disruptions and
repairs, shopping/delivery/restaurant interactions, household services, digital access and meetings,
planning, communication tone, and argument language. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:** `alerta meteorológica`, `aviso de emergencia`, `punto seguro`, `salida
bloqueada`, `evacuación parcial`, `zona inundada`, `calle cortada`, `desvío temporal`, `atasco
fuerte`, `carril cerrado`, `peaje obligatorio`, `multa de tráfico`, `permiso de conducir`,
`seguro del coche`, `revisión del coche`, `taller cercano`, `grúa disponible`, `batería
descargada`, `rueda pinchada`, `motor averiado`, `compra segura`, `pedido incompleto`,
`producto defectuoso`, `garantía comercial`, `plazo de devolución`, `etiqueta de devolución`,
`envío asegurado`, `seguimiento activo`, `entrega fallida`, `paquete dañado`, `repartidor
asignado`, `recogida programada`, `almacén cercano`, `reserva de mesa`, `mesa disponible`,
`menú del día`, `plato vegetariano`, `alergia alimentaria`, `cuenta separada`, `propina
incluida`, `comida para llevar`, `pedido para recoger`, `ingrediente principal`, `receta
sencilla`, `horno precalentado`, `sartén caliente`, `aceite usado`, `basura orgánica`,
`reciclaje obligatorio`, `contenedor lleno`, `limpieza pendiente`, `limpiador asignado`,
`lavadora rota`, `nevera vacía`, `congelador averiado`, `alarma activada`, `alarma falsa`,
`cámara apagada`, `llamada grabada`, `consentimiento verbal`, `consentimiento digital`,
`privacidad básica`, `datos actualizados`, `datos incorrectos`, `perfil bloqueado`, `cuenta
suspendida`, `sesión caducada`, `código temporal`, `clave segura`, `acceso temporal`, `permiso
de acceso`, `archivo comprimido`, `respaldo digital`, `versión antigua`, `versión nueva`,
`actualización obligatoria`, `pantalla congelada`, `sonido bajo`, `micrófono apagado`, `cámara
encendida`, `reunión grabada`, `enlace de reunión`, `invitación enviada`, `calendario
compartido`, `recordatorio automático`, `agenda llena`, `hueco libre`, `plan alternativo`,
`opción flexible`, `prioridad media`, `prioridad baja`, `tarea aplazada`, `tarea completada`,
`lista actualizada`, `resumen breve`, `explicación clara`, `respuesta breve`, `tono amable`,
`tono formal`, `mensaje confuso`, `mensaje claro`, `mal tono`, `buen trato`, `acuerdo claro`,
`límite claro`, `consecuencia directa`, `motivo principal`, `causa probable`, `efecto
inmediato`, `cambio notable`, `mejora clara`, `empeoramiento rápido`, `señal positiva`, `señal
negativa`, `duda razonable`, `prueba suficiente`, `dato relevante`, `detalle importante`, `nota
aclaratoria`, `comentario final`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived exercises:
  - production and recognition exercises for all 120 target lemmas.

Acceptance target:

- `learnerReadyLexemes` increases from 1705 to 1825.
- `reviewedSentences` increases from 3470 to 3710.
- `reviewedAcceptedAnswers` increases from 3473 to 3713.
- `exerciseCount` increases from 3410 to 3650.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-021 Accelerated B1/B2 Legal, Medical, Work, Housing, Utilities, and Travel Pack

**Status:** implemented locally after A2-020.

**Goal:** add learner-ready B1/B2 breadth for legal/public-service procedures, medical emergencies
and follow-up, work scheduling and pay, housing repairs and utilities, travel disruptions, lodging,
and transport service language. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:** `queja documentada`, `informe policial`, `audiencia próxima`, `asesoramiento
gratuito`, `permiso provisional`, `documento provisional`, `copia autorizada`, `código de
expediente`, `expediente abierto`, `expediente cerrado`, `recurso pendiente`, `plazo de
recurso`, `carta oficial`, `notificación vencida`, `oficina de registro`, `domicilio
registrado`, `certificado provisional`, `certificado médico laboral`, `cita presencial`, `cita
virtual`, `test inmediato`, `resultado urgente`, `receta renovada`, `medicación agotada`,
`dosis olvidada`, `opresión en el pecho`, `respiración difícil`, `pérdida de conocimiento`,
`reacción alérgica`, `ambulancia urgente`, `urgencias abiertas`, `atención prioritaria`,
`historial actualizado`, `informe pendiente`, `traslado sanitario`, `reposo absoluto`,
`seguimiento médico`, `vacunación pendiente`, `alergia grave`, `guardia nocturna`, `guardia
matinal`, `cambio de turno`, `contrato parcial`, `fase inicial`, `baja por enfermedad`,
`accidente laboral`, `formación obligatoria`, `reunión urgente`, `informe semanal`, `objetivo
claro`, `plazo interno`, `volumen de trabajo`, `equipo reducido`, `día remunerado`,
`teletrabajo parcial`, `ingreso bruto`, `ingreso neto`, `complemento salarial`, `nómina
corregida`, `vacaciones pendientes`, `vacaciones aprobadas`, `sustitución temporal`, `compañero
nuevo`, `conflicto laboral`, `arreglo urgente`, `técnico asignado`, `visita técnica`,
`presupuesto detallado`, `garantía válida`, `garantía vencida`, `pieza rota`, `aparato
averiado`, `instalación nueva`, `revisión anual`, `mantenimiento pendiente`, `gas cortado`,
`internet caído`, `señal débil`, `cobertura móvil`, `router apagado`, `contraseña wifi`,
`factura de luz`, `factura de agua`, `lectura de medidor`, `contador averiado`, `junta de
vecinos`, `gestor del edificio`, `alquiler pendiente`, `renta mensual`, `recibo de alquiler`,
`contrato prorrogado`, `aviso de desalojo`, `llave extra`, `copia de llaves`, `cobertura de
viaje`, `equipaje extraviado`, `reclamo de equipaje`, `demora del vuelo`, `embarque cerrado`,
`asiento asignado`, `asiento cambiado`, `maleta facturada`, `filtro de seguridad`, `pasaporte
caducado`, `visado aprobado`, `visado rechazado`, `frontera cerrada`, `reserva modificada`,
`hotel completo`, `habitación sucia`, `cambio de habitación`, `desayuno incluido`, `transporte
incluido`, `taxi oficial`, `tarifa fija`, `conductor disponible`, `documento original`, `copia
vigente`, `sello de entrada`, `registro de salida`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived exercises:
  - production and recognition exercises for all 120 target lemmas.

Acceptance target:

- `learnerReadyLexemes` increases from 1585 to 1705.
- `reviewedSentences` increases from 3230 to 3470.
- `reviewedAcceptedAnswers` increases from 3233 to 3473.
- `exerciseCount` increases from 3170 to 3410.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
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

## A2-009 Accelerated B1 Narration and Interaction Pack

**Status:** implemented locally after A2-008.

**Goal:** expand learner-ready B1 breadth for narration, past/future planning, opinions,
workplace communication, social interaction, health visits, and service interactions. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:**

| Lemma | POS | Domain |
|---|---|---|
| `contar` | verb | narration and social interaction |
| `narrar` | verb | narration |
| `describir` | verb | narration and health |
| `mencionar` | verb | opinions and workplace |
| `ocurrir` | verb | narration and past events |
| `suceder` | verb | narration and past events |
| `continuar` | verb | planning and work |
| `avanzar` | verb | planning and workplace |
| `retrasar` | verb | planning and transit |
| `finalizar` | verb | workplace and planning |
| `lograr` | verb | planning and outcomes |
| `intentar` | verb | planning and problem solving |
| `prever` | verb | future planning |
| `evaluar` | verb | workplace and services |
| `analizar` | verb | workplace and opinions |
| `resumir` | verb | narration and workplace |
| `presentar` | verb | workplace and services |
| `participar` | verb | workplace and social interaction |
| `colaborar` | verb | workplace and social interaction |
| `reunirse` | verb | workplace and social interaction |
| `entrevistar` | verb | workplace |
| `capacitar` | verb | workplace |
| `ascender` | verb | workplace |
| `renunciar` | verb | workplace and decisions |
| `consultar` | verb | health and services |
| `comunicar` | verb | workplace and services |
| `informar` | verb | workplace and services |
| `saludar` | verb | social interaction |
| `despedirse` | verb | social interaction |
| `invitar` | verb | social interaction |
| `agradecer` | verb | social and service interactions |
| `disculparse` | verb | social and service interactions |
| `celebrar` | verb | social interaction and narration |
| `conversar` | verb | social interaction |
| `confiar` | verb | opinions and relationships |
| `respetar` | verb | opinions and social interaction |
| `afirmar` | verb | opinions |
| `negar` | verb | opinions and conflict |
| `dudar` | verb | opinions and uncertainty |
| `parecer` | verb | opinions |
| `mejorar` | verb | health and services |
| `empeorar` | verb | health and problems |
| `diagnosticar` | verb | health |
| `ingresar` | verb | health and services |
| `operar` | verb | health and services |
| `tratar` | verb | health and problem solving |
| `devolver` | verb | services and shopping |
| `entregar` | verb | services and workplace |
| `contactar` | verb | services and workplace |
| `ajustar` | verb | planning and services |
| `renovar` | verb | services and planning |
| `aprobar` | verb | workplace and decisions |
| `suspender` | verb | services and planning |
| `proteger` | verb | services and health |
| `historia` | noun | narration |
| `detalle` | noun | narration and services |
| `noticia` | noun | narration and social interaction |
| `futuro` | noun | future planning |
| `pasado` | noun | past narration |
| `reunión` | noun | workplace and planning |
| `proyecto` | noun | workplace and planning |
| `empresa` | noun | workplace |
| `jefe` | noun | workplace and social interaction |
| `compañero` | noun | workplace and social interaction |
| `contrato` | noun | workplace and services |
| `horario` | noun | planning and services |
| `turno` | noun | workplace and services |
| `salario` | noun | workplace and money |
| `farmacia` | noun | health and services |
| `síntoma` | noun | health |

Implemented content delta:

- 70 reviewed Wiktionary lexeme rows.
- 140 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 140 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 140 `sentence_lexeme` joins.
- 140 derived exercises:
  - production and recognition exercises for all 70 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 276 to 346.
- `reviewedSentences` increases from 612 to 752.
- `reviewedAcceptedAnswers` increases from 615 to 755.
- `exerciseCount` increases from 552 to 692.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 280 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-010 Accelerated B1 Connectors and Practical Domains Pack

**Status:** implemented locally after A2-009.

**Goal:** broaden learner-ready B1 fluency with connectors, common chunks, sequencing language,
problem/solution verbs, workplace nouns, appointments, health services, housing, travel, and
banking. Rows use the `AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two
independent automatic reviewers.

**Target lemmas:**

| Lemma | POS | Domain |
|---|---|---|
| `aunque` | conjunction | connectors |
| `además` | adverb | connectors |
| `entonces` | adverb | connectors and narration |
| `mientras` | conjunction | connectors and narration |
| `todavía` | adverb | time and narration |
| `tampoco` | adverb | connectors and opinions |
| `incluso` | adverb | connectors and emphasis |
| `quizás` | adverb | opinions and uncertainty |
| `aproximadamente` | adverb | appointments and banking |
| `normalmente` | adverb | narration and routine |
| `actualmente` | adverb | workplace and narration |
| `especialmente` | adverb | opinions and emphasis |
| `finalmente` | adverb | narration and sequencing |
| `anteriormente` | adverb | past narration |
| `después` | adverb | sequencing and narration |
| `durante` | preposition | time and narration |
| `según` | preposition | connectors and opinions |
| `mediante` | preposition | services and banking |
| `excepto` | preposition | connectors and exceptions |
| `alrededor` | adverb | travel and housing |
| `relatar` | verb | narration |
| `indicar` | verb | services and directions |
| `señalar` | verb | narration and services |
| `evitar` | verb | problems and health |
| `prevenir` | verb | health and problems |
| `afrontar` | verb | problems and solutions |
| `enfrentar` | verb | problems and conflict |
| `denunciar` | verb | problems and services |
| `resolver` | verb | problems and solutions |
| `comprobar` | verb | services and problem solving |
| `verificar` | verb | services and banking |
| `gestionar` | verb | workplace and services |
| `tramitar` | verb | services and bureaucracy |
| `anular` | verb | appointments and services |
| `posponer` | verb | appointments and planning |
| `citar` | verb | appointments and services |
| `acudir` | verb | appointments and health |
| `asistir` | verb | workplace and appointments |
| `notificar` | verb | services and workplace |
| `presupuesto` | noun | banking and services |
| `cliente` | noun | workplace and services |
| `proveedor` | noun | workplace and services |
| `equipo` | noun | workplace |
| `informe` | noun | workplace and narration |
| `documento` | noun | workplace and services |
| `tarea` | noun | workplace and planning |
| `plazo` | noun | workplace and planning |
| `objetivo` | noun | planning and workplace |
| `resultado` | noun | workplace and health |
| `dato` | noun | workplace and banking |
| `formulario` | noun | services and appointments |
| `permiso` | noun | services and workplace |
| `calendario` | noun | appointments and planning |
| `disponibilidad` | noun | appointments and services |
| `retraso` | noun | travel and appointments |
| `cambio` | noun | planning and services |
| `enfermedad` | noun | health |
| `infección` | noun | health |
| `clínica` | noun | health and services |
| `hospital` | noun | health and services |
| `paciente` | noun | health |
| `análisis` | noun | health and workplace |
| `tratamiento` | noun | health |
| `medicamento` | noun | health |
| `prueba` | noun | health and services |
| `apartamento` | noun | housing |
| `alquiler` | noun | housing and banking |
| `vecino` | noun | housing and social interaction |
| `llave` | noun | housing and travel |
| `ascensor` | noun | housing and services |
| `baño` | noun | housing and travel |
| `destino` | noun | travel |
| `ruta` | noun | travel and transit |
| `pasaporte` | noun | travel and services |
| `billete` | noun | travel and banking |
| `préstamo` | noun | banking |
| `efectivo` | noun | banking and services |
| `recibo` | noun | banking and services |
| `cajero` | noun | banking and services |
| `cuota` | noun | banking and services |

Implemented content delta:

- 80 reviewed Wiktionary lexeme rows.
- 160 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 160 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 160 `sentence_lexeme` joins.
- 160 derived exercises:
  - production and recognition exercises for all 80 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 346 to 426.
- `reviewedSentences` increases from 752 to 912.
- `reviewedAcceptedAnswers` increases from 755 to 915.
- `exerciseCount` increases from 692 to 852.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 320 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-011 Accelerated B1 Connectors, Services, and Problem-Solving Pack

**Status:** implemented locally after A2-010.

**Goal:** extend B1 fluency with multiword connectors, narration chunks, opinion/problem-solving
language, workplace/service interactions, health/body vocabulary, housing/travel needs, and banking
support language. Rows use the `AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with
two independent automatic reviewers.

**Target lemmas:**

| Lemma | POS | Domain |
|---|---|---|
| `sin embargo` | adverbial phrase | connectors and opinions |
| `por eso` | adverbial phrase | connectors and explanations |
| `alternativamente` | adverb | connectors and planning |
| `por ejemplo` | adverbial phrase | connectors and examples |
| `en cuanto a` | prepositional phrase | connectors and workplace |
| `a pesar de` | prepositional phrase | connectors and narration |
| `de repente` | adverbial phrase | narration |
| `al principio` | adverbial phrase | narration and sequencing |
| `al final` | adverbial phrase | narration and sequencing |
| `por lo tanto` | adverbial phrase | connectors and explanations |
| `soler` | verb | routine and narration |
| `mantener` | verb | workplace and health |
| `apoyar` | verb | social and workplace |
| `permitirse` | verb | banking and decisions |
| `acostumbrarse` | verb | housing and work |
| `convencer` | verb | opinions and conflict |
| `criticar` | verb | opinions and workplace |
| `valorar` | verb | opinions and workplace |
| `argumentar` | verb | opinions and workplace |
| `aclarar` | verb | workplace and services |
| `corregir` | verb | workplace and services |
| `cometer` | verb | problems and narration |
| `fallar` | verb | problems and services |
| `funcionar` | verb | problems and services |
| `bloquear` | verb | banking and problems |
| `desbloquear` | verb | banking and services |
| `cargar` | verb | banking and services |
| `cobertura` | noun | health and services |
| `seguridad` | noun | health, housing, and banking |
| `riesgo` | noun | health and banking |
| `daño` | noun | problems and health |
| `avería` | noun | housing and repairs |
| `gasto` | noun | banking and housing |
| `ingreso` | noun | banking and health |
| `saldo` | noun | banking |
| `cargo` | noun | banking and workplace |
| `depósito` | noun | banking and housing |
| `garantía` | noun | services and housing |
| `reserva` | noun | travel and appointments |
| `estancia` | noun | travel and lodging |
| `recepción` | noun | lodging and services |
| `maleta` | noun | travel |
| `embarque` | noun | travel and transit |
| `salida` | noun | travel and transit |
| `llegada` | noun | travel and narration |
| `conexión` | noun | travel and services |
| `frontera` | noun | travel |
| `visado` | noun | travel and services |
| `barrio` | noun | housing and social |
| `edificio` | noun | housing and services |
| `calefacción` | noun | housing and services |
| `mudanza` | noun | housing |
| `contraseña` | noun | services and banking |
| `usuario` | noun | services and technology |
| `aplicación` | noun | services and technology |
| `mensaje` | noun | social and services |
| `llamada` | noun | social and services |
| `código` | noun | services and banking |
| `copia` | noun | workplace and services |
| `firma` | noun | workplace and services |
| `acuerdo` | noun | workplace and conflict |
| `decisión` | noun | workplace and opinions |
| `duda` | noun | opinions and services |
| `opción` | noun | planning and services |
| `ventaja` | noun | opinions and comparisons |
| `desventaja` | noun | opinions and comparisons |
| `culpa` | noun | conflict and problems |
| `error` | noun | problems and services |
| `solución` | noun | problems and solutions |
| `alternativa` | noun | planning and opinions |
| `prioridad` | noun | workplace and planning |
| `responsabilidad` | noun | workplace and obligations |
| `requisito` | noun | services and work |
| `norma` | noun | workplace and services |
| `multa` | noun | services and travel |
| `reclamación` | noun | services and complaints |
| `atención` | noun | services and health |
| `cuidado` | noun | health and social |
| `dolor` | noun | health |
| `fiebre` | noun | health |
| `tos` | noun | health |
| `herida` | noun | health |
| `espalda` | noun | health and body |
| `brazo` | noun | health and body |
| `pierna` | noun | health and body |
| `estómago` | noun | health and body |
| `positivo` | adjective | opinions and health |
| `negativo` | adjective | opinions and health |
| `útil` | adjective | opinions and services |
| `inútil` | adjective | opinions and complaints |

Implemented content delta:

- 90 reviewed Wiktionary lexeme rows.
- 180 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 180 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 180 `sentence_lexeme` joins.
- 180 derived exercises:
  - production and recognition exercises for all 90 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 426 to 516.
- `reviewedSentences` increases from 912 to 1092.
- `reviewedAcceptedAnswers` increases from 915 to 1095.
- `exerciseCount` increases from 852 to 1032.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 360 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-012 Accelerated B1 Public Services, Money, Health, and Housing Pack

**Status:** implemented locally after A2-011.

**Goal:** add learner-ready B1 breadth for common connectors and chunks, emotions/opinions,
public services, money and banking, medical care, housing repairs, workplace conflict, social
interaction, and narration. Rows use the `AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED`
lane with two independent automatic reviewers.

**Target lemmas:**

| Lemma | POS | Domain |
|---|---|---|
| `sin duda` | adverbial phrase | opinions and emphasis |
| `tal vez` | adverbial phrase | opinions and uncertainty |
| `de hecho` | adverbial phrase | connectors and opinions |
| `por supuesto` | adverbial phrase | social interaction |
| `a tiempo` | adverbial phrase | appointments and travel |
| `a menudo` | adverbial phrase | narration and routine |
| `en serio` | adverbial phrase | opinions and social interaction |
| `por cierto` | adverbial phrase | connectors and social interaction |
| `en general` | adverbial phrase | opinions and summaries |
| `cuanto antes` | adverbial phrase | appointments and urgency |
| `hasta ahora` | adverbial phrase | narration |
| `desde entonces` | adverbial phrase | past narration |
| `poco a poco` | adverbial phrase | narration and progress |
| `admitir` | verb | opinions and conflict |
| `exigir` | verb | services and conflict |
| `asumir` | verb | workplace and responsibility |
| `reconocer` | verb | opinions and banking |
| `demostrar` | verb | workplace and opinions |
| `sugerir` | verb | advice and workplace |
| `debatir` | verb | opinions and workplace |
| `interrumpir` | verb | social and workplace conflict |
| `competir` | verb | workplace and goals |
| `liderar` | verb | workplace |
| `supervisar` | verb | workplace |
| `despedir` | verb | workplace conflict |
| `jubilarse` | verb | work and life plans |
| `faltar` | verb | services and problems |
| `sobrar` | verb | money and planning |
| `matricularse` | verb | public services and education |
| `inscribirse` | verb | public services and appointments |
| `votar` | verb | public services |
| `caducar` | verb | public services and banking |
| `autorizar` | verb | public services and banking |
| `financiar` | verb | banking and housing |
| `invertir` | verb | money and planning |
| `gastar` | verb | money and housing |
| `adeudar` | verb | money and obligations |
| `recuperar` | verb | health and money |
| `marearse` | verb | medical |
| `vomitar` | verb | medical |
| `estornudar` | verb | medical |
| `adelgazar` | verb | health |
| `engordar` | verb | health |
| `pintar` | verb | housing and repairs |
| `construir` | verb | housing and work |
| `conectar` | verb | housing and services |
| `desconectar` | verb | housing and services |
| `gotear` | verb | housing and repairs |
| `inundar` | verb | housing and problems |
| `despegar` | verb | travel |
| `hospedarse` | verb | travel and lodging |
| `gobierno` | noun | public services |
| `ayuntamiento` | noun | public services |
| `policía` | noun | public services and safety |
| `bombero` | noun | public services and emergencies |
| `juzgado` | noun | public services |
| `certificado` | noun | public services |
| `impuesto` | noun | public services and money |
| `deuda` | noun | banking |
| `inversión` | noun | banking and planning |
| `transferencia` | noun | banking |
| `interés` | noun | banking and opinions |
| `moneda` | noun | money and travel |
| `enfermera` | noun | medical |
| `ambulancia` | noun | medical and emergency |
| `consulta` | noun | medical and services |
| `vacuna` | noun | medical |
| `pastilla` | noun | medical |
| `sangre` | noun | medical |
| `pecho` | noun | medical and body |
| `rodilla` | noun | medical and body |
| `dedo` | noun | medical and body |
| `vivienda` | noun | housing and public services |
| `techo` | noun | housing and repairs |
| `pared` | noun | housing and repairs |
| `suelo` | noun | housing |
| `grifo` | noun | housing and repairs |
| `tubería` | noun | housing and repairs |
| `cocina` | noun | housing |
| `salón` | noun | housing |
| `empleado` | noun | workplace |
| `candidato` | noun | workplace |
| `puesto` | noun | workplace |
| `ascenso` | noun | workplace |
| `despido` | noun | workplace conflict |
| `turno extra` | noun phrase | workplace |
| `retrasado` | adjective | travel and appointments |
| `mojado` | adjective | housing and weather |
| `seco` | adjective | housing and health |
| `seguramente` | adverb | opinions and uncertainty |

Implemented content delta:

- 90 reviewed Wiktionary lexeme rows.
- 180 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 180 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 180 `sentence_lexeme` joins.
- 180 derived exercises:
  - production and recognition exercises for all 90 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 516 to 606.
- `reviewedSentences` increases from 1092 to 1272.
- `reviewedAcceptedAnswers` increases from 1095 to 1275.
- `exerciseCount` increases from 1032 to 1212.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 360 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-013 Accelerated B1/B2 Bridge Public Systems, Negotiation, Travel, Housing, and Legal Pack

**Status:** implemented locally after A2-012.

**Goal:** add learner-ready B1/B2 bridge breadth for connectors, discourse markers, bureaucracy,
work and social negotiation, health systems, emergencies, travel disruptions, housing/legal, and
money. Rows use the `AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two
independent automatic reviewers.

**Target lemmas:**

| Lemma | POS | Domain |
|---|---|---|
| `no obstante` | adverbial phrase | discourse markers |
| `aun así` | adverbial phrase | discourse markers |
| `en resumen` | adverbial phrase | summaries and narration |
| `en conclusión` | adverbial phrase | summaries and argumentation |
| `por un lado` | adverbial phrase | structured opinions |
| `por otro lado` | adverbial phrase | structured opinions |
| `es decir` | adverbial phrase | clarification chunks |
| `en otras palabras` | adverbial phrase | clarification chunks |
| `al respecto` | adverbial phrase | formal discourse |
| `mientras tanto` | adverbial phrase | narration and sequencing |
| `de todos modos` | adverbial phrase | discourse markers |
| `de inmediato` | adverbial phrase | emergencies and services |
| `a largo plazo` | adverbial phrase | planning and money |
| `a corto plazo` | adverbial phrase | planning and money |
| `a continuación` | adverbial phrase | instructions and bureaucracy |
| `sin falta` | adverbial phrase | appointments and obligations |
| `por adelantado` | adverbial phrase | money and appointments |
| `en efectivo` | adverbial phrase | money and services |
| `con tarjeta` | adverbial phrase | money and services |
| `en persona` | adverbial phrase | public services |
| `mediar` | verb | work and social conflict |
| `conciliar` | verb | negotiation and work |
| `ceder` | verb | negotiation and conflict |
| `reembolsar` | verb | money and services |
| `indemnizar` | verb | legal and money |
| `asegurar` | verb | money housing and safety |
| `cotizar` | verb | money and work |
| `presupuestar` | verb | money and services |
| `liquidar` | verb | banking and legal obligations |
| `endeudarse` | verb | money and planning |
| `hospitalizar` | verb | health systems |
| `derivar` | verb | health and services |
| `monitorizar` | verb | health systems |
| `rehabilitarse` | verb | health systems |
| `desviar` | verb | travel disruptions |
| `reubicar` | verb | travel housing and work |
| `compensar` | verb | services and conflict |
| `desalojar` | verb | housing legal and emergencies |
| `demandar` | verb | legal and conflict |
| `apelar` | verb | legal and bureaucracy |
| `testificar` | verb | legal |
| `certificar` | verb | bureaucracy |
| `homologar` | verb | bureaucracy and work |
| `empadronarse` | verb | public services and housing |
| `solicitud formal` | noun phrase | bureaucracy |
| `expediente` | noun | bureaucracy and legal |
| `denuncia` | noun | legal and public services |
| `cita previa` | noun phrase | public services |
| `seguro médico` | noun phrase | health systems |
| `urgencias` | noun | health systems and emergencies |
| `especialista` | noun | health systems |
| `alergia` | noun | medical |
| `lesión` | noun | medical and body |
| `fractura` | noun | medical and body |
| `radiografía` | noun | medical systems |
| `hipoteca` | noun | housing and banking |
| `nómina` | noun | work and banking |
| `ahorro` | noun | money and planning |
| `tarifa` | noun | money and travel |
| `comisión` | noun | banking and work |
| `recargo` | noun | money and services |
| `inquilino` | noun | housing and legal |
| `propietario` | noun | housing and legal |
| `fianza` | noun | housing and money |
| `comunidad` | noun | housing and public life |
| `contratista` | noun | housing and repairs |
| `humedad` | noun | housing and health |
| `grieta` | noun | housing and repairs |
| `enchufe` | noun | housing and repairs |
| `cancelación` | noun | travel disruptions and appointments |
| `reembolso` | noun | money and travel disruptions |
| `itinerario` | noun | travel |
| `andén` | noun | travel and transit |
| `aduana` | noun | travel and public services |
| `pasajero` | noun | travel |
| `vuelo` | noun | travel disruptions |
| `malentendido` | noun | social conflict |
| `disculpa` | noun | social conflict |
| `tensión` | noun | social and work conflict |
| `mediación` | noun | social and legal conflict |
| `acoso` | noun | work and legal conflict |
| `testigo` | noun | legal and public services |
| `abogado` | noun | legal and services |
| `juez` | noun | legal |
| `prueba legal` | noun phrase | legal |
| `prioritario` | adjective | emergencies and services |
| `leve` | adjective | medical and legal |
| `obligado` | adjective | obligations and bureaucracy |
| `autorizado` | adjective | bureaucracy and services |
| `pendiente de pago` | adjective phrase | money and bureaucracy |
| `apto` | adjective | health work and bureaucracy |
| `válido` | adjective | bureaucracy and travel |
| `vencido` | adjective | bureaucracy and banking |
| `imprescindible` | adjective | formal opinions and bureaucracy |
| `razonable` | adjective | negotiation and opinions |
| `abusivo` | adjective | legal money and conflict |
| `confidencial` | adjective | work and bureaucracy |
| `presencial` | adjective | public services and work |
| `remoto` | adjective | work and services |
| `aproximado` | adjective | money and planning |

Implemented content delta:

- 100 reviewed Wiktionary lexeme rows.
- 200 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 200 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 200 `sentence_lexeme` joins.
- 200 derived exercises:
  - production and recognition exercises for all 100 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 606 to 706.
- `reviewedSentences` increases from 1272 to 1472.
- `reviewedAcceptedAnswers` increases from 1275 to 1475.
- `exerciseCount` increases from 1212 to 1412.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 400 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-014 Accelerated B1/B2 Bridge Everyday Systems, Repair, and Opinion Pack

**Status:** implemented locally after A2-013.

**Goal:** add learner-ready B1/B2 bridge breadth for high-frequency connectors and chunks,
conversation repair, argument and opinion language, household repairs, legal and medical systems,
money, work, travel, and service recovery. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:**

| Lemma | POS | Domain |
|---|---|---|
| `en cambio` | adverbial phrase | argument and contrast |
| `salvo` | preposition | exceptions and conditions |
| `debido a` | prepositional phrase | reasons and problems |
| `gracias a` | prepositional phrase | reasons and outcomes |
| `al contrario` | adverbial phrase | argument and repair |
| `en cualquier caso` | adverbial phrase | discourse markers |
| `en ese caso` | adverbial phrase | conditions and repair |
| `por si acaso` | adverbial phrase | planning and precaution |
| `a propósito` | adverbial phrase | conversation and intent |
| `desde luego` | adverbial phrase | agreement and emphasis |
| `al fin y al cabo` | adverbial phrase | argument and summaries |
| `por ahora` | adverbial phrase | planning and status |
| `por lo menos` | adverbial phrase | argument and estimates |
| `por lo visto` | adverbial phrase | uncertainty and narration |
| `en principio` | adverbial phrase | formal planning |
| `en realidad` | adverbial phrase | clarification |
| `de nuevo` | adverbial phrase | repair and repetition |
| `otra vez` | adverbial phrase | repair and repetition |
| `a la vez` | adverbial phrase | coordination and work |
| `al menos` | adverbial phrase | estimates and repair |
| `en vez de` | prepositional phrase | choices and repair |
| `a mano` | adverbial phrase | forms and household |
| `a domicilio` | adverbial phrase | services and household |
| `de guardia` | adverbial phrase | medical and emergencies |
| `fuera de servicio` | adjective phrase | travel and services |
| `en servicio` | adjective phrase | travel and services |
| `de acuerdo con` | prepositional phrase | rules and formal speech |
| `con respecto a` | prepositional phrase | formal discourse |
| `por separado` | adverbial phrase | forms and money |
| `por escrito` | adverbial phrase | bureaucracy and legal |
| `verbalmente` | adverb | work and legal |
| `sinceramente` | adverb | opinions and repair |
| `justamente` | adverb | argument and emphasis |
| `precisamente` | adverb | argument and emphasis |
| `probablemente` | adverb | uncertainty and planning |
| `raramente` | adverb | frequency and narration |
| `posteriormente` | adverb | formal sequencing |
| `diariamente` | adverb | routines and health |
| `semanalmente` | adverb | routines and money |
| `mensualmente` | adverb | routines and money |
| `sustituir` | verb | services and repairs |
| `actualizar` | verb | services and bureaucracy |
| `adelantar` | verb | appointments and planning |
| `interrogar` | verb | legal and conflict |
| `investigar` | verb | legal and problems |
| `encargarse` | verb | work and services |
| `sellar` | verb | bureaucracy and household |
| `escanear` | verb | bureaucracy and technology |
| `adjuntar` | verb | bureaucracy and technology |
| `audiencia` | noun | legal and public life |
| `juzgar` | verb | legal and opinions |
| `declarar` | verb | legal and bureaucracy |
| `comparecer` | verb | legal and bureaucracy |
| `sancionar` | verb | legal and public services |
| `multar` | verb | legal and travel |
| `recurso` | noun | legal and bureaucracy |
| `apelación` | noun | legal |
| `sentencia` | noun | legal |
| `acusación` | noun | legal and conflict |
| `defensa legal` | noun phrase | legal |
| `asesoría` | noun | work legal and money |
| `notaría` | noun | legal and bureaucracy |
| `registro civil` | noun phrase | public services |
| `certificado médico` | noun phrase | medical and work |
| `alta médica` | noun phrase | medical systems |
| `baja médica` | noun phrase | medical and work |
| `cita médica` | noun phrase | medical systems |
| `mareo` | noun | medical symptoms |
| `vómito` | noun | medical symptoms |
| `estornudo` | noun | medical symptoms |
| `análisis de sangre` | noun phrase | medical systems |
| `presión arterial` | noun phrase | medical systems |
| `seguro privado` | noun phrase | health and money |
| `tarjeta sanitaria` | noun phrase | health systems |
| `centro de salud` | noun phrase | health systems |
| `persiana` | noun | household and repairs |
| `bombilla` | noun | household and repairs |
| `interruptor` | noun | household and repairs |
| `calentador` | noun | household and repairs |
| `nevera` | noun | household |
| `lavadora` | noun | household |
| `fregadero` | noun | household and repairs |
| `horno` | noun | household and food |
| `colchón` | noun | household and lodging |
| `armario` | noun | household |
| `pasillo` | noun | housing and travel |
| `balcón` | noun | housing |
| `escalera` | noun | housing and travel |
| `ruido` | noun | housing and complaints |
| `reforma` | noun | housing and services |
| `sueldo` | noun | work and money |
| `convenio` | noun | work and legal |
| `jornada laboral` | noun phrase | work |
| `contrato temporal` | noun phrase | work and legal |
| `baja laboral` | noun phrase | work and medical |
| `permiso laboral` | noun phrase | work and bureaucracy |
| `entrevista` | noun | work and social |
| `currículum` | noun | work |
| `departamento` | noun | work and services |
| `equipo de trabajo` | noun phrase | work and collaboration |
| `puerta de embarque` | noun phrase | travel |
| `tarjeta de embarque` | noun phrase | travel |
| `transbordo` | noun | travel and transit |
| `atención al cliente` | noun phrase | services and complaints |
| `hoja de reclamaciones` | noun phrase | services and legal |
| `servicio técnico` | noun phrase | services and repairs |
| `devolución` | noun | shopping and services |
| `cambio de producto` | noun phrase | shopping and services |
| `factura electrónica` | noun phrase | money and services |
| `cajero automático` | noun phrase | banking and travel |
| `cuenta corriente` | noun phrase | banking |
| `cargo bancario` | noun phrase | banking and complaints |
| `saldo disponible` | noun phrase | banking |
| `tipo de interés` | noun phrase | banking and money |
| `pago pendiente` | noun phrase | money and obligations |
| `recibo domiciliado` | noun phrase | banking and housing |
| `presupuesto cerrado` | noun phrase | money and services |
| `contrato escrito` | noun phrase | legal and work |
| `acuerdo verbal` | noun phrase | work and legal |
| `en mi opinión` | adverbial phrase | opinion language |

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived exercises:
  - production and recognition exercises for all 120 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 706 to 826.
- `reviewedSentences` increases from 1472 to 1712.
- `reviewedAcceptedAnswers` increases from 1475 to 1715.
- `exerciseCount` increases from 1412 to 1652.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-020 Accelerated B1/B2 Conversation Repair, Documents, Banking, Housing, Medical, Work, and Travel Pack

**Status:** implemented locally after A2-019.

**Goal:** add learner-ready B1/B2 breadth for conversation repair, discourse markers, appointment
timing, digital documents, banking and billing issues, household repairs, medical/work leave,
support complaints, legal/work agreements, travel disruptions, and safety phrases. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:** `aclaración rápida`, `para aclarar`, `no entiendo bien`, `hay
interferencias`, `la voz se pierde`, `me he equivocado`, `tiene sentido`, `no tiene sentido`,
`eso me ayuda`, `lo reviso ahora`, `en resumen`, `por cierto`, `en otras palabras`, `para ser
claro`, `lo digo de otra manera`, `me explico mejor`, `espero su respuesta`, `salvo error`,
`queda claro`, `queda pendiente`, `a primera hora`, `a última hora`, `lo antes posible`, `como
muy tarde`, `con tiempo suficiente`, `sin perder tiempo`, `sin cumplir el plazo`, `plazo
ampliado`, `cita reprogramada`, `turno disponible`, `documentación completa`, `documentación
pendiente`, `confirmación por escrito`, `comprobante bancario`, `documento legible`, `documento
escaneado`, `archivo dañado`, `enlace caducado`, `contraseña caducada`, `sesión cerrada`,
`documento ilegible`, `cargo rechazado`, `sello digital`, `interés aplicado`, `sello oficial`,
`pago fraccionado`, `ingreso en cuenta`, `devolución aprobada`, `reembolso pendiente`, `factura
desglosada`, `importe cobrado`, `recargo indebido`, `aviso de corte`, `suministro cortado`,
`cuota atrasada`, `saldo retenido`, `llave rota`, `cerradura bloqueada`, `calefacción apagada`,
`ruido constante`, `vecino ruidoso`, `tarifa plana`, `fianza devuelta`, `informe médico`,
`gastos bancarios`, `cuenta domiciliada`, `apagón repentino`, `agua interrumpida`, `dolor
leve`, `mareo fuerte`, `puerta atascada`, `presión alta`, `seguro médico`, `ventana rota`,
`humedad en la pared`, `moho visible`, `medida urgente`, `solución temporal`, `solución
definitiva`, `problema recurrente`, `error frecuente`, `incidencia abierta`, `incidencia
resuelta`, `cita telefónica`, `análisis pendiente`, `reclamación formal`, `queja por escrito`,
`respuesta oficial`, `resultado positivo`, `resultado negativo`, `reposo relativo`, `oferta
laboral`, `entrevista pendiente`, `turno cambiado`, `jornada partida`, `baja voluntaria`,
`reunión aplazada`, `tarea urgente`, `prioridad alta`, `viaje retrasado`, `vuelo perdido`,
`billete cambiado`, `reserva anulada`, `habitación disponible`, `recepción cerrada`, `entrada
anticipada`, `preaviso laboral`, `dirección exacta`, `punto de encuentro`, `puesto indefinido`,
`zona restringida`, `acceso principal`, `viaje cancelado`, `tren cancelado`, `mensaje leído`,
`mensaje borrado`, `correo no deseado`, `notificación nueva`, `aviso leído`, `respuesta leída`,
`opción recomendada`, `opción descartada`, `decisión tomada`, `decisión pendiente`, `autobús
sustituido`, `acuerdo escrito`, `trato justo`, `malentendido común`, `situación incómoda`,
`comentario inapropiado`, `disculpa sincera`, `apoyo necesario`, `ayuda inmediata`, `riesgo
alto`, `riesgo bajo`, `zona segura`.

Implemented content delta:

- 136 reviewed Wiktionary lexeme rows.
- 272 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 272 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 272 `sentence_lexeme` joins.
- 272 derived exercises:
  - production and recognition exercises for all 136 target lemmas.

Acceptance target:

- `learnerReadyLexemes` increases from 1449 to 1585.
- `reviewedSentences` increases from 2958 to 3230.
- `reviewedAcceptedAnswers` increases from 2961 to 3233.
- `exerciseCount` increases from 2898 to 3170.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 544 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-016 Accelerated B1/B2 Repair, Systems, and Services Pack

**Status:** implemented locally after A2-015.

**Goal:** add learner-ready B1/B2 breadth for listening-friendly repair chunks, phone/service
phrases, money/banking, medical/work/legal/travel systems, household repairs, and public-service
paperwork. Rows use the `AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two
independent automatic reviewers.

**Target lemmas:** `cómo digo`, `cómo se dice`, `no capto`, `no entiendo la palabra`,
`hable claro`, `mande un mensaje`, `déjeme pensar`, `déjeme verlo`, `vuelvo enseguida`,
`gracias por avisar`, `gracias por esperar`, `perdón por molestar`, `sin problema`,
`con permiso`, `por favor avise`, `quedo atento`, `estoy disponible`, `estoy ocupado`,
`no puedo atender`, `llámeme luego`, `avísame cuando puedas`, `según entiendo`,
`según me dicen`, `por lo general`, `en concreto`, `en parte`, `de todas maneras`,
`a más tardar`, `fuera de plazo`, `bajo petición`, `a nombre de`, `a cargo de`,
`en nombre de`, `de forma urgente`, `de forma segura`, `mediante transferencia`,
`pago aplazado`, `pago inicial`, `saldo pendiente`, `cobro indebido`, `recibo pendiente`,
`aviso de pago`, `límite de crédito`, `retirada de efectivo`, `ingreso bancario`,
`número de póliza`, `historial médico`, `receta médica`, `parte médico`,
`consulta telefónica`, `seguro dental`, `centro médico`, `médico de guardia`,
`dolor de garganta`, `fiebre alta`, `justificante médico`, `dolor muscular`,
`prueba rápida`, `informe clínico`, `sala de urgencias`, `servicio urgente`,
`número de reserva`, `billete de vuelta`, `retraso del vuelo`, `cambio de andén`,
`conexión perdida`, `equipaje facturado`, `seguro de viaje`, `permiso de residencia`,
`permiso de trabajo`, `turno de mañana`, `turno de noche`, `nómina mensual`,
`puesto vacante`, `entrevista de trabajo`, `oferta de empleo`, `horario flexible`,
`teletrabajo`, `convenio colectivo`, `sindicato`, `indemnización`, `recurso legal`,
`denuncia formal`, `demanda judicial`, `antecedentes penales`, `poder notarial`,
`copia compulsada`, `firma digital`, `certificado digital`, `cita administrativa`,
`tasa administrativa`, `documento adjunto`, `copia de seguridad`, `pantalla`, `altavoz`,
`micrófono`, `auriculares`, `señal`, `ruido de fondo`, `mensaje de voz`,
`llamada perdida`, `videollamada`, `taller mecánico`, `pieza de repuesto`,
`presupuesto previo`, `reparación urgente`, `fuga de agua`, `daño material`,
`seguro obligatorio`, `comunidad de vecinos`, `contrato de alquiler`, `gastos incluidos`,
`recibo de luz`, `lectura del contador`, `avería eléctrica`, `entrega a domicilio`,
`libro de familia`, `padrón municipal`, `declaración de renta`, `justicia gratuita`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived exercises:
  - production and recognition exercises for all 120 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 946 to 1066.
- `reviewedSentences` increases from 1952 to 2192.
- `reviewedAcceptedAnswers` increases from 1955 to 2195.
- `exerciseCount` increases from 1892 to 2132.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-015 Accelerated B1/B2 Fluency, Listening Repair, Systems, and Travel Pack

**Status:** implemented locally after A2-014.

**Goal:** add learner-ready B1/B2 breadth for high-frequency fluency chunks,
pronunciation/listening-friendly repair phrases, household/legal/medical/money/work/travel
interactions, and everyday conversation repair. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:**

| Lemma | POS | Domain |
|---|---|---|
| `a ver` | discourse marker | conversation repair |
| `o sea` | discourse marker | conversation repair |
| `me refiero a` | verbal phrase | clarification |
| `quiero decir` | verbal phrase | clarification |
| `si no me equivoco` | adverbial phrase | careful speech |
| `corrígeme si me equivoco` | sentence chunk | conversation repair |
| `dicho de otra manera` | adverbial phrase | clarification |
| `por así decirlo` | adverbial phrase | argument nuance |
| `en pocas palabras` | adverbial phrase | summaries |
| `en definitiva` | adverbial phrase | summaries and opinion |
| `para empezar` | adverbial phrase | sequencing |
| `para terminar` | adverbial phrase | sequencing |
| `en primer lugar` | adverbial phrase | structured argument |
| `en segundo lugar` | adverbial phrase | structured argument |
| `por último` | adverbial phrase | sequencing |
| `por una parte` | adverbial phrase | structured opinion |
| `por otra parte` | adverbial phrase | structured opinion |
| `sea como sea` | adverbial phrase | argument repair |
| `de todas formas` | adverbial phrase | discourse markers |
| `de momento` | adverbial phrase | status and planning |
| `hasta entonces` | adverbial phrase | time and planning |
| `desde luego que sí` | sentence chunk | agreement |
| `claro que no` | sentence chunk | disagreement |
| `ni hablar` | sentence chunk | strong disagreement |
| `ni modo` | sentence chunk | reaction chunks |
| `qué va` | sentence chunk | informal disagreement |
| `ya veo` | sentence chunk | listening and repair |
| `entiendo` | sentence chunk | listening and repair |
| `lo siento` | sentence chunk | apologies |
| `perdona` | sentence chunk | apologies and repair |
| `disculpe` | sentence chunk | formal repair |
| `un momento` | sentence chunk | conversation repair |
| `espere un momento` | sentence chunk | service interaction |
| `hable más despacio` | sentence chunk | listening repair |
| `no le oigo` | sentence chunk | listening repair |
| `se corta la llamada` | sentence chunk | phone repair |
| `se oye mal` | sentence chunk | listening repair |
| `repita por favor` | sentence chunk | listening repair |
| `puede repetir` | sentence chunk | listening repair |
| `cómo se pronuncia` | question chunk | pronunciation repair |
| `cómo se escribe` | question chunk | spelling repair |
| `qué significa` | question chunk | meaning repair |
| `a qué se refiere` | question chunk | clarification |
| `no me queda claro` | sentence chunk | clarification |
| `me queda claro` | sentence chunk | confirmation |
| `estoy de acuerdo` | sentence chunk | agreement |
| `no estoy seguro` | sentence chunk | uncertainty |
| `depende` | sentence chunk | uncertainty |
| `puede ser` | sentence chunk | uncertainty |
| `me preocupa` | sentence chunk | concerns and opinion |
| `me molesta` | sentence chunk | complaints |
| `me conviene` | sentence chunk | preferences |
| `me interesa` | sentence chunk | preferences |
| `me cuesta` | sentence chunk | difficulty and repair |
| `me hace falta` | sentence chunk | needs and services |
| `me falta` | sentence chunk | needs and paperwork |
| `me sobra` | sentence chunk | money and quantities |
| `me urge` | sentence chunk | urgency and services |
| `me da miedo` | sentence chunk | emotions and medical |
| `me da vergüenza` | sentence chunk | emotions and repair |
| `me da rabia` | sentence chunk | emotions and complaints |
| `me da pena` | sentence chunk | emotions |
| `me alegra` | sentence chunk | emotions and social |
| `quedar en algo` | verbal phrase | negotiation |
| `ponerse de acuerdo` | verbal phrase | negotiation |
| `llegar a un acuerdo` | verbal phrase | negotiation |
| `romper el acuerdo` | verbal phrase | legal and conflict |
| `hacer falta` | verbal phrase | needs and services |
| `tener sentido` | verbal phrase | opinion and repair |
| `tener en cuenta` | verbal phrase | planning and argument |
| `darse cuenta` | verbal phrase | narration and repair |
| `echar de menos` | verbal phrase | emotions and social |
| `llevar a cabo` | verbal phrase | formal work |
| `poner en marcha` | verbal phrase | work and services |
| `dar de alta` | verbal phrase | medical and services |
| `dar de baja` | verbal phrase | services and work |
| `estar al tanto` | verbal phrase | work and updates |
| `estar pendiente` | verbal phrase | status and planning |
| `enviar adjunto` | verbal phrase | bureaucracy and technology |
| `acuse de recibo` | noun phrase | bureaucracy and legal |
| `plazo de entrega` | noun phrase | services and work |
| `fecha límite` | noun phrase | work and bureaucracy |
| `lista de espera` | noun phrase | medical and services |
| `número de expediente` | noun phrase | bureaucracy and legal |
| `código postal` | noun phrase | forms and addresses |
| `dirección fiscal` | noun phrase | taxes and bureaucracy |
| `domicilio actual` | noun phrase | forms and housing |
| `titular de cuenta` | noun phrase | banking |
| `justificante de pago` | noun phrase | money and bureaucracy |
| `orden de pago` | noun phrase | banking |
| `recargo por demora` | noun phrase | money and complaints |
| `interés de demora` | noun phrase | banking and legal |
| `impago` | noun | money and legal |
| `deudor` | noun | money and legal |
| `acreedor` | noun | money and legal |
| `aval` | noun | banking and housing |
| `garante` | noun | banking and housing |
| `horas extra` | noun phrase | work and money |
| `periodo de prueba` | noun phrase | work |
| `desempleo` | noun | work and public services |
| `sala de espera` | noun phrase | medical and services |
| `consulta externa` | noun phrase | medical systems |
| `urgencia médica` | noun phrase | medical emergencies |
| `dolor agudo` | noun phrase | medical symptoms |
| `dolor crónico` | noun phrase | medical symptoms |
| `malestar` | noun | medical symptoms |
| `náusea` | noun | medical symptoms |
| `tos seca` | noun phrase | medical symptoms |
| `falta de aire` | noun phrase | medical symptoms |
| `dificultad respiratoria` | noun phrase | medical symptoms |
| `alquiler mensual` | noun phrase | housing and money |
| `seguro de hogar` | noun phrase | housing and money |
| `corte de luz` | noun phrase | household emergencies |
| `corte de agua` | noun phrase | household emergencies |
| `fuga de gas` | noun phrase | household emergencies |
| `llave de repuesto` | noun phrase | housing |
| `hora de salida` | noun phrase | travel |
| `control de seguridad` | noun phrase | travel |
| `pérdida de equipaje` | noun phrase | travel disruptions |
| `salida de emergencia` | noun phrase | travel and emergencies |

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived exercises:
  - production and recognition exercises for all 120 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 826 to 946.
- `reviewedSentences` increases from 1712 to 1952.
- `reviewedAcceptedAnswers` increases from 1715 to 1955.
- `exerciseCount` increases from 1652 to 1892.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-017 Accelerated B1/B2 Discourse, Legal/Money, Medical, Work, Travel, and Services Pack

**Status:** implemented locally after A2-016.

**Goal:** add learner-ready B1/B2 breadth for high-frequency fluency chunks, discourse markers,
conversation repair, legal/money/medical/work/travel/service interactions, lodging, housing
repairs, and practical full-sentence prompts. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:** `para que quede claro`, `dicho esto`, `a todo esto`,
`ahora que lo dices`, `pese a ello`, `a pesar de todo`, `así que`, `por consiguiente`,
`en consecuencia`, `por si fuera poco`, `ni siquiera`, `al parecer`,
`con toda seguridad`, `desde mi punto de vista`, `a mi parecer`, `tengo entendido`,
`por lo que sé`, `que yo sepa`, `si hace falta`, `si te parece`, `si le parece`,
`cuando quieras`, `cuando pueda`, `me parece bien`, `me parece mal`, `no pasa nada`,
`da igual`, `más o menos`, `más bien`, `mejor dicho`, `para decirlo claro`,
`para ser sincero`, `la verdad es que`, `qué quieres decir`, `no te sigo`, `no le sigo`,
`voy a comprobarlo`, `lo compruebo ahora`, `déjeme comprobarlo`, `me puede ayudar`,
`necesito aclarar`, `tengo otra duda`, `banca en línea`, `transferencia bancaria`,
`domiciliación bancaria`, `cuota mensual`, `recibo bancario`, `cargo pendiente`,
`pago rechazado`, `reclamación bancaria`, `atención telefónica`, `número de atención`,
`correo certificado`, `notificación oficial`, `sede electrónica`, `formulario en línea`,
`plazo legal`, `cita judicial`, `asesoría legal`, `contrato indefinido`, `salario bruto`,
`salario neto`, `permiso retribuido`, `vacaciones pagadas`, `reunión pendiente`,
`acta de reunión`, `plan de trabajo`, `carga de trabajo`, `horario partido`,
`guardia médica`, `centro hospitalario`, `urgencias pediátricas`, `dolor abdominal`,
`dolor de pecho`, `erupción cutánea`, `picor`, `hinchazón`, `herida abierta`,
`resonancia magnética`, `ecografía`, `consulta de seguimiento`, `tratamiento médico`,
`dosis diaria`, `efecto secundario`, `alta hospitalaria`, `farmacia cercana`,
`mostrador de embarque`, `control de pasaportes`, `zona de llegadas`, `zona de salidas`,
`mostrador de información`, `servicio de equipajes`, `reclamación de equipaje`,
`cancelación del vuelo`, `cambio de asiento`, `reserva confirmada`,
`alojamiento temporal`, `habitación individual`, `habitación doble`, `recepción del hotel`,
`llave de habitación`, `servicio de limpieza`, `salida tardía`, `depósito de seguridad`,
`caldera`, `termostato`, `regleta`, `ventana corredera`, `fontanero`, `cerrajero`,
`electricista`, `administrador de finca`, `gastos de comunidad`, `derrame`, `gotera`,
`moho`, `contrato de suministro`, `alta de luz`, `baja de servicio`, `repartidor`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived exercises:
  - production and recognition exercises for all 120 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 1066 to 1186.
- `reviewedSentences` increases from 2192 to 2432.
- `reviewedAcceptedAnswers` increases from 2195 to 2435.
- `exerciseCount` increases from 2132 to 2372.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-018 Accelerated B1/B2 Practical Fluency, Services, Money, Medical, Work, and Travel Pack

**Status:** implemented locally after A2-017.

**Goal:** add learner-ready B1/B2 breadth for short listening-friendly discourse chunks,
conversation repair, service interactions, bureaucracy, legal/money workflows, medical systems,
workplace language, transit, travel disruptions, and lodging. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:** `en fin`, `antes que nada`, `sobre todo`, `a partir de ahora`,
`tarde o temprano`, `de vez en cuando`, `de verdad`, `por desgracia`, `por suerte`,
`menos mal`, `como mínimo`, `como máximo`, `vale la pena`, `no vale la pena`,
`ahora mismo`, `en seguida`, `por aquí`, `por allí`, `a lo mejor`, `por casualidad`,
`de memoria`, `de acuerdo contigo`, `no estoy de acuerdo`, `me explico`, `explíqueme`,
`perdón, no entendí`, `puede hablar más alto`, `puede escribirlo`, `lo digo por esto`,
`no quise decir eso`, `lo reviso y le aviso`, `le llamo en cuanto pueda`,
`le envío el documento`, `quedo a la espera`, `gracias de antemano`, `sentido común`,
`punto de vista`, `queja formal`, `servicio al cliente`, `número de seguimiento`,
`paquete perdido`, `entrega pendiente`, `recogida en tienda`, `devolución gratuita`,
`garantía extendida`, `datos personales`, `protección de datos`, `consentimiento firmado`,
`copia del contrato`, `cláusula abusiva`, `aviso previo`, `incumplimiento`,
`multa administrativa`, `trámite pendiente`, `solicitud oficial`,
`respuesta por escrito`, `descuento aplicado`, `cargo duplicado`, `comisión bancaria`,
`extracto bancario`, `límite diario`, `cuenta bloqueada`, `clave de acceso`,
`contraseña temporal`, `recuperar contraseña`, `identificación oficial`,
`ingreso mensual`, `gasto fijo`, `presupuesto familiar`, `ahorro mensual`,
`préstamo personal`, `analítica de sangre`, `resultado médico`, `informe de alta`,
`cansancio`, `ansiedad`, `inyección`, `tensión arterial`, `seguro laboral`,
`jornada completa`, `jornada parcial`, `riesgo laboral`, `seguridad social`,
`recursos humanos`, `responsable directo`, `turno partido`, `viaje de trabajo`,
`billete electrónico`, `escala corta`, `retraso acumulado`, `transporte público`,
`abono mensual`, `parada cercana`, `ruta alternativa`, `mapa sin conexión`,
`reserva cancelada`, `confirmación por correo`, `a fin de cuentas`, `para variar`,
`por mi parte`, `por tu parte`, `hasta aquí`, `de paso`, `sin querer`, `sin prisa`,
`en conjunto`, `cada vez más`, `cada vez menos`, `copia simple`, `contrato firmado`,
`firma manuscrita`, `tasa pendiente`, `oficina virtual`, `buzón electrónico`,
`cita confirmada`, `documento vencido`, `autorización firmada`,
`reclamación pendiente`, `respuesta automática`, `atención presencial`,
`horario de atención`, `dolor lumbar`, `dolor cervical`, `receta electrónica`,
`historial clínico`, `urgencia dental`, `revisión médica`, `prueba diagnóstica`,
`tratamiento urgente`, `inflamación`, `sueldo base`, `nómina atrasada`,
`convenio laboral`, `jornada intensiva`, `puesto fijo`, `conexión cancelada`,
`equipaje de mano`, `escala larga`, `cambio de puerta`, `autobús nocturno`,
`tren regional`, `estación central`, `alojamiento reservado`.

Implemented content delta:

- 143 reviewed Wiktionary lexeme rows.
- 286 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 286 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 286 `sentence_lexeme` joins.
- 286 derived exercises:
  - production and recognition exercises for all 143 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 1186 to 1329.
- `reviewedSentences` increases from 2432 to 2718.
- `reviewedAcceptedAnswers` increases from 2435 to 2721.
- `exerciseCount` increases from 2372 to 2658.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 572 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-019 Accelerated B1/B2 Confirmations, Service Status, Money, Documents, and Medical Pack

**Status:** implemented locally after A2-018.

**Goal:** add learner-ready B1/B2 breadth for short confirmation and apology chunks, scheduling,
service status, public-service documents, payment/invoice workflows, account access, medical
follow-up, and work/leave vocabulary. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:** `por favor confirme`, `confirme la recepción`, `recibido, gracias`,
`no hay problema`, `sin inconveniente`, `con mucho gusto`, `lo siento mucho`,
`perdón por el retraso`, `se lo agradezco`, `le agradezco la ayuda`, `me viene bien`,
`no me viene bien`, `me encaja`, `no me encaja`, `mejor otro día`,
`cuando le vaya bien`, `si no es molestia`, `si fuera posible`,
`en cuanto tenga tiempo`, `antes de que cierre`, `después de la reunión`,
`por el momento`, `al mismo tiempo`, `por una razón sencilla`, `en mi experiencia`,
`según mi experiencia`, `según el contrato`, `según la factura`, `según el informe`,
`según el médico`, `según la empresa`, `por teléfono`, `a distancia`,
`con cita previa`, `sin cita previa`, `fuera de horario`, `dentro del plazo`,
`con antelación`, `sin aviso`, `aviso urgente`, `mensaje urgente`, `correo urgente`,
`llamada urgente`, `respuesta pendiente`, `solicitud pendiente`, `firma pendiente`,
`revisión pendiente`, `copia pendiente`, `reserva pendiente`, `confirmación pendiente`,
`cambio pendiente`, `caso abierto`, `caso cerrado`, `número de caso`,
`número de cliente`, `número de contrato`, `número de factura`,
`fecha de vencimiento`, `fecha de pago`, `fecha de entrega`, `fecha de entrada`,
`fecha de salida`, `importe total`, `importe pendiente`, `importe exacto`,
`precio final`, `precio aproximado`, `coste adicional`, `gasto adicional`,
`recargo adicional`, `saldo insuficiente`, `tarjeta bloqueada`, `tarjeta caducada`,
`transferencia pendiente`, `transferencia recibida`, `pago confirmado`,
`pago anulado`, `recibo duplicado`, `factura vencida`, `factura corregida`,
`presupuesto aprobado`, `presupuesto rechazado`, `contrato renovado`,
`contrato vencido`, `servicio cancelado`, `servicio activo`, `servicio suspendido`,
`alta confirmada`, `baja confirmada`, `acceso denegado`, `acceso permitido`,
`usuario registrado`, `perfil actualizado`, `código de verificación`,
`código incorrecto`, `archivo adjunto`, `documento firmado`, `formulario incompleto`,
`formulario enviado`, `copia digital`, `copia impresa`, `certificado válido`,
`certificado vencido`, `permiso vigente`, `permiso vencido`, `seguro vigente`,
`seguro vencido`, `revisión médica pendiente`, `consulta urgente`,
`cita de seguimiento`, `tratamiento pendiente`, `medicación habitual`,
`medicación nueva`, `alergia conocida`, `síntoma nuevo`, `fiebre persistente`,
`herida infectada`, `resultado pendiente`, `prueba pendiente`, `baja temporal`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived exercises:
  - production and recognition exercises for all 120 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 1329 to 1449.
- `reviewedSentences` increases from 2718 to 2958.
- `reviewedAcceptedAnswers` increases from 2721 to 2961.
- `exerciseCount` increases from 2658 to 2898.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-036 Accelerated B1/B2 Conversation, Bureaucracy, Money, Health, Repairs, Travel, Work, and Digital Pack

**Status:** implemented locally after A2-035.

**Goal:** add learner-ready B1/B2 breadth for conversation repair, formal requests, legal and
bureaucratic paperwork, banking, medical and household problems, travel disruption, workplace
coordination, and digital-service vocabulary. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:** `conversación tranquila`, `conversación difícil`, `frase útil`, `frase educada`,
`pregunta breve`, `respuesta útil`, `respuesta educada`, `comentario sincero`, `tono tranquilo`,
`tono respetuoso`, `aclaración útil`, `confusión inicial`, `desacuerdo leve`, `trámite digital`,
`trámite provincial`, `certificado municipal`, `permiso municipal`, `expediente pendiente`,
`expediente digital`, `plazo administrativo`, `plazo prorrogado`, `copia sellada`,
`denuncia pendiente`, `cuota pendiente`, `deuda antigua`, `deuda familiar`, `ingreso variable`,
`pago parcial`, `recibo electrónico`, `cajero disponible`, `tarjeta temporal`, `límite mensual`,
`dolor constante`, `tos persistente`, `tos nocturna`, `síntoma reciente`, `alergia estacional`,
`tensión alta`, `cobertura médica`, `centro sanitario`, `espera larga`, `receta nueva`,
`control médico`, `infección reciente`, `vendaje seco`, `consulta dental`, `urgencia familiar`,
`cerradura atascada`, `tubería bloqueada`, `fuga visible`, `fuga interna`, `bombilla fundida`,
`enchufe roto`, `cable suelto`, `calefacción rota`, `aire frío`, `lavadora nueva`, `horno apagado`,
`visita urgente`, `reparación provisional`, `vuelo nocturno`, `andén cerrado`, `desayuno temprano`,
`cambio de horario`, `billete digital`, `terminal nueva`, `tarea pendiente`, `tarea prioritaria`,
`supervisor directo`, `equipo nuevo`, `contrato pendiente`, `llamada interna`, `cliente nuevo`,
`error técnico`, `queja pendiente`, `solución provisional`, `objetivo mensual`,
`resultado parcial`, `enlace temporal`, `archivo ligero`, `carpeta nueva`, `copia reciente`,
`actualización reciente`, `aplicación nueva`, `mensaje privado`, `cita municipal`,
`oficina regional`, `oficina central`, `solicitud digital`, `solicitud urgente`,
`autorización pendiente`, `autorización temporal`, `formulario obligatorio`,
`certificado familiar`, `comprobante impreso`, `comprobante digital`, `número provisional`,
`turno administrativo`, `ventanilla cerrada`, `tarifa reducida`, `tarifa mensual`, `ingreso anual`,
`gasto anual`, `pago automático`, `tarjeta prepago`, `transferencia automática`, `comisión fija`,
`consulta rápida`, `revisión dental`, `prueba negativa`, `prueba positiva`, `fiebre baja`,
`tratamiento corto`, `pastilla diaria`, `dosis correcta`, `pieza suelta`, `pieza dañada`,
`técnico autorizado`, `técnico disponible`, `aparato roto`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived exercises:
  - production and recognition exercises for all 120 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 3351 to 3471.
- `reviewedSentences` increases from 6762 to 7002.
- `reviewedAcceptedAnswers` increases from 6765 to 7005.
- `exerciseCount` increases from 6702 to 6942.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-037 Accelerated B1/B2 Conversation, Bureaucracy, Legal, Money, Health, Repairs, Travel, Work, and Digital Pack

**Status:** implemented locally after A2-036.

**Goal:** add learner-ready B1/B2 breadth for conversation repair, public-service paperwork,
legal claims, banking and billing, medical follow-up, household repairs, travel disruption,
work coordination, and digital-security vocabulary. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:** `pregunta cerrada`, `pregunta neutral`, `pregunta final`, `pregunta oral`,
`pregunta natural`, `pregunta previa`, `pregunta educada`, `pregunta común`, `pregunta firme`,
`pregunta respetuosa`, `pregunta sincera`, `pregunta detallada`, `respuesta abierta`,
`respuesta cerrada`, `solicitud firmada`, `solicitud incompleta`, `solicitud obligatoria`,
`solicitud provisional`, `solicitud municipal`, `solicitud provincial`, `solicitud prorrogada`,
`solicitud sellada`, `solicitud administrativa`, `solicitud electrónica`, `solicitud válida`,
`solicitud única`, `solicitud regional`, `formulario provisional`, `contrato dudoso`,
`contrato obligatorio`, `contrato legal`, `contrato civil`, `contrato gratuito`,
`contrato familiar`, `cláusula firmada`, `cláusula revisada`, `cláusula dudosa`,
`cláusula obligatoria`, `saldo programado`, `saldo inmediato`, `saldo adicional`, `saldo dañado`,
`saldo conjunto`, `saldo inactivo`, `saldo incorrecto`, `saldo anual`, `saldo inesperado`,
`saldo devuelto`, `saldo duplicado`, `saldo parcial`, `saldo negociable`, `saldo confirmado`,
`cita persistente`, `cita preocupante`, `cita repentina`, `cita abdominal`, `cita superficial`,
`cita clínica`, `cita positiva`, `cita doble`, `cita completa`, `cita rápida`, `cita negativa`,
`cita diaria`, `cita leve`, `consulta persistente`, `avería urgente`, `avería casera`,
`avería original`, `avería compatible`, `avería básica`, `avería suelta`, `avería bloqueada`,
`avería dañada`, `avería húmeda`, `avería mojada`, `avería limpia`, `avería ocupada`,
`avería pesada`, `avería cerrada`, `vuelo directo`, `vuelo internacional`, `vuelo rápido`,
`vuelo local`, `vuelo sencillo`, `vuelo combinado`, `vuelo confirmado`, `vuelo ligero`,
`vuelo oficial`, `vuelo céntrico`, `vuelo tranquilo`, `vuelo pesado`, `vuelo corto`,
`tren directo`, `reunión presencial`, `reunión virtual`, `reunión nocturna`, `reunión flexible`,
`reunión mensual`, `reunión nueva`, `reunión aceptada`, `reunión cancelada`, `reunión retrasada`,
`reunión satisfecha`, `reunión confiable`, `reunión trimestral`, `reunión medible`,
`archivo cifrado`, `archivo duplicado`, `archivo permanente`, `archivo incorrecto`,
`archivo expirado`, `archivo válido`, `archivo activo`, `archivo seguro`, `archivo principal`,
`archivo remoto`, `archivo automático`, `archivo vencido`, `archivo público`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived exercises:
  - production and recognition exercises for all 120 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 3471 to 3591.
- `reviewedSentences` increases from 7002 to 7242.
- `reviewedAcceptedAnswers` increases from 7005 to 7245.
- `exerciseCount` increases from 6942 to 7182.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-038 Accelerated B1/B2 Service Status, Documents, Money, Health, Work, and Digital Pack

**Status:** implemented locally after A2-037.

**Goal:** add learner-ready B1/B2 breadth for practical service status, confirmations, forms,
billing, access, appointments, and everyday administration. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:** `cambio de domicilio`, `cambio de titular`, `cambio de fecha`, `cambio de ruta`,
`cambio de tarifa`, `cambio de contraseña`, `cambio de compañía`, `solicitud de cita`,
`solicitud de ayuda`, `solicitud de información`, `solicitud de reembolso`, `solicitud de baja`,
`solicitud de alta`, `solicitud de copia`, `solicitud de revisión`, `confirmación de asistencia`,
`confirmación de reserva`, `confirmación de pago`, `confirmación de envío`,
`confirmación de entrega`, `confirmación de lectura`, `confirmación de identidad`,
`confirmación de datos`, `aviso de retraso`, `aviso de vencimiento`, `aviso de seguridad`,
`aviso de mantenimiento`, `aviso de llegada`, `aviso de salida`, `número de referencia`,
`número de pedido`, `número de cuenta`, `número de tarjeta`, `fecha de revisión`,
`fecha de caducidad`, `fecha de nacimiento`, `fecha de inicio`, `fecha de fin`, `fecha de cobro`,
`fecha de devolución`, `fecha de recogida`, `justificante de asistencia`,
`justificante de ingresos`, `comprobante de compra`, `comprobante de reserva`,
`comprobante de envío`, `comprobante de entrega`, `copia de contrato`, `copia de factura`,
`copia de recibo`, `copia de pasaporte`, `copia de permiso`, `copia de denuncia`,
`copia de informe`, `copia de receta`, `estado de cuenta`, `estado de pedido`, `estado de envío`,
`estado de reserva`, `estado de solicitud`, `estado de reparación`, `estado de pago`,
`estado de salud`, `cita de control`, `cita de revisión`, `cita de urgencias`,
`cita de vacunación`, `consulta de resultados`, `consulta de facturación`, `consulta de soporte`,
`informe de urgencias`, `informe de daños`, `informe de gastos`, `informe de actividad`,
`informe de progreso`, `orden de reparación`, `orden de trabajo`, `orden de compra`,
`servicio de urgencias`, `servicio de atención`, `servicio de entrega`, `servicio de asistencia`,
`servicio de mantenimiento`, `tarjeta de crédito`, `tarjeta de débito`, `tarjeta de transporte`,
`cuota de inscripción`, `cuota de mantenimiento`, `cargo por servicio`, `cargo por retraso`,
`límite de gasto`, `clave de seguridad`, `código de acceso`, `código de descuento`,
`enlace de descarga`, `archivo de respaldo`, `archivo de audio`, `carpeta de trabajo`,
`carpeta de fotos`, `mensaje de error`, `mensaje de confirmación`, `notificación de acceso`,
`notificación de seguridad`, `prueba de identidad`, `prueba de domicilio`, `prueba de ingresos`,
`resumen de cuenta`, `resumen de gastos`, `resumen de actividad`, `plan de viaje`,
`lista de documentos`, `punto de entrega`, `centro de atención`, `centro de trabajo`,
`área de clientes`, `área de descargas`, `área de pagos`, `línea de atención`, `línea de crédito`,
`línea de emergencia`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived exercises:
  - production and recognition exercises for all 120 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 3591 to 3711.
- `reviewedSentences` increases from 7242 to 7482.
- `reviewedAcceptedAnswers` increases from 7245 to 7485.
- `exerciseCount` increases from 7182 to 7422.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-039 Accelerated B1/B2 Systems, Services, Problems, Risk, Documents, Travel, Work, and Digital Pack

**Status:** implemented locally after A2-038.

**Goal:** add learner-ready B1/B2 breadth for guides, lists, service points, systems, problems,
delays, risk language, checks, permits, contracts, and digital file workflows. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:** `guía de usuario`, `manual de usuario`, `guía de viaje`, `guía de trámites`,
`guía de pagos`, `lista de compras`, `lista de contactos`, `lista de invitados`,
`lista de prioridades`, `plan de emergencia`, `plan de estudios`, `plan de mantenimiento`,
`plan de seguridad`, `zona de espera`, `zona de carga`, `zona de descanso`, `zona de trabajo`,
`zona de seguridad`, `punto de información`, `punto de acceso`, `punto de control`,
`punto de venta`, `punto de salida`, `centro de llamadas`, `centro de formación`,
`centro de vacunación`, `centro de emergencias`, `centro de servicios`, `línea de ayuda`,
`línea de soporte`, `línea de autobús`, `línea de metro`, `línea de financiación`,
`área de espera`, `área de descanso`, `área de trabajo`, `área de seguridad`,
`área de información`, `mesa de ayuda`, `mesa de entrada`, `mesa de registro`, `mesa de trabajo`,
`mesa de negociación`, `sala de reuniones`, `sala de consultas`, `sala de formación`,
`sala de espera infantil`, `servicio de traducción`, `servicio de recogida`,
`servicio de devolución`, `servicio de transporte`, `servicio de facturación`, `programa de ayuda`,
`programa de formación`, `programa de salud`, `programa de puntos`, `programa de descuentos`,
`sistema de reservas`, `sistema de pagos`, `sistema de acceso`, `sistema de turnos`,
`sistema de seguridad`, `problema de conexión`, `problema de acceso`, `problema de pago`,
`problema de entrega`, `problema de salud`, `error de sistema`, `error de facturación`,
`error de dirección`, `error de reserva`, `error de contraseña`, `falta de información`,
`falta de pago`, `falta de cobertura`, `falta de tiempo`, `falta de personal`,
`cambio en la factura`, `cambio en la reserva`, `cambio en el contrato`, `cambio en el horario`,
`cambio en el servicio`, `retraso en el pago`, `retraso en la entrega`, `retraso en el vuelo`,
`retraso en la respuesta`, `retraso en la reparación`, `riesgo de caída`, `riesgo de incendio`,
`riesgo de fraude`, `riesgo de pérdida`, `riesgo de infección`, `prueba de acceso`,
`prueba de nivel`, `prueba de sonido`, `prueba de conexión`, `prueba de funcionamiento`,
`control de calidad`, `control de identidad`, `control de acceso`, `control de gastos`,
`control de temperatura`, `caso de emergencia`, `caso de fraude`, `caso de pérdida`,
`caso de accidente`, `caso de reclamación`, `archivo de contrato`, `archivo de factura`,
`archivo de imagen`, `archivo de vídeo`, `archivo de texto`, `copia de trabajo`,
`copia de seguridad local`, `copia de seguridad remota`, `copia de archivo`, `permiso de entrada`,
`permiso de salida`, `permiso de aparcamiento`, `contrato de trabajo`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived exercises:
  - production and recognition exercises for all 120 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 3711 to 3831.
- `reviewedSentences` increases from 7482 to 7722.
- `reviewedAcceptedAnswers` increases from 7485 to 7725.
- `exerciseCount` increases from 7422 to 7662.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-040 Accelerated B1/B2 Records, Channels, Payment, Safety, Work, Travel, and Digital Pack

**Status:** implemented locally after A2-039.

**Goal:** add learner-ready B1/B2 breadth for records, file formats, service channels, payment
methods, discounts, safety signs, schedules, reports, screens, and app controls. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:** `registro de entrada`, `registro de usuario`, `registro de actividad`,
`registro de llamada`, `formato de archivo`, `formato de fecha`, `formato de pago`,
`formato de solicitud`, `formato de informe`, `canal de comunicación`, `canal de atención`,
`canal de soporte`, `canal de ventas`, `canal de emergencia`, `modo de pago`, `modo de acceso`,
`modo de espera`, `modo de ahorro`, `modo de seguridad`, `nivel de acceso`, `nivel de riesgo`,
`nivel de servicio`, `nivel de prioridad`, `nivel de cobertura`, `paquete de datos`,
`paquete de viaje`, `paquete de servicios`, `paquete de ayuda`, `paquete de formación`,
`reserva de hotel`, `reserva de plaza`, `reserva de coche`, `reserva de actividad`,
`boleta de pago`, `boleta de compra`, `boleta de inscripción`, `boleta de entrega`,
`boleta de devolución`, `recargo por cambio`, `recargo por servicio`, `recargo por equipaje`,
`recargo por envío`, `descuento por familia`, `descuento por estudiante`,
`descuento por temporada`, `descuento por volumen`, `descuento por reserva`, `señal de alarma`,
`señal de salida`, `señal de tráfico`, `señal de advertencia`, `señal de emergencia`,
`ruta de evacuación`, `ruta de regreso`, `ruta de acceso`, `ruta de trabajo`, `horario de cierre`,
`horario de verano`, `horario de invierno`, `turno de tarde`, `turno de guardia`,
`turno de atención`, `parte de baja`, `parte de alta`, `parte de reparación`, `parte de entrega`,
`aviso por correo`, `aviso por mensaje`, `aviso por teléfono`, `aviso por escrito`,
`aviso por aplicación`, `pago con tarjeta`, `pago con móvil`, `pago en efectivo`, `pago en línea`,
`pago a plazos`, `contacto de soporte`, `contacto de facturación`, `contacto de empresa`,
`contacto de referencia`, `método de pago`, `método de contacto`, `método de entrega`,
`método de verificación`, `método de acceso`, `perfil de usuario`, `perfil de cliente`,
`perfil de empresa`, `perfil de riesgo`, `perfil de salud`, `historial de pagos`,
`historial de viajes`, `historial de salud`, `historial de mensajes`, `reporte de error`,
`reporte de uso`, `reporte de ventas`, `reporte de daños`, `reporte de seguridad`,
`pantalla de inicio`, `pantalla de pago`, `pantalla de acceso`, `pantalla de ayuda`,
`botón de ayuda`, `botón de pago`, `botón de envío`, `botón de búsqueda`, `botón de salida`,
`opción de entrega`, `opción de recogida`, `opción de devolución`, `opción de financiación`,
`opción de cancelación`, `ventana de chat`, `ventana de ayuda`, `menú de opciones`,
`menú de usuario`, `campo de búsqueda`, `campo de texto`, `barra de progreso`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived exercises:
  - production and recognition exercises for all 120 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 3831 to 3951.
- `reviewedSentences` increases from 7722 to 7962.
- `reviewedAcceptedAnswers` increases from 7725 to 7965.
- `exerciseCount` increases from 7662 to 7902.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-041 Accelerated B1/B2 Forms, Certificates, Codes, Bills, Insurance, Legal, Health, and Digital Pack

**Status:** implemented locally after A2-040.

**Goal:** add learner-ready B1/B2 breadth for job/visa/service requests, forms, certificates,
case and tracking numbers, customer codes, notifications, confirmations, bills, insurance,
formal letters, medical service points, legal notices, and digital signatures/passwords. Rows use
the `AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemmas:** `solicitud de empleo`, `solicitud de visa`, `petición de cita`,
`petición de reembolso`, `solicitud de cambio`, `petición de información`,
`solicitud de acceso`, `petición de ayuda`, `solicitud de presupuesto`,
`solicitud de préstamo`, `formulario de contacto`, `formulario de inscripción`,
`formulario de queja`, `formulario de autorización`, `formulario de consentimiento`,
`formulario de evaluación`, `formulario de reserva`, `formulario de devolución`,
`formulario de garantía`, `formulario de registro`, `constancia médica`,
`certificado laboral`, `certificado escolar`, `credencial digital`,
`certificado de nacimiento`, `certificado de matrimonio`, `certificado de residencia`,
`certificado de vacunación`, `certificado de antecedentes`, `certificado de ingresos`,
`identificador de expediente`, `identificador de cliente`, `identificador de pedido`,
`identificador de envío`, `identificador de cuenta`, `identificador de referencia`,
`identificador de reserva`, `número de serie`, `identificador de póliza`,
`identificador de contrato`, `lector de QR`, `dirección postal`,
`código de barras`, `token de verificación`, `código de cliente`, `código de reserva`,
`código de seguimiento`, `código de pago`, `código de error`, `código de activación`,
`notificación de pago`, `notificación de entrega`, `notificación de devolución`,
`notificación de cita`, `notificación de cambio`, `notificación de retraso`,
`notificación de emergencia`, `notificación de actualización`, `notificación de vencimiento`,
`notificación de renovación`, `confirmación de cita`, `acuse de pago`,
`acuse de reserva`, `acuse de entrega`, `acuse de asistencia`,
`validación de identidad`, `confirmación de correo`, `confirmación de teléfono`,
`confirmación de inscripción`, `confirmación de cancelación`, `recibo de agua`,
`recibo eléctrico`, `recibo de gas`, `factura de teléfono`, `factura de internet`,
`factura de hotel`, `factura de restaurante`, `factura de transporte`, `factura de servicio`,
`factura de reparación`, `póliza de seguro`, `póliza de salud`, `póliza de viaje`,
`póliza de hogar`, `póliza de coche`, `reclamación por escrito`, `queja escrita`,
`denuncia por escrito`, `respuesta escrita`, `comunicado oficial`, `carta de invitación`,
`carta de recomendación`, `carta de autorización`, `carta de renuncia`, `carta de aviso`,
`consultorio médico`, `centro dental`, `clínica privada`, `clínica pública`, `área de urgencias`,
`unidad de cuidados`, `servicio de ambulancia`, `cobertura sanitaria`, `cobertura para viaje`,
`cobertura de hogar`, `orden judicial`, `aviso judicial`, `orientación legal`, `consulta legal`,
`acuerdo por escrito`, `tiempo de entrega`, `plazo de pago`, `fecha tope`, `hora límite`,
`texto legal`, `firma validada`, `firma en línea`, `contraseña de un solo uso`,
`clave de un solo uso`, `sesión iniciada`.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived exercises:
  - production and recognition exercises for all 120 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 3951 to 4071.
- `reviewedSentences` increases from 7962 to 8202.
- `reviewedAcceptedAnswers` increases from 7965 to 8205.
- `exerciseCount` increases from 7902 to 8142.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-042 Accelerated B1/B2 Communication, Management, Follow-up, Review, Scheduling, Authorization, and Verification Pack

**Status:** implemented locally after A2-041.

**Goal:** add learner-ready B1/B2 breadth for practical service/work flows: communications,
case management, follow-up, reviews, assessments, scheduling, cancellations, status updates,
authorizations, and identity/payment/document verification. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemma families:** `comunicación de ...`, `gestión de ...`, `seguimiento de ...`,
`revisión de ...`, `evaluación de ...`, `programación de ...`, `cancelación de ...`,
`actualización de ...`, `autorización para ...`, and `verificación de ...` across services,
money, work, travel, health, housing, legal, safety, bureaucracy, repairs, shopping, insurance,
and digital domains.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived exercises:
  - production and recognition exercises for all 120 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 4071 to 4191.
- `reviewedSentences` increases from 8202 to 8442.
- `reviewedAcceptedAnswers` increases from 8205 to 8445.
- `exerciseCount` increases from 8142 to 8382.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

## A2-043 Accelerated B1/B2 Instructions, Requirements, Conditions, Checks, Resolution, Preparation, Presentation, Protection, and Coordination Pack

**Status:** implemented locally after A2-042.

**Goal:** add learner-ready B1/B2 breadth for instructions, indications, requirements,
conditions, checks, resolution, preparation, presentation, protection, and coordination across
payment, safety, documents, appointments, travel, service, account, claims, treatment,
maintenance, contracts, and projects. Rows use the
`AI_DRAFT -> AUTO_CHECKED -> AUTO_REVIEWED -> REVIEWED` lane with two independent automatic
reviewers.

**Target lemma families:** `instrucción de ...`, `indicación de ...`, `requisito de ...`,
`condición de ...`, `comprobación de ...`, `resolución de ...`, `preparación de ...`,
`presentación de ...`, `protección de ...`, and `coordinación de ...` across money, safety,
bureaucracy, services, travel, health, repairs, legal, and work domains.

Implemented content delta:

- 120 reviewed Wiktionary lexeme rows.
- 240 `AI_DRAFT` sentence rows promoted to `REVIEWED` by two independent automatic reviewers.
- 240 `AI_DRAFT` accepted-answer rows promoted to `REVIEWED` by the same two-reviewer gate.
- 240 `sentence_lexeme` joins.
- 240 derived exercises:
  - production and recognition exercises for all 120 target lemmas.

Acceptance result:

- `learnerReadyLexemes` increases from 4191 to 4311.
- `reviewedSentences` increases from 8442 to 8682.
- `reviewedAcceptedAnswers` increases from 8445 to 8685.
- `exerciseCount` increases from 8382 to 8622.
- `missingA1A2GapCount` remains 0.
- No raw or partially reviewed `AI_DRAFT` rows are included in shipped content; all 480 generated
  content rows are promoted to `REVIEWED` and recorded in `content_manifest.json`'s
  `autoReviewLedger`.

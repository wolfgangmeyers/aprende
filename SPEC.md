# Aprende — Client-Only Spanish Learning App — Spec (v1.1, Draft)

**Status:** Draft, robot-review applied. Research complete and adversarially verified (Duolingo-mechanics + Android-native architecture; claims individually flagged where interpolated/inferred). v1.1 folds in review findings: single SRS engine (FSRS-6), generalized `srs_item` identity, offline capability tiers, NPC leaderboard fully cut.
**Date:** 2026-05-30 (v1 draft → v1.1 review pass same day)
**Target platform:** Native Android (Kotlin + Jetpack Compose + Room + DataStore). **No server, no network dependency for the core loop.**
**Companion artifacts (this repo):** research outputs under the workflow transcript dir; this spec is the single source of truth for what we build.

> **Naming:** "Aprende" is a working title for the app in this document. Swap freely; nothing depends on it.

## Reading order

1. **Goal & scope** — what we are building and the hard constraints.
2. **Why client-only changes the design** — what a no-server app can and cannot do vs Duolingo.
3. **Stack decision** — Kotlin/Compose/Room, with React Native/Expo recorded as the rejected alternative.
4. **Content model** — the bundled, read-only curriculum: vocabulary, sentences, grammar, courses.
5. **Language mechanics** — Spanish grammar the app models and how answers are checked.
6. **Spaced-repetition engine** — the SRS that decides what to review and when (the core IP).
7. **Lesson flow** — how a single session is assembled, sequenced, and graded.
8. **Review phases** — reinforcement distinct from learning new material.
9. **Gamification** — XP, streaks, hearts, gems, achievements (and what we cut).
10. **Progress & state model** — the Room schema for everything the learner accumulates.
11. **Offline persistence & data lifecycle** — storage, backup/export, content updates.
12. **Android app architecture** — layers, lifecycle, background work, notifications, TTS/STT.
13. **Build, tooling & distribution** — Gradle, SDK levels, asset delivery, testing.
14. **Acceptance criteria** — verifiable end-to-end on a device with airplane mode on.
15. **Risks & open questions.**
16. **Phased rollout.**

---

## 1. Goal & scope

Build a native Android app that teaches Spanish to an English speaker using the proven Duolingo-style loop — bite-sized lessons, a large frequency-ranked vocabulary, spaced-repetition review, and gamified daily engagement — **running entirely on-device with no backend of our own and no network requirement to learn.**

### Non-negotiable constraints

- **C1 — No server.** We operate no backend. No accounts, no auth, no API. All content ships in the app or via Google Play's own delivery mechanisms; all learner state lives on the device.
- **C2 — Fully offline core loop.** Every learning action — open app, take a lesson, get graded, review, earn XP, keep a streak — must work in airplane mode after install.
- **C3 — Single-device, single-user.** No cross-device sync (that would require a server). Backup/restore is user-driven file export/import plus Android Auto Backup.
- **C4 — Licensed content only.** Every bundled dataset must be redistributable under a license we comply with (attribution shipped in-app where required).
- **C5 — Source-checked, review-gated content (no invented learning material).** Every piece of *learning content* — sentences, translations, vocabulary glosses, exercise prompts, accepted-answer sets, and grammar explanations/tips — must trace to an **explicit source of truth** and pass a **human review gate** before it ships. Nothing fabricated is shipped: no LLM-generated or hand-invented sentence/translation/prompt/explanation enters `content.db` without a recorded source and a reviewer sign-off. A mistranslation or invented "fact" actively teaches the learner an error, so content is treated as a **vetted pipeline with provenance**, not free-form authoring (§4.6). (Applies to learning material only — UI chrome/microcopy is normal app text.)

### In scope (v1)

- One course: **Spanish for English speakers**, sequenced A1 → mid-B1.
- Frequency-ranked vocabulary of **~2,000 lemmas** (covers ~86% of everyday Spanish by interpolated estimate, §4.1), expandable later.
- Lesson, review, and practice sessions with the full non-speaking exercise taxonomy.
- On-device SRS scheduling via **FSRS-6** with shipped default weights, fully local (single engine for v1 — see §6).
- TTS pronunciation (Android `TextToSpeech`) and a "type what you hear" listening mode — **offline-after-one-time-voice-install** (Tier 1, §11.0), not part of the Tier-0 offline core.
- Speaking exercises via `SpeechRecognizer` as a **capability-gated progressive enhancement** that degrades gracefully (Tier 2, §11.0/§12.6).
- Client-only gamification: XP, daily goal, streak + streak freeze, hearts, gems, achievements.
- Words list with per-word strength; mistakes review; targeted listening/vocabulary practice.
- Backup: export/import progress to a JSON file via the Storage Access Framework.

### Out of scope (deferred or cut by C1)

- **Competitive leagues, leaderboards, friend quests, referrals** — these require shared multi-user state and a server. **Cut for v1** (a fidelity-reduced NPC-simulated "league feel" is parked as a Phase-3 possibility only, §16/O2 — not v1 scope).
- Multiple courses / other languages (architecture leaves room; content is the cost).
- Real-money purchases / subscriptions (no billing in v1; hearts/gems are earned, not bought).
- Cross-device sync and cloud accounts (forbidden by C1).
- Stories, video call, and roleplay/conversation modes (Duolingo gates these behind Super; cut for v1).
- Adaptive cross-user difficulty calibration (Duolingo "Birdbrain" trains on millions of users — impossible client-only; we approximate with static per-item difficulty priors, see §6).

---

## 2. Why client-only changes the design

Duolingo is a server-backed product; a faithful client-only clone is impossible in a few specific places, and pretending otherwise would be the wrong design. The honest mapping:

| Duolingo capability | Client-only verdict | What we do instead |
|---|---|---|
| Per-word SRS (HLR/Birdbrain) | **Partially feasible.** Full HLR/Birdbrain train a global model over millions of cross-user traces — impossible on one device. | Ship **FSRS-6** (default weights, runs fully local). Replace cross-user "lexeme difficulty" with a **static per-item difficulty prior derived from frequency rank**. |
| Path / units / crown levels | **Fully feasible.** Pure positional state machine. | Bundle ordered course JSON; persist position + per-node completion locally. |
| Exercise grading | **Fully feasible.** Deterministic. | String-normalize + edit-distance for free text; equality for tiles/choice. No NLP, no server. |
| Audio / TTS | **Feasible.** | Android on-device `TextToSpeech` (Spanish voice); optionally bundle MP3s for top sentences. |
| Speech recognition (speaking) | **Feasible with caveats.** On-device recognition is not universal. | `SpeechRecognizer` with `EXTRA_PREFER_OFFLINE`; treat as progressive enhancement with a "can't speak now" skip. |
| XP / streak / hearts / gems / achievements | **Fully feasible.** Deterministic functions of the user's own activity. | Local counters in Room/DataStore; decay/regen computed lazily from timestamps. |
| Leagues / leaderboards / friend quests | **Infeasible.** Inherently multi-user, server-arbitrated. | **Cut from v1.** A fidelity-reduced NPC-simulated leaderboard is parked as a Phase-3 possibility only (§16/O2). |
| Anti-cheat (clock tampering for streaks/hearts) | **Unsolvable client-only.** | Accept it. Single-user practice app; no shared scoring to protect. Detect gross clock rollback defensively (§6.7) but don't over-invest. |

**Design rule that falls out of C2:** because there is no server cron, **all time-based state (SRS due-dates, heart regen, streak status, strength decay) is computed lazily from stored timestamps at read time** (against an injected `Clock`, §12.3), never via a background job that must run on schedule. Background work (WorkManager) is used only for *reminders and throwaway display counts* — never as the source of truth for state, and never written back into `srs_item` or read by the session generator (§12.4).

---

## 3. Stack decision

**Chosen: Kotlin + Jetpack Compose (Material 3) + Room + Jetpack DataStore**, with Kotlin coroutines/Flow for async, Hilt for DI, Navigation Compose for screens, WorkManager for reminder scheduling, and the platform `TextToSpeech` / `SpeechRecognizer` APIs.

Rationale:
- "Native UI" + "build/tooling appropriate for Android" was the explicit directive.
- Room gives a relational store that can be **pre-populated from a bundled database asset** — exactly what a large read-only curriculum + per-item SRS rows needs.
- Compose's animation APIs make the brand's "whimsy, magic, and delight" cheap to express (strength meters that glow and decay, celebratory lesson-complete animations).
- One language (Kotlin) across UI, domain, and data; coroutines/Flow model offline-first state cleanly.

**Rejected alternative — React Native / Expo.** The existing `/app` in the parent project is RN/Expo, so it was the obvious reuse candidate (persona principle: leverage what exists). Rejected because: (a) the directive specified native UI and Android-appropriate tooling; (b) this is a greenfield concept app, not an extension of the existing storefront app, so there is no shared code to leverage; (c) Room's pre-populated-DB-from-asset and the platform speech APIs are first-class on native and require bridging/config on RN. Recorded here so the decision isn't relitigated.

---

## 4. Content model (bundled, read-only curriculum)

The curriculum is **authored data, shipped with the app, never written at runtime.** It is the spine everything else hangs off. Conceptually four datasets, stored in a **pre-populated Room database** (see §10/§11):

### 4.1 Lexemes (the vocabulary spine)

The unit of knowledge is the **lemma** (dictionary headword: `tener`), not the surface form (`tiene`). Each lexeme row:

| Field | Notes |
|---|---|
| `lexemeId` | stable id |
| `lemma` | e.g. `tener` |
| `pos` | part of speech (noun, verb, adj, …) |
| `gender` | for nouns: M/F (stored, **not derived** — `el día`, `la mano` are exceptions) |
| `englishGloss` | primary meaning(s) |
| `frequencyRank` | 1..N; drives ordering and the difficulty prior |
| `cefrBand` | A1/A2/B1 — **approximate**, derived from frequency band + manual curation of the first few hundred (no authoritative open word→CEFR dataset exists for Spanish; see §5.6) |
| `difficultyPrior` | derived from `frequencyRank`; seeds the SRS in place of cross-user difficulty |

**A conjugation→lemma map** ships alongside so that recognizing `tiene`, `tienes`, `tuvo` all credit the lemma `tener`. Generated offline from Wiktionary/verb-conjugation data; shipped as a static table.

**Coverage target:** front-load the ~1,000–2,000 highest-frequency lemmas. Verified coverage: top ~1,000 lemmas ≈ 76–81% of written / ~88% of spoken Spanish; ~2,000 ≈ ~86–87% (interpolated estimate); sharp diminishing returns after. v1 ships ~2,000.

### 4.2 Sentences (the exercise bank)

Short example sentences (Spanish ⇄ English) tagged by the lexemes they contain, used to generate exercises. Each sentence carries a **set of accepted answer variants** (multiple valid translations / word orders) curated at authoring time, because one prompt legitimately has many correct answers and there is no server to adjudicate.

### 4.3 Grammar tables (generated forms)

Rather than store every conjugation, ship regular ending tables (3 verb classes × 6 tenses) + an override map for the ~10–20 irregular/stem-changing verbs, and generate forms at runtime. See §5.

**Code vs. vetted content (C5):** the *regular* ending tables are a deterministic algorithm — language structure, not invented per-word data — so they live in code (the `Conjugator`, verified against authoritative grammar references). The *irregular per-verb forms* are **vetted content** (sourced e.g. from Wiktionary, reviewed, shipped in `content.db`), NOT hardcoded — a wrong conjugation actively mis-teaches, so it must pass the §4.6 gate. The `Conjugator` consults an irregular-form source (content) and falls back to the regular rule when there is no override.

### 4.4 Course structure (the Path)

Ordered hierarchy, all positional:

```
Course → Section[] → Unit[] → Node[] → Lesson[] → Exercise[]
```

- A **Node** is one circle on the Path; completing its lessons advances the learner. Node has integer "level" state (crown-equivalent, 0..N) and an optional `legendary` flag (a no-hints variant).
- A **Unit** bundles ~8 nodes (course-dependent) and ends with a longer hint-disabled **unit challenge**.
- A **Section** groups units; finishing the required units in a section unlocks the next.
- **Gating is purely positional:** unlock node N+1 when N is complete; unlock section S+1 when its units are done. No backend validation.

### 4.5 Content licensing (satisfies C4)

Verified redistributable sources to assemble the bundle:

| Dataset | Use | License | Obligation |
|---|---|---|---|
| **Tatoeba** spa-eng sentence pairs (~144k via manythings.org; ~443k spa sentences in full dump) | sentence/exercise bank | CC-BY 2.0 FR | ship per-sentence attribution/credits in-app |
| **Tatoeba CC0 subset** | generated content where attribution friction matters | CC0 1.0 | none |
| **hermitdave/FrequencyWords** (OpenSubtitles) | frequency-ranked word list | code MIT, data **CC BY-SA** | ShareAlike — keep segregated from our own content to avoid copyleft reaching it; ship attribution |
| **Wiktionary** glosses/conjugation | dictionary + conjugation→lemma map | CC BY-SA | attribution |
| **Wikidata** | glosses where available | CC0 | none |

**Do NOT redistribute:** Davies "A Frequency Dictionary of Spanish" (copyrighted book) or RAE CREA text. Use them as references for *ordering decisions* only; ship CC-licensed substitutes for actual data. **Open question O1:** confirm the exact frequency list we ship and its license obligations before content authoring starts.

### 4.6 Content provenance & vetting (satisfies C5)

Content is a **vetted pipeline**, not free-form authoring. The governing principle (and the persona's "separate generation from validation; validate before trusting"): we may *derive* freely from vetted sources, but we *filter rigorously* and **ship only reviewed content**.

**Provenance on every content row.** Each `sentence`, `accepted_answer`, `lexeme` gloss, and `grammar_rule`/explanation in `content.db` carries:

| Field | Meaning |
|---|---|
| `source` | dataset name (e.g. `tatoeba`, `wiktionary`, `authored`) |
| `sourceId` | stable id within the source (e.g. Tatoeba sentence id + owner) — lets us re-derive and attribute |
| `license` | the source's license (drives the §4.5 attribution screen) |
| `vettingStatus` | `UNVETTED` → `AUTO_CHECKED` → `REVIEWED` (only `REVIEWED` may ship) |
| `reviewedBy`, `reviewedAt` | human sign-off record |

**The pipeline (a build-time content workflow, not runtime):**
1. **Ingest** only from vetted sources (§4.5). A row's `source`/`sourceId`/`license` is set here; fabrication is impossible because every row originates from a source record.
2. **Derive** — filter to short sentences, select target lemmas, build accepted-answer sets, generate conjugations from the rule tables (§5.2, deterministic, not invented), assemble the Path. Derivation may *transform* source data but may not *invent* facts.
3. **Auto-check (`AUTO_CHECKED`)** — automated validation: every sentence has ≥1 accepted answer; translations are bidirectionally consistent with the source pair; accepted-answer sets pass the §5.5 normalizer; conjugations match the generator; no orphan/duplicate rows; license present.
4. **Human review gate (`REVIEWED`)** — a reviewer signs off content before it ships, with extra scrutiny on anything `authored` (grammar tips, hand-added accepted variants) and on semantic judgement calls (ser/estar, idioms). **LLM assistance is allowed for *drafting/derivation* but its output is `UNVETTED` until a human reviews it** — it never ships blind.
5. **Publish** — the `content.db` build **fails hard** if any row to be shipped is not `REVIEWED` or lacks a `source` (a CI gate, not a warning). This is the mechanical enforcement of C5.

**App-design consequences:** the app never *generates* learning content at runtime (sentences are bundled; grading is deterministic; conjugations come from rule tables) — so the entire fabrication risk lives in the build pipeline, where the gate sits. The in-app credits/attribution screen (§4.5/AC14) is rendered from the same provenance fields. See PLAN.md for the workflow's pipeline stages.

---

## 5. Language mechanics (what the app models + how answers are checked)

### 5.1 Gender & agreement

- Noun gender is a **stored attribute** (M/F), not inferred. Default heuristic (-o→M, -a→F) with explicit exceptions: `el día/idioma/clima/problema/mapa`, `la mano/foto`; stressed-initial-`a` feminines take `el` for phonetics (`el agua`) but stay grammatically feminine (`el agua fría`).
- Articles (`el/la/los/las`, `un/una/unos/unas`) and adjectives **agree in gender and number**, computed from the noun's stored gender + number. Adjective forms: `-o` adjectives have 4 forms; `-e`/consonant adjectives vary by number only.

### 5.2 Verb conjugation (regular tables + irregular overrides)

Six tenses for A1–B1, generated from infinitive + ending tables (verified correct):

- **Present** — `-ar`: o/as/a/amos/áis/an · `-er`: o/es/e/emos/éis/en · `-ir`: o/es/e/imos/ís/en (`-er`/`-ir` differ only in nosotros/vosotros).
- **Preterite** — `-ar`: é/aste/ó/amos/asteis/aron · `-er`/`-ir`: í/iste/ió/imos/isteis/ieron.
- **Imperfect** — `-ar`: aba/abas/aba/ábamos/abais/aban · `-er`/`-ir`: ía/ías/ía/íamos/íais/ían (only `ser`, `ir`, `ver` irregular).
- **Future** — infinitive + é/ás/á/emos/éis/án (closed set of ~12 irregular *stems*, e.g. `tendr-`, `har-`, `dir-`, take the same endings).
- **Present subjunctive** — "opposite vowel": `-ar`→e-endings, `-er`/`-ir`→a-endings, stem from the yo present form.
- **Imperative** — affirmative tú = 3rd-person-sing present; negative tú = subjunctive; 8 irregular affirmative tú commands (di, haz, ve, pon, sal, sé, ten, ven).

**Irregular verb tables shipped explicitly:** ser, estar, tener, ir, hacer, poder, querer, decir, saber, venir, haber (+ `-go` yo-forms tengo/vengo/pongo/salgo/traigo/caigo/hago/digo, and e→ie / o→ue / e→i stem-changers).

### 5.3 ser vs estar, pronouns

- **ser** = identity/essence (DOCTOR), **estar** = state/location/condition (PLACE); "permanent vs temporary" is a teaching heuristic with exceptions (`estar muerto`). These are *semantic* choices — exercises need hand-authored accepted-answer sets, not generated ones.
- **Pronouns:** subject; direct (me/te/lo/la/nos/os/los/las); indirect (me/te/le/nos/os/les); reflexive (me/te/se/nos/os/se). Order = **RID** (Reflexive, Indirect, Direct); precede conjugated verbs, attach to infinitives/gerunds/affirmative commands (`dámelo`); `le/les`→`se` before lo/la/los/las.

### 5.4 Typing Spanish characters

Ship an **on-screen accent bar** (ñ á é í ó ú ü ¿ ¡) on every typed-answer screen so a Spanish OS keyboard is never required.

### 5.5 Answer checking (deterministic, on-device)

The single most-reused piece of logic. For **free-text** answers (typed translation, listen-and-type, fill-in-the-blank):

1. Unicode-normalize (NFC), lowercase, trim, strip terminal punctuation, collapse whitespace.
2. Compare against each member of the exercise's **accepted-answer set**.
3. Compute an **accent-insensitive** comparison so a missing accent is accepted — optionally surfaced as a soft "you have a typo" hint, never a failure.
4. Apply a **Damerau-Levenshtein** edit-distance threshold (scaled to answer length, ~1–2) to forgive single-char typos and adjacent transpositions; missing a whole word is penalized as wrong, not a typo.

> **Verification note:** that Duolingo specifically uses Levenshtein internally is an *inference*, not confirmed. We adopt Damerau-Levenshtein because it's the standard, correct approach (covers ~80% of human typos) — not as a claim about Duolingo's internals.

For **tiles/matching/multiple-choice**: exact equality on token order / selected index. No fuzzy matching. Trivially local.

### 5.6 CEFR sequencing

Bake the ordering into course structure: **A1** = present + ser/estar + gender/articles/subject pronouns + basic negation; **A2** = preterite, imperfect, preterite-vs-imperfect, object pronouns, near future (`ir a` + inf), simple future, informal commands, present perfect, por/para; **B1** = present subjunctive, conditional, compound/pluperfect tenses, relative clauses. CEFR labels on lexemes are **derived/approximate** (frequency bands + manual curation of the first few hundred) — there is no authoritative open word→CEFR dataset for Spanish; the Instituto Cervantes *Plan Curricular* is the reference but is a curricular spec, not a machine-readable list.

---

## 6. Spaced-repetition engine (the core IP)

This is what makes it a learning app rather than a quiz. It decides **what** to surface and **when**.

### 6.1 Engine choice: one engine — FSRS-6

**Decision D1 (locked): v1 ships exactly one SRS engine, FSRS-6.** No `SrsScheduler` plug-in interface, no second shipped implementation — `ScheduleReviewUseCase` (§12.1) is the seam that isolates SRS logic from the rest of the app, and that is sufficient. Rationale: SRS quality is the core IP of a learning app (semantic correctness), FSRS-6 runs fully on-device with shipped default weights, and the Phase-0 spike de-risks the formulas. A runtime-swappable interface with one shipping implementation would be premature generalization; if FSRS is ever replaced it's a change to one use-case, not a pre-built abstraction.

- **FSRS-6**: best-quality scheduling, **ships with default weights** (a 21-value constant vector), runs **fully on-device**. Per-item state: `{difficulty D, stability S, lastReview, dueAt}`. Per-user weight optimization is explicitly **out of v1 scope** (default weights only).
- **Contingency (not a shipped feature):** if the Phase-0 FSRS spike fails its reference-vector tests within its timebox (O4), fall back to a **Leitner box ladder** (intervals 1/2/4/8/16 days, promote on correct, demote on wrong — pre-ML Duolingo parity). This is a contingency the spike resolves, not a parallel engine carried in the codebase.

### 6.2 FSRS-6 mechanics (verified)

- Retrievability: `R(t,S) = (1 + factor·t/S)^(−w20)`, `factor = 0.9^(−1/w20) − 1` (so `R(S,S)=0.9`).
- Next interval for desired retention `r`: `I(r,S) = (S/factor)·(r^(1/(−w20)) − 1)`. Default `r = 0.9`, exposed as a product knob (lower r → fewer reviews).
- Initial stability `S0(G)=w_{G−1}`; initial difficulty `D0(G)=w4 − e^(w5·(G−1)) + 1` clamped [1,10].
- Difficulty update with linear damping + mean reversion toward `D0(4)` via `w7`.
- Stability grows on recall (bigger gains when S small, D low, R low) and is reset lower on lapse.
- **Default weights are shipped constants** (FSRS-6 21-value vector). Grades map from exercise outcome (see §6.4).

### 6.3 The static difficulty prior (replaces Birdbrain)

Duolingo's cross-user difficulty calibration is impossible on one device. We substitute a **per-item `difficultyPrior` derived from frequency rank** (rarer word → harder → higher initial FSRS difficulty / shorter initial interval). This is the principled client-only stand-in. Per-user difficulty *learning* (e.g. a local online logistic update) is **out of scope for v1** — the static prior is the entire v1 surface.

### 6.4 Grade derivation from exercise outcome

The learner never self-rates (unlike Anki). Derive the FSRS grade from the graded exercise, applied to the exercise's **target item** (§6.4a):

- First-try correct, no hint, no typo → **Good** (G=3).
- Correct but used a hint or had a forgiven typo → **Hard** (G=2).
- Wrong → **Again** (G=1) → a lapse.
- No "Easy" (G=4) path from normal exercises; reserved for an explicit "I knew that" affordance if added later.

### 6.4a Which item an exercise grades (fan-out rule)

A sentence touches many lexemes, but an exercise **teaches/tests one target item** (the lemma or grammar rule the node is introducing — recorded on the exercise in content). The FSRS grade updates **only that target `srs_item`**. Incidental lexemes appearing in the sentence are *not* all lapsed/credited — that would thrash unrelated items' schedules. (This keeps one graded answer → one `srs_item` write, and is why `srs_item` is keyed by a generic `itemId`/`itemType`, §10.2.)

### 6.5 Lazy decay (consequence of C2)

There is no server cron. Strength/retrievability and due-status are **computed from stored timestamps whenever the UI or session generator needs them** — never written by a scheduled job. `dueAt` (epoch-millis) is stored; "is due now" = `clock.now() ≥ dueAt`. Strength shown in the Words list = current `R(t,S)` evaluated at open.

### 6.6 Strength UI

Map `R ∈ [0,1]` to a Duolingo-style decaying meter — rendered as the brand's "magical" glowing crystals/bars that visibly fade over time and refill on practice. Bucket a skill's average R into 4 bars; gold above ~2.5 bars.

### 6.7 Clock-tamper defense (bounded)

Single-user app, no shared scoring, so anti-cheat is low-value — but a user moving the clock forward then back can corrupt SRS. Defensive minimum: persist a monotonically-increasing `lastSeenWallClock`; if `now < lastSeenWallClock` by more than a small skew, freeze decay/streak advancement for that session rather than corrupting state. Do not over-invest (persona: don't add defensive complexity beyond the real risk).

---

## 7. Lesson flow (single-session assembly, sequencing, grading)

A lesson session is **generated client-side** from the node's exercise pool. Algorithm:

1. **Select items.** For a *new* node: a few new lexemes (introduced with hints/word-bank + gloss on first appearance) interleaved with review of earlier lexemes tagged to this node. For a *review* session: pull due/weak items only (see §8).
2. **Target length ~15–17 exercises** (research: ~17 for an all-correct lesson; ~10 for practice). Length is **dynamic** — see step 5.
3. **Mix exercise types** matched to goal (verified taxonomy):
   - Early/new vocab: **word-bank/tile translation**, **tap-the-pairs matching** (low spelling burden).
   - Production/spelling: **typed translation**, **listen-and-type**.
   - Grammar discrimination: **multiple choice**, **select-the-missing-word**, **fill-in-the-blank**, **arrange-the-words**.
   - Audio: **tap-what-you-hear** (TTS-driven).
   - Speaking (if available): **speak-the-phrase** via `SpeechRecognizer`, always with a "can't speak now" skip.
4. **Grade** per §5.5 (deterministic). Wrong answer → lose a heart (§9), show correct answer.
5. **Re-queue mistakes within the session:** any incorrectly answered exercise is pushed back into the session queue and must be answered correctly before the session ends (this is what makes length dynamic). Also append `(exerciseId, target itemId)` to the persistent **mistakes queue** (§8) and feed the outcome to the SRS as a lapse on the exercise's **target item only** (§6.4/§6.4a).
6. **Complete:** award XP (§9), update streak/daily-goal, update the FSRS state of each exercise's target item, mark node progress.

**Hearts gate:** running out of hearts mid-lesson ends/blocks the session per §9. Unit challenges and legendary/jump tests run the same engine with **hints disabled** and a limited heart budget.

---

## 8. Review phases (reinforcement ≠ learning new)

Distinct intent from §7: surface already-seen material that is decaying, plus mistakes.

- **Due-review session.** Sort all seen items by current recall `R` ascending; take those below threshold (`R < 0.9`, capped at ~10–20). Pure local computation over stored SRS rows.
- **Mistakes review.** Drain up to ~10 from the persistent mistakes queue (item id + the specific exercise that was missed); also sprinkle some into normal and listening sessions. Clearing a mistake correctly removes it from the queue and credits the SRS.
- **Listening practice.** ~10 TTS-driven listen-and-type/tap-what-you-hear exercises; re-injects earlier mistakes.
- **Vocabulary practice.** Untimed matching over encountered lemmas (Match-Madness-style), sortable weakest-first.
- **Words screen.** Lists learned lemmas with a strength indicator (current `R`), sortable weakest-first to drive practice — mirrors Duolingo's old "Words" list, all derived from on-device state.

**Session generator rule:** bias toward due + mistakes first; only pull new/unseen items when the due queue is short or when advancing the Path. "Strengthening" resets touched items' displayed strength to full, but **correct answers extend the interval (later next review) and wrong answers/hints shorten it** (per §6).

---

## 9. Gamification (client-only)

All deterministic functions of the user's own activity → fully local. Verified values used as defaults (tunable):

- **XP** — standard lesson 10 XP; final lesson in a node/unit 20 XP; full no-mistake combo up to +5. Stored as a running total + per-day total.
- **Daily goal** — selectable tiers Basic 1 / Casual 10 / Regular 20 / Serious 30 / Intense 50 XP (default Regular). Met when day's XP ≥ goal.
- **Streak** — +1 per day the goal is met; resets on a missed day unless protected. Computed from the injected `Clock` + last-completed local-date (epoch-day), with §6.7 tamper guard and a grace window so a timezone hop doesn't falsely break it (§12.3). **Forgiving by design** because reminders are best-effort (§12.5).
- **Streak freeze** — purchasable with gems (default cost 200), auto-consumed on a missed day; cap 2 equipped. (Monthly free streak *repair* is deferred to Phase 3 — one protection mechanism is enough for v1.)
- **Hearts** — start 5, lose 1 per mistake, regen 1 every ~5h (timestamp-diff vs `Clock`, computed lazily), refill via a completed practice session, or spend gems (default 350). No "unlimited hearts" toggle in v1 — with no billing it's a meaningless free switch that would void the failure-pressure loop; hearts are the loop.
- **Gems** — local integer balance; earned from streak milestones, achievements, daily-goal completion; spent on freezes/heart-refills. Local shop catalog.
- **Achievements** — 10-level tiers evaluated against local counters on each session: streak days, words learned, total XP, lessons completed, legendary levels.

**Cut from v1 (require a server):** leagues, leaderboards, friend quests, referrals. A fidelity-reduced NPC-simulated leaderboard (synthetic opponents + a streak-vs-self "ghost") is **not v1 scope** — parked as a Phase-3 possibility pending **open question O2** (§16).

---

## 10. Progress & state model (Room schema)

**Decision D2 (locked): two *separate* Room databases, not one.** This is forced by a verified Room behavior: `createFromAsset` only repopulates during a `fallbackToDestructiveMigration()` rebuild, and Room **ignores** the bundled asset when an explicit migration path exists. If content and progress shared one DB, shipping updated content via destructive migration would **wipe the learner's SRS state**. So:

- **`content.db`** — read-only, replaceable. Pre-populated from the bundled asset; on a content update we bump its `@Database` version, ship a new asset, and let `createFromAsset` + destructive rebuild replace it. Never holds learner state.
- **`progress.db`** — read-write, never overwritten. Carries **explicit `Migration` classes** so learner data survives every app update.

Cross-DB references are by id only (no FK across databases); the repository layer joins them in code. Both DBs export their schema (`room.schemaLocation`) so the bundled `content.db` asset is built to match — Room **fails** prepopulation on a schema mismatch.

### 10.1 Content DB (`content.db`, read-only, pre-populated from bundled asset)

`lexeme`, `sentence`, `sentence_lexeme` (join), `accepted_answer`, `grammar_rule` / `irregular_form`, `conjugation_lemma_map`, `course`, `section`, `unit`, `node`, `lesson`, `exercise`, plus a `sentence_fts` (`@Fts4`, `contentEntity = sentence`) virtual table for word/sentence search via SQL `MATCH`. Shipped via `Room.databaseBuilder(...).createFromAsset("database/content.db")`. Never written at runtime.

**Provenance columns (C5/§4.6):** the content-bearing entities (`sentence`, `accepted_answer`, `lexeme`, `grammar_rule`) carry `source`, `sourceId`, `license`, `vettingStatus`, `reviewedBy`, `reviewedAt`. The content build refuses to emit any row that is not `REVIEWED` or lacks a `source`. These also feed the in-app attribution screen.

### 10.2 Progress DB (`progress.db`, read-write, the learner's accumulated state)

| Table | Key fields |
|---|---|
| `srs_item` | **composite PK `(itemId, itemType)`** where `itemType ∈ {LEXEME, GRAMMAR_RULE}` (`itemId` references content by id); FSRS state `D, S, lastReview, dueAt` (epoch-millis); `state` enum (NEW/LEARNING/REVIEW/RELEARNING); `timesSeen/Correct/Wrong`; **`dueAt` indexed** for the "due today" query |
| `node_progress` | `nodeId`, `level` (crown-equiv), `legendary`, `completedAt` |
| `mistake_queue` | `exerciseId`, `itemId`, `itemType`, `missedAt` |
| `daily_activity` | `localDate`, `xpEarned`, `goalMet` (drives streak + goal) |
| `user_stats` | totals: XP, gems, hearts + `heartsLostAt`, streak length, streak freezes, words-learned count |
| `achievement` | `achievementId`, `level`, `unlockedAt` |

`srs_item` uses a **generic item identity** (not a hardcoded `lexemeId`) so the engine can also schedule grammar rules (e.g. ser-vs-estar) and so §6.6's skill-average works — and because `progress.db` is the never-overwritten DB (D2), making this identity general *now* avoids an expensive live-data migration later. FSRS-only state (D1 ships one engine), so no nullable second-engine columns.

**Settings & lightweight scalars live in Jetpack DataStore, not Room** — TTS voice/locale, speaking-enabled flag, daily-goal setting, accent-bar prefs. Rule of thumb: if you query/sort/join it (SRS rows, mistakes, daily activity), Room; if it's a handful of app-level scalars/flags, DataStore.

> **Implementation deviation (ratified):** the v1 implementation uses **Preferences DataStore**, not Proto DataStore as originally specified here. Rationale: the settings surface is flat scalars, and Proto would require adding the protobuf Gradle plugin + `.proto` codegen (build complexity not justified at this phase), whereas `datastore-preferences` is already a dependency. Revisit Proto only if settings become structured enough to justify the switch.

---

## 11. Offline persistence & data lifecycle

### 11.0 Offline capability tiers (what C2 actually guarantees)

Not everything is offline at the *same* level. The C2 guarantee is the text loop; audio features are enhancements. This tiering is a hard invariant:

| Tier | Feature | Offline guarantee |
|---|---|---|
| **0 — Core (C2)** | Open app, take a lesson (typed/tile/matching/choice/fill-in), deterministic grading, SRS scheduling, XP, streak, hearts, gems, Words list, mistakes + due review | **Always offline**, from a fresh airplane-mode install. Uses **zero** TTS/STT. |
| **1 — Offline after one-time install** | TTS listening exercises (listen-and-type, tap-what-you-hear) + pronunciation playback | Offline **once a Spanish TTS voice is installed**; the one-time `ACTION_INSTALL_TTS_DATA` install needs network (§12.6). Treated as a progressive enhancement, **not** part of the Tier-0 core. |
| **2 — Capability-gated** | Speaking exercises (`SpeechRecognizer`) | Only where on-device recognition is available (Android 13+ + downloaded model); otherwise disabled, never cloud-fallback (§12.6). |

**Path invariant:** the entire v1 course Path ships in the **AAB base module** — no Path node may depend on an on-demand/fast-follow asset pack, so a positional unlock can never strand an offline learner at a node whose content isn't installed. Asset Delivery is for *optional/expansion* content only.

- **Content** ships as a **pre-populated `content.db` Room asset** (`createFromAsset`) under `assets/database/` — fast, queryable (incl. FTS), no parse-on-launch cost. A text-only corpus (frequency list + thousands of Tatoeba pairs) is single-digit-to-low-tens of MB DEFLATE-compressed — comfortably inside the AAB base module (Play's ~200 MB base download cap; verified). Large audio is the only thing that could approach the cap → **Play Asset Delivery** (see §13).
- **Progress** is local `progress.db` (Room) + DataStore. Survives app restarts and process death by construction.
- **Backup / restore (satisfies C3) — ship BOTH:**
  - **User-driven export/import (primary).** Serialize `progress.db` to a versioned JSON document and write it to a user-chosen file via the Storage Access Framework: `ActivityResultContracts.CreateDocument("application/json")` to export, `OpenDocument()` to import; stream through `ContentResolver.openOutputStream/openInputStream`. **No storage permission required.** `takePersistableUriPermission` if we keep a reusable backup target. This is the only reliable "move to a new phone / different vendor" path.
  - **Android Auto Backup (safety net).** `android:allowBackup="true"` + a `dataExtractionRules` XML (Android 12+) that includes `progress.db`/DataStore and excludes caches. Verified limits: **~25 MB/app cap**, best-effort (~nightly, idle + Wi-Fi + charging), single most-recent snapshot, encrypted, doesn't count against the user's Drive quota. **Frame to users as automatic recovery on reinstall, NOT multi-device sync** — it may never run if conditions aren't met.
- **Content updates** without a server: ship new curriculum in **app updates** — new `content.db` asset version replaces the old via destructive rebuild; `progress.db` is untouched (D2). Optionally Play Asset Delivery on-demand/fast-follow packs for expansion content: these download from **Google Play's CDN, not a server of ours** (so they satisfy C1), but require connectivity *to fetch* — never to *learn* with already-installed content (consistent with C2: the *core loop* is offline; content acquisition is not).
- **Storage budget** — prefer on-device TTS over bundled MP3s to keep size down (§12.6); bundle MP3s (mark `noCompress` in Gradle so already-compressed audio isn't double-compressed) only for the highest-value sentences if TTS quality is insufficient.

---

## 12. Android app architecture

(All API names, SDK levels, size limits, and offline-recognition availability below are from the verified Android-native research pass.)

### 12.1 Layers (official "Guide to app architecture")

- **UI layer** — Compose (Material 3) screens + ViewModels exposing a single immutable `UiState` as `StateFlow` via `stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), initial)`; Compose collects with `collectAsStateWithLifecycle()` (lifecycle-aware — pauses collection when backgrounded so timers/audio behave). Unidirectional data flow.
- **Domain layer** — use-cases for the non-trivial logic, unit-testable without Compose/Room: `GenerateLessonUseCase`, `GradeAnswerUseCase`, `ScheduleReviewUseCase`, `UpdateStreakUseCase`. SRS/grading/streak rules live here, not in ViewModels.
- **Data layer** — repositories over Room DAOs (returning `Flow`, so the UI auto-updates on DB change) + DataStore; the only layer that knows about persistence; single source of truth (no remote source exists — that's the whole point). Domain use-cases depend on **repository interfaces** (Hilt injects fakes in tests), never on DAOs directly.
- **Cross-DB joins live only in the repository (D2 seam).** The hot grading path — surface form `tuvo` → lemma `tener` (lookup in `content.db.conjugation_lemma_map`) → upsert `progress.db.srs_item` — touches both databases. Only the repository bridges them (by id; no cross-DB FK); the domain layer stays persistence-agnostic. **Unknown-surface-form fallback:** if a typed form isn't in the conjugation map, fall back to exact-lemma match against the exercise's target item and log it for content review — never silently fail to credit.
- **DI** — Hilt (`@HiltViewModel` + `hiltViewModel()` in Compose; lets tests inject fakes). **Async** — Kotlin coroutines/Flow; Room and DataStore are coroutine-native (DB work on `Dispatchers.IO`).
- **Animation for "whimsy/magic/delight" (brand req):** Compose's default physics-based `spring` (`DampingRatioMediumBouncy`/`StiffnessLow`) for answer-correct pops and streak counters; `AnimatedContent` for question-card swaps; `AnimatedVisibility` for correct/incorrect banners; `rememberInfiniteTransition` for the glowing/pulsing strength crystals and streak flame.

### 12.2 Navigation

Navigation Compose: Path/home, lesson session, review hub, words list, profile/stats, settings.

### 12.3 Lifecycle, process death & time

- Durable state is in Room/DataStore, so process death is survivable by construction.
- Transient in-session state (current exercise index, mistake re-queue, in-progress answer) held in ViewModel + `SavedStateHandle` (Bundle-backed, survives *system-initiated* death; small/Parcelable only). Session state is **small by construction** (≤ ~20 exercise ids/indices) to stay well clear of the Bundle `TransactionTooLargeException` ceiling — don't persist rich per-exercise objects there; rehydrate from `content.db` by id. On restore, resume or cleanly restart the session.
- **Time is computed via an injected `java.time.Clock`** (`Clock.systemDefaultZone()` in prod, `Clock.fixed()` in tests) so all streak roll-over, SRS due-checks, and lazy decay are deterministic and unit-testable across midnight/DST/timezone boundaries. Streak "today" = `LocalDate.now(zone)`; persist the last-completed day as epoch-day.

### 12.4 Background work

- **WorkManager** for the nightly "recompute due-review counts for the launcher badge / notification" job. Verified constraints: **15-min minimum periodic interval**, and it **does not run during Doze** (deferred to maintenance windows) — fine because this job is timing-tolerant. It auto-reschedules across reboot (no `BOOT_COMPLETED` handler needed).
- **Never the source of truth** for SRS/streak (those are lazy from timestamps, §6.5/§12.3). The WorkManager-computed due-count is a **throwaway display input** for the notification/badge only — it is never written into `srs_item` and never read by the session generator, which always recomputes the due list lazily on open. (So a stale badge of "7 due" vs an in-app "9 due" is acceptable display lag, not a correctness bug.)

### 12.5 Notifications & the daily reminder

- `NotificationManager` + a notification channel (`IMPORTANCE_DEFAULT`). **`POST_NOTIFICATIONS` runtime permission (Android 13+)** requested **contextually** — when the learner first enables reminders or finishes onboarding, with a rationale — never blindly at first launch (a single "Don't allow" is sticky). Check `areNotificationsEnabled()` before posting.
- **Daily reminder timing (verified nuance):** the precise daily reminder uses `AlarmManager.setAlarmClock()` — the most Doze-resilient option and exempt from the ~9-min allow-while-idle throttle. We deliberately **avoid `SCHEDULE_EXACT_ALARM`** (denied by default on Android 14+) and **`USE_EXACT_ALARM`** (Play-restricted to alarm/clock/calendar apps — a study reminder would risk Play rejection). If even `setAlarmClock()` is undesirable, fall back to inexact `setAndAllowWhileIdle()`. Re-register the alarm on `BOOT_COMPLETED` and on timezone change (AlarmManager alarms don't survive reboot; WorkManager does).
- **Reliability expectation baked into UX:** Doze + App Standby buckets throttle exactly the *lapsed* user we most want to remind, so reminders are best-effort. The streak is therefore made **forgiving** (grace handling + streak freeze, §9) rather than depending on a guaranteed notification.

### 12.6 TTS & speech recognition

- **`TextToSpeech`** with Spanish `Locale` (es-ES / es-MX). On first run, check `isLanguageAvailable(...)`; if `LANG_MISSING_DATA`, deep-link the user via `ACTION_INSTALL_TTS_DATA` to install the voice pack. **Prefer embedded/offline voices** by filtering `getVoices()` to `isNetworkConnectionRequired() == false` so we never silently depend on the network. Drives all listening exercises + pronunciation playback (zero audio asset weight). Treat an offline Spanish voice as a *dependency to verify*, not a platform guarantee — provide a graceful message if none exists.
- **`SpeechRecognizer`** for speaking exercises, as a **progressive enhancement**: gate on `isOnDeviceRecognitionAvailable()` and use `createOnDeviceSpeechRecognizer()` (API 31+) with a downloaded offline model (true no-server recognition is documented for **Android 13+**); pass `EXTRA_PREFER_OFFLINE` / locale `es-ES`; read the transcript and fuzzy-match (§5.5) to the target. Offline accuracy is lower (especially short single-word answers and learner accents) → grade leniently, allow retries, never rely on a confidence score. Always provide a "can't speak now" skip; never block progression. `RECORD_AUDIO` requested only when the learner first opts into speaking; deny → hide speaking, keep everything else fully usable. **On devices below the offline-recognition bar, speaking is simply disabled** (we do not fall back to cloud recognition, which would violate C2).
- Short "magical" SFX (correct/wrong/level-up chimes) via **`SoundPool`** (low-latency, in-memory); bundled small assets. Longer clips, if any, via `MediaPlayer`.

---

## 13. Build, tooling & distribution

(SDK levels, size limits, and asset-pack constraints below are from the verified Android research pass.)

- **Build:** Gradle with **Kotlin DSL** (`build.gradle.kts`); single app module to start, split by feature later if it grows.
- **SDK:** **`targetSdk = 35`** (Android 15 — Play's requirement for new apps/updates through 2025–26; API 36 available and adoptable). **`minSdk = 24`** to cover the large majority of active devices with full Compose/Room/DataStore support. **Caveat:** offline speech recognition needs API 31+/Android 13+ — speaking exercises are *feature-gated at runtime* (§12.6), not by `minSdk`, so the base app still installs on 24.
- **Distribution:** Android App Bundle (AAB). Verified caps: base-module download **~200 MB**; install-time asset packs count toward listed size, fast-follow/on-demand packs (up to 1.5 GB each) download from Play's CDN post-install. The text corpus fits in the base APK; reach for **Play Asset Delivery** only if bundled audio pushes past the limit. **Not** Play Feature Delivery (that's for code modules, not data); **not** OBB (legacy, unsupported for AAB).
- **Signing & versioning:** Play App Signing; release `signingConfig` with secrets loaded from a gitignored `keystore.properties`; semantic `versionName` + monotonic `versionCode`; `content.db` carries its own `@Database` version (D2).
- **Testing (per CLAUDE.md zero-tolerance + persona "prove it works"):**
  - **JVM unit** — JUnit4 + `kotlinx-coroutines-test` `runTest` for: FSRS-6 math against known reference vectors, answer-checker (NFC normalization, accent-insensitivity, Damerau-Levenshtein thresholds, multi-accepted-answer sets), conjugation generator, session generator, streak/heart/XP logic (with `Clock.fixed()` to nail midnight/DST/timezone cases). MockK for collaborators.
  - **Room** — `Room.inMemoryDatabaseBuilder(...)` DAO tests and **`progress.db` migration tests** (real DB, not mocks — persona: test-double fidelity); a test that proves a `content.db` version bump preserves `progress.db` (D2).
  - **Flow** — **Turbine** for ViewModel `StateFlow` emissions.
  - **Compose UI** — `createComposeRule()` for screen behavior (runnable on the JVM via Robolectric); Espresso/UiAutomator for critical end-to-end flows.
  - **Offline test** — an instrumented test that runs a full lesson with the radio off to prove C2.
- **CI:** GitHub Actions — JVM unit + Room + Flow + Robolectric Compose tests on every change; instrumented tests via Gradle Managed Devices (or `android-emulator-runner`) / Firebase Test Lab.

---

## 14. Acceptance criteria (verifiable on-device, airplane mode ON)

- **AC1** — Fresh install, **airplane mode on**: open app, complete a full lesson using **only Tier-0 exercise types (no TTS, no STT)**, get graded, earn XP, see streak increment. (Proves the C1+C2 core loop is fully offline with zero audio dependency.)
- **AC2** — Typed answer missing an accent (`tu` for `tú`) is **accepted** (optionally flagged as a typo), not failed; a single-char typo within threshold is accepted; a wrong word is rejected.
- **AC3** — A prompt with multiple valid translations accepts **any** member of its accepted-answer set.
- **AC4** — Conjugation generator produces correct forms for a regular verb in all six tenses and correct overrides for ser/estar/tener (test vectors).
- **AC5** — SRS: an item answered correctly schedules a **later** `dueAt` than one answered wrong; FSRS formulas match known reference vectors within tolerance.
- **AC6** — Lazy decay: advancing the injected `Clock` by N days (test seam, §12.3) makes previously-known items appear in the due-review queue **without any background job having run**.
- **AC7** — Mistakes made in a lesson reappear in a Mistakes review session and leave the queue when answered correctly.
- **AC8** — Hearts: 5 wrong answers exhaust hearts and gate the session; hearts regenerate after the configured interval (timestamp-diff); a completed practice refills one.
- **AC9** — TTS (Tier 1): after a one-time voice install, TTS plays a Spanish sentence with the radio off; listen-and-type grades against the transcript.
- **AC10** — Speaking, available path (Tier 2): on a device *with* offline recognition, a spoken correct utterance passes and a "can't speak now" skip is always present.
- **AC11** — Export progress to a file, wipe app data, import the file → streak/XP/SRS state restored.
- **AC12** — Process death mid-lesson (test harness) resumes or cleanly restarts without corrupting progress.
- **AC13** — Streak survives a missed day **iff** a streak freeze was equipped (and the freeze is consumed).
- **AC14** — All bundled content carries the required attribution, visible in an in-app credits screen (proves C4).
- **AC15** — Content update preserves progress: simulating a `content.db` version bump (new asset) leaves `progress.db` — streak, XP, SRS rows — fully intact (proves D2).
- **AC16** — Speaking, unavailable path (Tier 2): on a device/emulator *without* offline recognition, speaking exercises are **disabled** (not shown) and the rest of the app is fully usable; **no cloud round-trip occurs** (proves §12.6 never violates C2). (AC10 covers the available path; AC16 covers the unavailable path — the two are disjoint.)
- **AC17** — Content vetting gate (C5/§4.6): the content build **fails** if any shipped row is missing a `source` or is not `vettingStatus = REVIEWED` (seed an `UNVETTED` row in a pipeline test and assert the build rejects it). Every shipped content row resolves to a source visible in the in-app attribution screen.

---

## 15. Risks & open questions

- **O1 — Frequency list & licensing (blocking content authoring).** Pick the exact CC-licensed frequency list (hermitdave CC BY-SA vs Leipzig CC BY 4.0 vs Wiktionary) and confirm ShareAlike handling so copyleft doesn't reach our authored content. *Owner decision needed before content build.*
- **O2 — Competitive feel without a server (Phase 3, not v1).** v1 cuts leagues entirely. *If* product later wants a competitive feel, the only client-only option is an NPC-simulated leaderboard + streak-vs-self ghost — fidelity-reduced and possibly worse than honest absence. Decide in Phase 3; not a v1 dependency. *Product decision.*
- **O3 — Audio strategy.** On-device TTS only (smallest, quality varies by device) vs bundling MP3s for top sentences (bigger, consistent). Lean TTS-first; revisit if quality testing fails.
- **O4 — FSRS spike contingency.** v1 ships FSRS-6 (D1, single engine). If the Phase-0 FSRS spike fails its reference-vector tests within its timebox, the contingency is to ship a Leitner box ladder instead (§6.1) — resolved during Phase 0, not carried as a parallel engine.
- **O5 — App size vs offline guarantee.** If the bundle exceeds Play's base limit, Play Asset Delivery install-time packs keep the offline guarantee but complicate the build; confirm sizes during a content-size spike.
- **R1 — Speech recognition fragmentation.** On-device recognition isn't universal; speaking must remain optional. (Mitigated by progressive-enhancement design.)
- **R2 — Clock tampering** corrupts SRS/streak (no server arbiter). Bounded defense in §6.7; accept residual risk for a single-user app.
- **R3 — CEFR approximation.** Frequency-band CEFR labels are approximate; mis-leveling is a content-quality risk mitigated by manual curation of early lemmas.
- **R4 — Incorrect/fabricated content teaches errors (high impact).** A wrong translation, bad accepted-answer set, or invented grammar "fact" actively mis-teaches and is hard to detect post-ship (no server to hotfix content — it rides an app update). Mitigated by the C5/§4.6 vetting pipeline: provenance on every row, automated checks, a human review gate, and a build that **fails** on any unvetted/sourceless row (AC17). LLM assistance is confined to drafting; its output is `UNVETTED` until human-reviewed.

## 16. Phased rollout

- **Phase 0 — Spikes.** (a) FSRS-6 implementation + reference-vector tests; (b) pre-populated Room DB from a sample bundled asset; (c) content-size spike (assemble a slice of Tatoeba + frequency list, measure AAB size, decide Asset Delivery). Resolves O4/O5 and informs O1 (the frequency-list/licensing choice is an owner decision that feeds the content-size spike).
- **Phase 1 — Core loop, offline.** Path/nodes, lesson generator, full non-speaking exercise taxonomy, deterministic grading, FSRS scheduling, XP/streak/hearts/gems, Words list, mistakes + due review. Meets **AC1–AC8, AC11–AC15**. **This is the MVP.** (AC15 — content-update preserves progress — belongs here because D2's two-DB safety is core to the MVP.)
- **Phase 2 — Audio & speech.** TTS listening exercises (Tier 1), SpeechRecognizer speaking (Tier 2, capability-gated), SFX. Meets **AC9, AC10, AC16**.
- **Phase 3 — Polish & depth.** Achievements/leveling, "magical" strength-meter animations and lesson-complete delight, larger vocabulary, broader B1 grammar, optional per-user FSRS weight optimization, and — only if O2 says yes — the fidelity-reduced NPC leaderboard.

---

*End of v1.1 draft. Research complete and verified; robot-review (requirements + architecture + scope) applied and cross-validated. Next: planning.*

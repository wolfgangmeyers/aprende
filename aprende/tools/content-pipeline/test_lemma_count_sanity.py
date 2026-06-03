#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import copy
import subprocess
import tempfile
import os
import sys
import unittest
from unittest import mock


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SANITY_SCRIPT = os.path.join(SCRIPT_DIR, "lemma_count_sanity.py")
BUILD_SCRIPT = os.path.join(SCRIPT_DIR, "build_content_db.py")


def load_sanity_module():
    spec = importlib.util.spec_from_file_location("lemma_count_sanity", SANITY_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SANITY_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_build_module():
    spec = importlib.util.spec_from_file_location("build_content_db", BUILD_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {BUILD_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sequencing_lexeme(build, lexeme_id, cefr_band="A1", frequency_rank=None):
    return build.Row(
        {
            "lexemeId": lexeme_id,
            "lemma": f"fixture {lexeme_id}",
            "pos": "noun",
            "gender": "M",
            "englishGloss": f"fixture {lexeme_id}",
            "frequencyRank": frequency_rank or lexeme_id,
            "cefrBand": cefr_band,
            "difficultyPrior": 0.5,
        },
        source="fixture",
        sourceId=f"fixture:{lexeme_id}",
        license="CC-BY-SA-3.0",
    )


def sequencing_exercise(exercise_id, node_id, target_id):
    return {
        "exerciseId": exercise_id,
        "nodeId": node_id,
        "sentenceId": exercise_id,
        "type": "TYPED_TRANSLATION",
        "direction": "ES_TO_EN",
        "targetItemId": target_id,
        "targetItemType": "LEXEME",
        "promptHint": None,
    }


def sequencing_fixture(build, count=9):
    lexemes = [sequencing_lexeme(build, lexeme_id) for lexeme_id in range(1, count + 1)]
    nodes = build.build_sequencing_plan(lexemes)["nodes"]
    intro_by_target = build.build_sequencing_plan(lexemes)["targetIntroNode"]
    exercises = [
        sequencing_exercise(exercise_id, intro_by_target[exercise_id], exercise_id)
        for exercise_id in range(1, count + 1)
    ]
    return lexemes, exercises, nodes, intro_by_target


class LemmaCountSanityIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sanity = load_sanity_module()
        cls.report = cls.sanity.build_sanity_report()

    def test_current_assertion_uses_real_pipeline_report(self):
        self.sanity.assert_current(self.report)
        self.assertEqual(2329, self.report["reviewableItemSummary"]["totalReviewableItems"])
        self.assertEqual(2339, self.report["reviewableItemSummary"]["sourceContentRows"]["rawLexemes"])
        self.assertEqual(8650, self.report["reviewableItemSummary"]["sourceContentRows"]["totalContentRows"])
        self.assertEqual(
            2329,
            self.report["reviewGate"]["reviewableItems"]["countedReviewedRows"],
        )
        self.assertEqual(7805, self.report["reviewGate"]["contentRows"]["rowsRequiringIndependentReviews"])
        self.assertEqual(0, self.report["reviewGate"]["contentRows"]["rowsWithInsufficientIndependentReviews"])

    def test_target_gate_reports_pilot_stop_phrase_gap_and_recalibrated_b1_count(self):
        self.assertEqual(580, self.report["postRebandGate"]["a1A2PhraseOrChunkItems"])
        self.assertEqual(981, self.report["postRebandGate"]["b1ReviewableItems"])
        failures = self.sanity.target_shape_failures(self.report)
        self.assertIn("A1+A2 phrase/chunk total 580 < 1500", failures)
        self.assertNotIn("B1 reviewable total 981 > 6000", failures)
        self.assertNotIn("on-ramp total reviewables below floor", failures)

    def test_on_ramp_report_counts_reviewed_pack_items(self):
        on_ramp = self.report["onRamp"]
        self.assertEqual("bounded_a1_a2_on_ramp_batch", on_ramp["status"])
        self.assertEqual(451, on_ramp["totalReviewables"])
        self.assertEqual(451, on_ramp["phraseOrChunkItems"])
        self.assertEqual(127, on_ramp["reviewablesByCefrBand"]["A1"])
        self.assertEqual(324, on_ramp["reviewablesByCefrBand"]["A2"])
        self.assertEqual(8, on_ramp["orderedBeginnerUnits"])

    def test_target_shape_still_reports_phrase_gap_when_under_floor(self):
        report = copy.deepcopy(self.report)
        report["postRebandGate"]["a1A2PhraseOrChunkItems"] = 44
        with self.assertRaises(SystemExit) as raised:
            self.sanity.assert_target_shape(report)
        self.assertIn(
            "A1+A2 phrase/chunk total 44 < 1500",
            str(raised.exception),
        )

    def test_c1_plus_lane_reports_current_reviewed_items(self):
        lane = self.report["c1PlusLane"]
        self.assertEqual("active_initial_lane", lane["status"])
        self.assertEqual(251, lane["reviewableItems"])
        self.assertEqual(4, len(lane["futureCategories"]))
        self.assertIn("B2 reviewables", lane["b2ToC1Boundary"])

    def test_ai_draft_item_with_less_than_two_reviews_is_not_reviewed(self):
        build = self.sanity.load_build_module()
        row = build.Row(
            {"lexemeId": 999999, "lemma": "fixture", "pos": "noun"},
            source=build.AI_DRAFT_SOURCE,
            sourceId="ai_draft:fixture",
            license="proprietary",
            vettingStatus=build.REVIEWED,
            reviewedBy=build.AUTO_REVIEW_REVIEWERS[build.AUTO_REVIEW_SPANISH],
            reviewedAt=build.AUTO_REVIEW_TS,
            reviewEvidence=[
                {
                    "reviewType": build.AUTO_REVIEW_SPANISH,
                    "reviewer": build.AUTO_REVIEW_REVIEWERS[build.AUTO_REVIEW_SPANISH],
                    "reviewedAt": build.AUTO_REVIEW_TS,
                    "decision": "APPROVED",
                    "notes": "fixture intentionally missing second review",
                }
            ],
        )

        status = self.sanity.review_gate_status(row, build)
        self.assertTrue(status["requiresIndependentReviews"])
        self.assertEqual(1, status["approvedIndependentReviewCount"])
        self.assertFalse(status["countsAsReviewed"])

    def test_generated_phrase_requires_authenticity_review_to_count_as_reviewed(self):
        build = self.sanity.load_build_module()
        row = build.Row(
            {
                "lexemeId": 999997,
                "lemma": "fuga de agua",
                "pos": "noun phrase",
                "phraseCefrRubric": {"cefrBand": "A2"},
                build.INDEPENDENT_REVIEW_REQUIRED_FIELD: True,
            },
            source="wiktionary",
            sourceId="fuga de agua",
            license="CC-BY-SA-3.0",
            vettingStatus=build.REVIEWED,
            reviewedBy=build.AUTO_REVIEW_REVIEWERS[build.AUTO_REVIEW_SPANISH],
            reviewedAt=build.AUTO_REVIEW_TS,
            reviewEvidence=[
                {
                    "reviewType": build.AUTO_REVIEW_SPANISH,
                    "reviewer": build.AUTO_REVIEW_REVIEWERS[build.AUTO_REVIEW_SPANISH],
                    "reviewedAt": build.AUTO_REVIEW_TS,
                    "decision": "APPROVED",
                    "notes": "correctness-only fixture",
                }
            ],
        )

        self.assertEqual(
            {build.AUTO_REVIEW_SPANISH, build.AUTO_REVIEW_AUTHENTICITY, build.AUTO_REVIEW_DIALECT},
            build.required_auto_review_types(row),
        )
        status = self.sanity.review_gate_status(row, build)
        self.assertTrue(status["requiresIndependentReviews"])
        self.assertEqual(1, status["approvedIndependentReviewCount"])
        self.assertFalse(status["countsAsReviewed"])

    def test_ai_draft_phrase_requires_authenticity_not_pedagogy_review(self):
        build = self.sanity.load_build_module()
        row = build.Row(
            {
                "lexemeId": 999995,
                "lemma": "fuga de agua",
                "pos": "noun phrase",
            },
            source=build.AI_DRAFT_SOURCE,
            sourceId="ai_draft:fuga-de-agua",
            license="proprietary",
            vettingStatus=build.REVIEWED,
            reviewedBy="+".join([
                build.AUTO_REVIEW_REVIEWERS[build.AUTO_REVIEW_SPANISH],
                build.AUTO_REVIEW_REVIEWERS[build.AUTO_REVIEW_PEDAGOGY],
            ]),
            reviewedAt=build.AUTO_REVIEW_TS,
            reviewEvidence=[
                {
                    "reviewType": build.AUTO_REVIEW_SPANISH,
                    "reviewer": build.AUTO_REVIEW_REVIEWERS[build.AUTO_REVIEW_SPANISH],
                    "reviewedAt": build.AUTO_REVIEW_TS,
                    "decision": "APPROVED",
                    "notes": "correctness fixture",
                },
                {
                    "reviewType": build.AUTO_REVIEW_PEDAGOGY,
                    "reviewer": build.AUTO_REVIEW_REVIEWERS[build.AUTO_REVIEW_PEDAGOGY],
                    "reviewedAt": build.AUTO_REVIEW_TS,
                    "decision": "APPROVED",
                    "notes": "pedagogy fixture",
                },
            ],
        )

        self.assertEqual(
            {build.AUTO_REVIEW_SPANISH, build.AUTO_REVIEW_AUTHENTICITY, build.AUTO_REVIEW_DIALECT},
            build.required_auto_review_types(row),
        )
        status = self.sanity.review_gate_status(row, build)
        self.assertEqual(
            [build.AUTO_REVIEW_AUTHENTICITY, build.AUTO_REVIEW_DIALECT],
            status["missingRequiredReviewTypes"],
        )
        self.assertFalse(status["countsAsReviewed"])

    def test_any_multiword_lexeme_requires_three_spanish_review_dimensions(self):
        build = self.sanity.load_build_module()
        row = build.Row(
            {
                "lexemeId": 999992,
                "lemma": "mesa reservada",
                "pos": "noun phrase",
            },
            source="wiktionary",
            sourceId="mesa reservada",
            license="CC-BY-SA-3.0",
            vettingStatus=build.AUTO_CHECKED,
        )

        self.assertEqual(
            {build.AUTO_REVIEW_SPANISH, build.AUTO_REVIEW_AUTHENTICITY, build.AUTO_REVIEW_DIALECT},
            build.required_auto_review_types(row),
        )

    def test_generated_sentence_dialect_review_scans_spanish_text(self):
        build = self.sanity.load_build_module()
        row = build.Row(
            {
                "sentenceId": 999991,
                "spanishText": "El grifo gotea.",
                "englishText": "The faucet drips.",
            },
            source=build.AI_DRAFT_SOURCE,
            sourceId="ai_draft:fixture-grifo",
            license="proprietary",
            vettingStatus=build.AUTO_CHECKED,
        )

        ok, notes = build.local_dialect_review(row, {})
        self.assertFalse(ok)
        self.assertIn("grifo", notes)

    def test_sourced_sentence_requires_spanish_authenticity_and_dialect_reviews(self):
        build = self.sanity.load_build_module()
        row = build.Row(
            {
                "sentenceId": 999989,
                "spanishText": "Tengo un perro.",
                "englishText": "I have a dog.",
            },
            source="tatoeba",
            sourceId="tatoeba:fixture",
            license="CC-BY-2.0-FR",
            vettingStatus=build.AUTO_CHECKED,
        )

        self.assertEqual(
            {build.AUTO_REVIEW_SPANISH, build.AUTO_REVIEW_AUTHENTICITY, build.AUTO_REVIEW_DIALECT},
            build.required_auto_review_types(row),
        )

    def test_generated_sentence_authenticity_rejects_aparece_aqui_filler(self):
        build = self.sanity.load_build_module()
        row = build.Row(
            {
                "sentenceId": 999990,
                "spanishText": "La promesa cumplida aparece aquí.",
                "englishText": "The kept promise appears here.",
            },
            source=build.AI_DRAFT_SOURCE,
            sourceId="ai_draft:fixture-filler",
            license="proprietary",
            vettingStatus=build.AUTO_CHECKED,
        )

        ok, notes = build.local_authenticity_review(row, {})
        self.assertFalse(ok)
        self.assertIn("template filler", notes)

    def test_cli_rejects_unvetted_content_fixture(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as out:
            result = subprocess.run(
                [sys.executable, BUILD_SCRIPT, "--out", out.name, "--inject-unvetted"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(2, result.returncode)
        self.assertIn("CONTENT VETTING GATE FAILED", result.stderr)
        self.assertIn("UNVETTED", result.stderr)

    def test_cli_rejects_single_review_ai_draft_fixture(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as out:
            result = subprocess.run(
                [sys.executable, BUILD_SCRIPT, "--out", out.name, "--inject-ai-draft-single-review"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(2, result.returncode)
        self.assertIn("CONTENT VETTING GATE FAILED", result.stderr)
        self.assertIn("lacks required independent automatic approvals", result.stderr)

    def test_cli_malformed_exercise_fixture_fails_coverage_gate(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as out, tempfile.NamedTemporaryFile(suffix=".json") as snapshot:
            result = subprocess.run(
                [
                    sys.executable,
                    BUILD_SCRIPT,
                    "--out",
                    out.name,
                    "--inject-malformed-exercise",
                    "--fail-on-coverage-gaps",
                    "--baseline-snapshot",
                    snapshot.name,
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(4, result.returncode)
        self.assertIn("COVERAGE BUDGET FAILED", result.stderr)
        self.assertIn("viajar is not learner-ready", result.stderr)

    def test_built_content_has_no_shippable_blocklist_or_filler_hits(self):
        build = self.sanity.load_build_module()
        lexemes, sentences, _accepted, _sentence_lexeme, _conj, _exercises, _nodes = build.vetted_sample()
        blocked_terms = set(build.PENINSULAR_OR_NON_NEUTRAL_LATAM_TERMS)
        lexeme_hits = [
            row.data["lemma"]
            for row in lexemes
            if set(build.phrase_tokens(row.data["lemma"])) & blocked_terms
        ]
        sentence_hits = [
            row.data["spanishText"]
            for row in sentences
            if (
                set(build.phrase_tokens(row.data["spanishText"])) & blocked_terms
                or "aparece aqui" in build.normalize_signal_text(row.data["spanishText"])
            )
        ]

        self.assertEqual([], lexeme_hits)
        self.assertEqual([], sentence_hits)

    def test_reviewed_phrase_sentence_violation_fails_instead_of_pruning(self):
        build = self.sanity.load_build_module()
        lexemes = []
        sentences = []
        accepted = []
        sentence_lexeme = []
        exercises = []
        pack = build.build_numbered_ai_accelerated_pack(999980, 999980, 999980, [
            (
                "llave de agua rota",
                "noun phrase",
                "F",
                "broken faucet",
                1800,
                "A2",
                0.5,
                "housing and repairs",
                "fixture",
                [("El grifo gotea.", "The faucet drips.")],
                {"cefrBand": "A2", "rubricReason": "fixture", "rubricSignals": ["domain:test"]},
            ),
        ])
        build.append_ai_accelerated_pack(
            pack, "fixture-reviewed-bad-sentence", 999980,
            lexemes, sentences, accepted, sentence_lexeme, exercises,
        )
        evidence = copy.deepcopy(build.REVIEW_EVIDENCE_ITEMS)
        build.register_per_item_review_evidence(
            "lexeme",
            lexemes[0],
            {build.AUTO_REVIEW_SPANISH, build.AUTO_REVIEW_AUTHENTICITY, build.AUTO_REVIEW_DIALECT},
            "Fixture per-item review evidence for a reviewed phrase with a bad generated sentence.",
        )
        evidence.update({
            build.review_evidence_key("lexeme", lexemes[0]): build.REVIEW_EVIDENCE_ITEMS[
                build.review_evidence_key("lexeme", lexemes[0])
            ]
        })
        with mock.patch.object(build, "REVIEW_EVIDENCE_ITEMS", evidence):
            build.prune_unreviewed_phrase_content(lexemes, sentences, accepted, sentence_lexeme, exercises)

            self.assertEqual(["El grifo gotea."], [row.data["spanishText"] for row in sentences])
            failures = build.stage_auto_check(lexemes, sentences, accepted)
            self.assertEqual([], failures)
            failures = build.stage_auto_review(lexemes, sentences, accepted)
        self.assertTrue(failures)
        self.assertIn("failed explicit review evidence", failures[0])

    def test_authenticity_review_rejects_retired_connector_tail_spam_shape(self):
        build = self.sanity.load_build_module()
        row = build.Row(
            {
                "lexemeId": 999996,
                "lemma": "paso pendiente de cuenta",
                "pos": "noun phrase",
                "phraseCefrRubric": {"cefrBand": "B1"},
                build.INDEPENDENT_REVIEW_REQUIRED_FIELD: True,
            },
            source="wiktionary",
            sourceId="paso pendiente de cuenta",
            license="CC-BY-SA-3.0",
            vettingStatus=build.AUTO_CHECKED,
        )

        ok, notes = build.local_authenticity_review(row, {})
        self.assertFalse(ok)
        self.assertIn("Cartesian", notes)

    def test_authenticity_review_rejects_unapproved_phrase_even_when_shape_is_plausible(self):
        build = self.sanity.load_build_module()
        row = build.Row(
            {
                "lexemeId": 999994,
                "lemma": "revisión de cuenta",
                "pos": "noun phrase",
                "phraseCefrRubric": {"cefrBand": "B1"},
                build.INDEPENDENT_REVIEW_REQUIRED_FIELD: True,
            },
            source="wiktionary",
            sourceId="revisión de cuenta",
            license="CC-BY-SA-3.0",
            vettingStatus=build.AUTO_CHECKED,
        )

        failures = build.stage_auto_review([row], [], [])
        self.assertTrue(failures)
        self.assertIn("missing explicit review evidence", failures[0])

    def test_payload_review_flags_do_not_bypass_explicit_review_evidence(self):
        build = self.sanity.load_build_module()
        row = build.Row(
            {
                "lexemeId": 999993,
                "lemma": "frase inventada amable",
                "pos": "phrase",
                "phraseCefrRubric": {
                    "cefrBand": "B1",
                    "rubricSignals": [
                        "correctness_review:approved",
                        "naturalness_review:approved",
                        "dialect_review:neutral_latam",
                        "generation:subagent",
                    ],
                },
                build.INDEPENDENT_REVIEW_REQUIRED_FIELD: True,
            },
            source="wiktionary",
            sourceId="frase inventada amable",
            license="CC-BY-SA-3.0",
            vettingStatus=build.AUTO_CHECKED,
        )

        spanish_ok, spanish_notes = build.local_spanish_review(row, {})
        authenticity_ok, authenticity_notes = build.local_authenticity_review(row, {})
        dialect_ok, dialect_notes = build.local_dialect_review(row, {})
        self.assertTrue(spanish_ok, spanish_notes)
        self.assertTrue(authenticity_ok, authenticity_notes)
        self.assertTrue(dialect_ok, dialect_notes)
        failures = build.stage_auto_review([row], [], [])
        self.assertTrue(failures)
        self.assertIn("missing explicit review evidence", failures[0])

    def test_retired_spam_pack_constants_are_absent(self):
        build = self.sanity.load_build_module()
        for pack_number in range(42, 70):
            self.assertFalse(
                hasattr(build, f"AI_ACCELERATED_PACK_A2_{pack_number:03d}"),
                f"retired spam pack A2_{pack_number:03d} should not remain",
            )

    def test_replacement_domain_registry_covers_required_domains(self):
        build = self.sanity.load_build_module()
        expected_domains = {
            "admin_workflow_services",
            "instructions_requirements",
            "confirmations_authorizations",
            "steps_status_problems",
            "reasons_proofs_notices_deadlines",
            "locations_directions_contacts",
            "payments",
            "travel_routes",
            "health",
            "requests_complaints",
            "work_service_operations",
            "decisions",
            "documents_forms",
            "customer_service",
            "workplace_social_negotiation",
            "housing_maintenance",
        }
        self.assertEqual(expected_domains, build.EXPECTED_REPLACEMENT_DOMAINS)
        self.assertEqual(expected_domains, {domain for domain, _pack in build.REPLACEMENT_DOMAIN_PACKS})
        for domain, pack in build.REPLACEMENT_DOMAIN_PACKS:
            self.assertGreaterEqual(len(pack), 12, domain)

    def test_b2_batch_3_registry_covers_reviewed_json_pack(self):
        build = self.sanity.load_build_module()
        expected_domain_counts = {
            "b2_nuanced_opinions_argumentation": 60,
            "b2_abstract_social_topics": 57,
            "b2_hypotheticals_counterfactuals": 56,
            "b2_concession_nuanced_emotion": 56,
            "b2_formal_professional_register": 52,
            "b2_reported_speech_sophisticated_connectors": 60,
        }
        actual_domain_counts = {
            domain: len(pack)
            for domain, pack in build.AI_ACCELERATED_PACK_B2_BATCH_3_PACKS
        }

        self.assertEqual(expected_domain_counts, actual_domain_counts)
        self.assertEqual(341, sum(actual_domain_counts.values()))
        for domain, pack in build.AI_ACCELERATED_PACK_B2_BATCH_3_PACKS:
            for item in pack:
                self.assertEqual("B2", item["cefrBand"], domain)
                self.assertIn(item["lemma"], build.SPANISH_CORRECTNESS_PHRASE_LEDGER)
                self.assertIn(item["lemma"], build.AUTHENTIC_PHRASE_LEDGER)
                self.assertIn(item["lemma"], build.NEUTRAL_LATAM_PHRASE_LEDGER)

    def test_manifest_includes_generated_phrase_lexeme_review_evidence(self):
        build = self.sanity.load_build_module()
        lexemes, sentences, accepted, _sentence_lexeme, _conj, _exercises, _nodes = build.vetted_sample()
        failures = build.stage_auto_check(lexemes, sentences, accepted)
        self.assertEqual([], failures)
        failures = build.stage_auto_review(lexemes, sentences, accepted)
        self.assertEqual([], failures)
        build.stage_review_gate(lexemes, sentences, accepted)

        with tempfile.TemporaryDirectory() as tmp:
            manifest = build.write_manifest(tmp, lexemes, sentences, accepted)

        pilot_lexeme_reviews = [
            entry for entry in manifest["autoReviewLedger"]
            if entry["table"] == "lexeme"
            and entry["sourceId"] == "fuga de agua"
        ]
        self.assertEqual(1, len(pilot_lexeme_reviews))
        review_types = {
            evidence["reviewType"]
            for evidence in pilot_lexeme_reviews[0]["reviewEvidence"]
            if evidence["decision"] == "APPROVED"
        }
        self.assertEqual(
            {build.AUTO_REVIEW_SPANISH, build.AUTO_REVIEW_AUTHENTICITY, build.AUTO_REVIEW_DIALECT},
            review_types,
        )
        evidence_bases = {
            evidence["evidenceBasis"]
            for evidence in pilot_lexeme_reviews[0]["reviewEvidence"]
        }
        self.assertEqual({build.EVIDENCE_BASIS_LEGACY}, evidence_bases)

    def test_existing_reviewable_items_pass_with_legacy_pack_attestation(self):
        build = self.sanity.load_build_module()
        lexemes, sentences, accepted, sentence_lexeme, _conj, exercises, _nodes = build.vetted_sample()
        self.assertEqual([], build.stage_auto_check(lexemes, sentences, accepted))
        self.assertEqual([], build.stage_auto_review(lexemes, sentences, accepted))
        build.stage_review_gate(lexemes, sentences, accepted)
        build.stage_publish_gate(lexemes, sentences, accepted)

        coverage = build.build_coverage_report(lexemes, sentences, accepted, sentence_lexeme, exercises)
        self.assertEqual(2329, coverage["summary"]["learnerReadyLexemes"])
        legacy_lexeme_reviews = [
            row for row in lexemes
            if build.required_auto_review_types(row)
            and all(
                evidence.get("evidenceBasis") == build.EVIDENCE_BASIS_LEGACY
                for evidence in row.reviewEvidence
            )
        ]
        self.assertEqual(1346, len(legacy_lexeme_reviews))

    def review_evidence_failure_for_known_lexeme(self, mutate):
        build = self.sanity.load_build_module()
        lexemes, sentences, accepted, _sentence_lexeme, _conj, _exercises, _nodes = build.vetted_sample()
        evidence = copy.deepcopy(build.REVIEW_EVIDENCE_ITEMS)
        mutate(evidence["lexeme:4072"])
        with mock.patch.object(build, "REVIEW_EVIDENCE_ITEMS", evidence):
            self.assertEqual([], build.stage_auto_check(lexemes, sentences, accepted))
            failures = build.stage_auto_review(lexemes, sentences, accepted)
        return failures

    def test_per_item_review_boilerplate_rationales_hard_fail_catalog_validation(self):
        build = self.sanity.load_build_module()
        evidence = copy.deepcopy(build.REVIEW_EVIDENCE_ITEMS)
        changed = 0
        for key, item in evidence.items():
            dimensions = item.get("dimensions", {})
            if build.AUTO_REVIEW_AUTHENTICITY not in dimensions:
                continue
            if dimensions[build.AUTO_REVIEW_AUTHENTICITY].get("evidenceBasis") != build.EVIDENCE_BASIS_PER_ITEM:
                continue
            dimensions[build.AUTO_REVIEW_AUTHENTICITY]["rationale"] = (
                f"Fixture reviewer approved item {key}: '{item['crossChecks']['text']}' "
                "as natural learner-useful Spanish."
            )
            changed += 1
            if changed == 6:
                break

        self.assertEqual(6, changed)
        with self.assertRaises(SystemExit) as raised:
            build.validate_review_evidence_catalog(evidence)
        self.assertIn("per_item_review rationale boilerplate pattern reused 6 times", str(raised.exception))

    def corrupt_prune_evidence_failure(self, mutate=None):
        build = self.sanity.load_build_module()
        pack = build.build_numbered_ai_accelerated_pack(999981, 999981, 999981, [
            (
                "frase revisada de prueba",
                "phrase",
                None,
                "reviewed test phrase",
                1800,
                "A2",
                0.5,
                "test",
                "fixture",
                [("La frase revisada de prueba funciona.", "The reviewed test phrase works.")],
                {"cefrBand": "A2", "rubricReason": "fixture", "rubricSignals": ["domain:test"]},
            ),
        ])
        lexemes = []
        sentences = []
        accepted = []
        sentence_lexeme = []
        exercises = []
        build.append_ai_accelerated_pack(
            pack, "fixture-corrupt-evidence", 999981,
            lexemes, sentences, accepted, sentence_lexeme, exercises,
        )
        evidence = copy.deepcopy(build.REVIEW_EVIDENCE_ITEMS)
        build.register_per_item_review_evidence(
            "lexeme",
            lexemes[0],
            {build.AUTO_REVIEW_SPANISH, build.AUTO_REVIEW_AUTHENTICITY, build.AUTO_REVIEW_DIALECT},
            "Fixture-specific rationale for frase revisada de prueba evidence.",
        )
        key = build.review_evidence_key("lexeme", lexemes[0])
        evidence[key] = build.REVIEW_EVIDENCE_ITEMS[key]
        if mutate is None:
            del evidence[key]
        else:
            mutate(evidence[key])
        with mock.patch.object(build, "REVIEW_EVIDENCE_ITEMS", evidence):
            with self.assertRaises(SystemExit) as raised:
                build.prune_unreviewed_phrase_content(lexemes, sentences, accepted, sentence_lexeme, exercises)
        return str(raised.exception)

    def test_prune_missing_review_evidence_hard_fails(self):
        message = self.corrupt_prune_evidence_failure()
        self.assertIn("CORRUPT REVIEW EVIDENCE", message)
        self.assertIn("missing explicit review evidence", message)

    def test_prune_mismatched_review_evidence_hash_hard_fails(self):
        message = self.corrupt_prune_evidence_failure(
            lambda item: item.update({"contentHash": "sha256:bad"})
        )
        self.assertIn("CORRUPT REVIEW EVIDENCE", message)
        self.assertIn("mismatched content hash", message)

    def test_prune_non_approved_review_evidence_hard_fails(self):
        def mutate(item):
            item["dimensions"]["spanish_authenticity"]["verdict"] = "REJECTED"

        message = self.corrupt_prune_evidence_failure(mutate)
        self.assertIn("CORRUPT REVIEW EVIDENCE", message)
        self.assertIn("verdict is 'REJECTED', not APPROVED", message)

    def test_prune_missing_dimension_review_evidence_hard_fails(self):
        def mutate(item):
            del item["dimensions"]["spanish_dialect_neutral_latam"]

        message = self.corrupt_prune_evidence_failure(mutate)
        self.assertIn("CORRUPT REVIEW EVIDENCE", message)
        self.assertIn("missing evidence for spanish_dialect_neutral_latam", message)

    def test_missing_required_review_evidence_hard_fails(self):
        build = self.sanity.load_build_module()
        lexemes, sentences, accepted, _sentence_lexeme, _conj, _exercises, _nodes = build.vetted_sample()
        evidence = copy.deepcopy(build.REVIEW_EVIDENCE_ITEMS)
        del evidence["lexeme:4072"]["dimensions"][build.AUTO_REVIEW_AUTHENTICITY]
        with mock.patch.object(build, "REVIEW_EVIDENCE_ITEMS", evidence):
            self.assertEqual([], build.stage_auto_check(lexemes, sentences, accepted))
            failures = build.stage_auto_review(lexemes, sentences, accepted)
        self.assertTrue(any("missing evidence for spanish_authenticity" in failure for failure in failures))

    def test_mismatched_review_evidence_hash_hard_fails(self):
        failures = self.review_evidence_failure_for_known_lexeme(
            lambda item: item.update({"contentHash": "sha256:bad"})
        )
        self.assertTrue(any("mismatched content hash" in failure for failure in failures))

    def test_mismatched_review_evidence_source_id_hard_fails(self):
        def mutate(item):
            item["crossChecks"]["sourceId"] = "different-source"

        failures = self.review_evidence_failure_for_known_lexeme(mutate)
        self.assertTrue(any("cross-check sourceId mismatch" in failure for failure in failures))

    def test_mismatched_review_evidence_text_hard_fails(self):
        def mutate(item):
            item["crossChecks"]["text"] = "texto cambiado"

        failures = self.review_evidence_failure_for_known_lexeme(mutate)
        self.assertTrue(any("cross-check text mismatch" in failure for failure in failures))

    def test_non_approved_review_evidence_hard_fails(self):
        def mutate(item):
            item["dimensions"]["spanish_authenticity"]["verdict"] = "REJECTED"

        failures = self.review_evidence_failure_for_known_lexeme(mutate)
        self.assertTrue(any("verdict is 'REJECTED', not APPROVED" in failure for failure in failures))

    def test_legacy_pack_attestation_on_new_item_hard_fails(self):
        build = self.sanity.load_build_module()
        row = build.Row(
            {
                "lexemeId": 999996,
                "lemma": "frase nueva revisada",
                "pos": "phrase",
                "gender": None,
                "englishGloss": "new reviewed phrase",
                "frequencyRank": 1800,
                "cefrBand": "A2",
                "difficultyPrior": 0.5,
                "phraseCefrRubric": {"cefrBand": "A2", "rubricReason": "fixture", "rubricSignals": ["fixture"]},
                build.INDEPENDENT_REVIEW_REQUIRED_FIELD: True,
            },
            source="wiktionary",
            sourceId="frase nueva revisada",
            license="CC-BY-SA-3.0",
        )
        evidence = copy.deepcopy(build.REVIEW_EVIDENCE_ITEMS)
        key = build.review_evidence_key("lexeme", row)
        evidence[key] = {
            "itemType": "lexeme",
            "stableKey": key,
            "contentHash": build.review_evidence_content_hash("lexeme", row),
            "crossChecks": build.review_evidence_cross_checks("lexeme", row),
            "_evidenceSourceFile": "in_memory_fixture",
            "dimensions": {
                review_type: {
                    "verdict": build.APPROVED_VERDICT,
                    "reviewer": build.AUTO_REVIEW_REVIEWERS[review_type],
                    "reviewedAt": build.AUTO_REVIEW_TS,
                    "rationale": "fixture incorrectly using legacy attestation for new content",
                    "evidenceBasis": build.EVIDENCE_BASIS_LEGACY,
                    "source": "fixture",
                }
                for review_type in {
                    build.AUTO_REVIEW_SPANISH,
                    build.AUTO_REVIEW_AUTHENTICITY,
                    build.AUTO_REVIEW_DIALECT,
                }
            },
        }
        lexemes, sentences, accepted = [row], [], []
        with mock.patch.object(build, "REVIEW_EVIDENCE_ITEMS", evidence):
            self.assertEqual([], build.stage_auto_check(lexemes, sentences, accepted))
            failures = build.stage_auto_review(lexemes, sentences, accepted)
        self.assertTrue(any("legacy_pack_attestation is not allowed" in failure for failure in failures))

    def test_rebanded_source_item_with_less_than_two_reviews_is_not_reviewed(self):
        build = self.sanity.load_build_module()
        row = build.Row(
            {
                "lexemeId": 999998,
                "lemma": "mesa reservada",
                "pos": "noun phrase",
                self.sanity.INDEPENDENT_REVIEW_REQUIRED_FIELD: True,
            },
            source="wiktionary",
            sourceId="mesa reservada",
            license="CC-BY-SA-3.0",
            vettingStatus=build.REVIEWED,
            reviewedBy="wolfgang",
            reviewedAt=build.AUTO_REVIEW_TS,
        )

        status = self.sanity.review_gate_status(row, build)
        self.assertTrue(status["requiresIndependentReviews"])
        self.assertEqual(0, status["approvedIndependentReviewCount"])
        self.assertFalse(status["countsAsReviewed"])

    def test_target_assertion_fails_on_insufficient_independent_reviews(self):
        report = copy.deepcopy(self.report)
        report["postRebandGate"]["a1A2PhraseOrChunkItems"] = 1500
        report["postRebandGate"]["b1ReviewableItems"] = 6000
        report["onRamp"]["totalReviewables"] = 300
        report["onRamp"]["phraseOrChunkItems"] = 100
        report["onRamp"]["reviewablesByCefrBand"]["A1"] = 120
        report["onRamp"]["reviewablesByCefrBand"]["A2"] = 120
        report["onRamp"]["orderedBeginnerUnits"] = 8
        report["reviewGate"]["reviewableItems"]["rowsWithInsufficientIndependentReviews"] = 1

        with self.assertRaises(SystemExit) as raised:
            self.sanity.assert_target_shape(report)
        self.assertIn(
            "reviewable items include rows with insufficient independent reviews",
            str(raised.exception),
        )

    def test_target_assertion_honors_reviewed_reband_audit_justification(self):
        report = copy.deepcopy(self.report)
        report["postRebandGate"]["reviewedAuditJustificationPresent"] = True
        failures = self.sanity.target_shape_failures(report)
        self.assertNotIn("A1+A2 phrase/chunk total 44 < 1500", failures)


class SequencingValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = load_build_module()

    def test_validate_sequencing_rejects_use_before_assigned_intro_node(self):
        lexemes, exercises, nodes, intro_by_target = sequencing_fixture(self.build, count=9)
        late_target = 9
        self.assertGreater(intro_by_target[late_target], 1)
        exercises = [
            {**exercise, "nodeId": 1}
            if exercise["targetItemId"] == late_target else exercise
            for exercise in exercises
        ]

        report = self.build.validate_sequencing(lexemes, exercises, nodes)

        self.assertEqual("failed", report["status"])
        self.assertEqual(1, len(report["failures"]["usesBeforeIntroduction"]))
        violation = report["failures"]["usesBeforeIntroduction"][0]
        self.assertEqual(late_target, violation["targetItemId"])
        self.assertEqual(1, violation["nodeId"])
        self.assertEqual(intro_by_target[late_target], violation["firstIntroductionNode"])
        with self.assertRaises(SystemExit) as raised:
            self.build.enforce_sequencing(report)
        self.assertEqual(5, raised.exception.code)

    def test_validate_sequencing_rejects_intro_node_over_target_cap(self):
        lexemes = [sequencing_lexeme(self.build, lexeme_id) for lexeme_id in range(1, 10)]
        with mock.patch.object(self.build, "chunked", lambda items, _size: [items]):
            nodes = self.build.build_sequencing_plan(lexemes)["nodes"]
            intro_by_target = self.build.build_sequencing_plan(lexemes)["targetIntroNode"]
            exercises = [
                sequencing_exercise(exercise_id, intro_by_target[exercise_id], exercise_id)
                for exercise_id in range(1, 10)
            ]
            report = self.build.validate_sequencing(lexemes, exercises, nodes)

        self.assertEqual("failed", report["status"])
        self.assertEqual(1, len(report["failures"]["introNodesOverTargetCap"]))
        self.assertEqual(9, report["failures"]["introNodesOverTargetCap"][0]["newTargetCount"])
        with self.assertRaises(SystemExit) as raised:
            self.build.enforce_sequencing(report)
        self.assertEqual(5, raised.exception.code)

    def test_validate_sequencing_rejects_target_without_intro_exercise(self):
        lexemes, exercises, nodes, _intro_by_target = sequencing_fixture(self.build, count=2)
        missing_target = 2
        exercises = [
            exercise for exercise in exercises
            if exercise["targetItemId"] != missing_target
        ]

        report = self.build.validate_sequencing(lexemes, exercises, nodes)

        self.assertEqual("failed", report["status"])
        self.assertEqual([missing_target], report["failures"]["targetsMissingFirstIntroduction"])
        self.assertNotIn(str(missing_target), report["firstIntroductionNodeByTarget"])
        with self.assertRaises(SystemExit) as raised:
            self.build.enforce_sequencing(report)
        self.assertEqual(5, raised.exception.code)

    def test_real_built_path_is_well_formed(self):
        lexemes, sentences, accepted, sentence_lexeme, _conj, exercises, nodes = self.build.vetted_sample()
        coverage = self.build.build_coverage_report(lexemes, sentences, accepted, sentence_lexeme, exercises)
        learner_ready_ids = {
            entry["lexemeId"]
            for entry in coverage["lexemeReadiness"]
            if entry["learnerReady"]
        }

        report = self.build.validate_sequencing(lexemes, exercises, nodes)

        self.assertEqual("passed", report["status"])
        self.assertEqual(
            report["summary"]["nodeCount"],
            report["counts"]["nodesByKind"]["intro"] + report["counts"]["nodesByKind"]["checkpoint"],
        )
        self.assertEqual(list(range(len(nodes))), [display_order for _node_id, _title, display_order in nodes])
        self.assertTrue(learner_ready_ids <= {int(target_id) for target_id in report["firstIntroductionNodeByTarget"]})
        self.assertEqual([], report["failures"]["usesBeforeIntroduction"])
        self.assertLessEqual(
            report["summary"]["maxNewTargetsInIntroNode"],
            self.build.SEQUENCING_MAX_NEW_TARGETS_PER_NODE,
        )
        self.assertEqual(
            [],
            [entry for entry in report["nodeCounts"] if entry["title"].endswith("Review") and entry["newTargetCount"]],
        )
        self.assertEqual(
            [],
            [entry for entry in report["nodeCounts"] if not entry["title"].endswith("Review") and not entry["newTargetCount"]],
        )

    def test_real_built_path_has_no_empty_nodes(self):
        _lexemes, _sentences, _accepted, _sentence_lexeme, _conj, exercises, nodes = self.build.vetted_sample()
        exercise_count_by_node = {}
        for exercise in exercises:
            exercise_count_by_node[exercise["nodeId"]] = exercise_count_by_node.get(exercise["nodeId"], 0) + 1

        empty_nodes = [
            {"nodeId": node_id, "title": title}
            for node_id, title, _display_order in nodes
            if exercise_count_by_node.get(node_id, 0) == 0
        ]

        self.assertEqual([], empty_nodes)

    def test_first_review_node_is_completable_and_unlocks_next_position(self):
        _lexemes, _sentences, _accepted, _sentence_lexeme, _conj, exercises, nodes = self.build.vetted_sample()
        exercise_count_by_node = {}
        for exercise in exercises:
            exercise_count_by_node[exercise["nodeId"]] = exercise_count_by_node.get(exercise["nodeId"], 0) + 1
        ordered_nodes = sorted(nodes, key=lambda row: row[2])
        review_index = next(
            index for index, (_node_id, title, _display_order) in enumerate(ordered_nodes)
            if title == "A1 Unit 1 Review"
        )
        review_node_id, _review_title, _review_order = ordered_nodes[review_index]
        next_node_id, _next_title, _next_order = ordered_nodes[review_index + 1]

        self.assertGreater(exercise_count_by_node.get(review_node_id, 0), 0)

        completed_nodes = {node_id for node_id, _title, _order in ordered_nodes[:review_index + 1]}
        prev_completed = True
        unlocked_by_node = {}
        for node_id, _title, _display_order in ordered_nodes:
            completed = node_id in completed_nodes
            unlocked_by_node[node_id] = prev_completed or completed
            prev_completed = completed

        self.assertTrue(unlocked_by_node[next_node_id])


class PhraseCefrRubricIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = load_build_module()

    def setUp(self):
        self.build.reset_phrase_cefr_rubric_audit()

    def build_fixture_pack(self):
        rows = [
            ("entrada principal", "f", "main entrance", "routine place", "una", "La"),
            ("agua fría", "f", "cold water", "food and drink", "un poco de", "El"),
            ("mi casa", "f", "my house", "home", None, "Mi"),
            ("cita médica", "f", "medical appointment", "routine health errand", "una", "La"),
            ("mesa reservada", "f", "reserved table", "restaurant booking", "una", "La"),
            ("billete de ida", "m", "one-way ticket", "routine travel", "un", "El"),
            ("tienda abierta", "f", "open store", "shopping", "una", "La"),
            ("reclamación formal", "f", "formal complaint", "formal services", "una", "La"),
            (
                "procedimiento administrativo", "m", "administrative procedure",
                "specialized medical-administrative services", "un", "El",
            ),
            ("responsabilidad legal", "f", "legal responsibility", "legal abstract", "una", "La"),
            ("informe detallado", "m", "detailed report", "explanation and documentation", "un", "El"),
        ]
        specs = self.build.build_phrase_pack_specs(rows)
        return self.build.build_numbered_ai_accelerated_phrase_pack(900000, 910000, 920000, specs)

    def test_real_phrase_pack_builder_assigns_fixture_cefr_bands(self):
        pack = self.build_fixture_pack()
        actual = {item["lemma"]: item["cefrBand"] for item in pack}

        self.assertEqual("A1", actual["entrada principal"])
        self.assertEqual("A1", actual["agua fría"])
        self.assertEqual("A1", actual["mi casa"])
        self.assertEqual("A2", actual["cita médica"])
        self.assertEqual("A2", actual["mesa reservada"])
        self.assertEqual("A2", actual["billete de ida"])
        self.assertEqual("A2", actual["tienda abierta"])
        self.assertEqual("B1", actual["reclamación formal"])
        self.assertEqual("B1", actual["procedimiento administrativo"])
        self.assertEqual("B1", actual["responsabilidad legal"])
        self.assertEqual("B1", actual["informe detallado"])

    def test_a1_requires_routine_a1_domain_signal(self):
        specs = self.build.build_phrase_pack_specs([
            ("agua mineral", "f", "mineral water", "banking", "un poco de", "El"),
            ("entrada principal", "f", "main entrance", "office", "una", "La"),
            ("agua fría", "f", "cold water", "food and drink", "un poco de", "El"),
            ("mi casa", "f", "my house", "home", None, "Mi"),
        ])
        pack = self.build.build_numbered_ai_accelerated_phrase_pack(903000, 913000, 923000, specs)
        actual = {item["lemma"]: item["cefrBand"] for item in pack}

        self.assertEqual("A2", actual["agua mineral"])
        self.assertEqual("A2", actual["entrada principal"])
        self.assertEqual("A1", actual["agua fría"])
        self.assertEqual("A1", actual["mi casa"])

    def test_intermediate_terms_do_not_fall_through_bare_a2_domains(self):
        specs = self.build.build_phrase_pack_specs([
            ("hipoteca pendiente", "f", "pending mortgage", "banking", "una", "La"),
            ("multa de tráfico", "f", "traffic fine", "bureaucracy", "una", "La"),
            ("denuncia policial", "f", "police report", "safety", "una", "La"),
        ])
        pack = self.build.build_numbered_ai_accelerated_phrase_pack(904000, 914000, 924000, specs)
        actual = {item["lemma"]: item["cefrBand"] for item in pack}

        self.assertEqual("B1", actual["hipoteca pendiente"])
        self.assertEqual("B1", actual["multa de tráfico"])
        self.assertEqual("B1", actual["denuncia policial"])

    def test_mixed_phrase_pack_produces_multiple_cefr_bands(self):
        pack = self.build_fixture_pack()
        self.assertGreaterEqual(len({item["cefrBand"] for item in pack}), 2)

    def test_manual_override_requires_reason_and_is_audited(self):
        with self.assertRaisesRegex(ValueError, "requires a manualRubricReason"):
            self.build.build_phrase_pack_specs([
                {
                    "lemma": "frase de prueba",
                    "gender": "f",
                    "englishGloss": "test phrase",
                    "domain": "test fixture",
                    "indefiniteArticle": "una",
                    "definiteArticle": "La",
                    "manualCefrBand": "A2",
                }
            ])

        specs = self.build.build_phrase_pack_specs([
            {
                "lemma": "frase de prueba",
                "gender": "f",
                "englishGloss": "test phrase",
                "domain": "test fixture",
                "indefiniteArticle": "una",
                "definiteArticle": "La",
                "manualCefrBand": "A2",
                "manualRubricReason": "fixture demonstrates explicit source override",
            }
        ])
        pack = self.build.build_numbered_ai_accelerated_phrase_pack(901000, 911000, 921000, specs)
        self.assertEqual("A2", pack[0]["cefrBand"])

        audit = self.build.build_phrase_cefr_rubric_report()
        entry = next(record for record in audit["items"] if record["lemma"] == "frase de prueba")
        self.assertEqual("manual_override", entry["rubricReason"])
        self.assertIn("manual_override:A2", entry["rubricSignals"])
        self.assertIn("fixture demonstrates explicit source override", entry["manualRubricReason"])

    def test_phrase_cefr_rubric_report_artifact_is_written(self):
        self.build.build_phrase_pack_specs([
            ("cita médica", "f", "medical appointment", "routine health errand", "una", "La"),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            report = self.build.write_phrase_cefr_rubric_report(tmp)
            path = os.path.join(tmp, "phrase_cefr_rubric_report.json")
            self.assertTrue(os.path.exists(path))
            self.assertIn("itemsByCefrBand", report)
            self.assertEqual(1, report["itemsByCefrBand"]["A2"])

    def test_low_frequency_and_idiomatic_signals_force_b1_plus(self):
        specs = self.build.build_phrase_pack_specs([
            {
                "lemma": "tienda abierta",
                "gender": "f",
                "englishGloss": "open store",
                "domain": "shopping",
                "indefiniteArticle": "una",
                "definiteArticle": "La",
                "frequencyRank": 2601,
            },
            {
                "lemma": "mesa reservada",
                "gender": "f",
                "englishGloss": "reserved table",
                "domain": "frase hecha",
                "indefiniteArticle": "una",
                "definiteArticle": "La",
                "frequencyRank": 1200,
            },
        ])
        pack = self.build.build_numbered_ai_accelerated_phrase_pack(902000, 912000, 922000, specs)
        actual = {item["lemma"]: item["cefrBand"] for item in pack}
        self.assertEqual("B1", actual["tienda abierta"])
        self.assertEqual("B1", actual["mesa reservada"])

        audit = {
            record["lemma"]: record["rubricSignals"]
            for record in self.build.build_phrase_cefr_rubric_report()["items"]
        }
        self.assertIn("b1_plus:low_frequency", audit["tienda abierta"])
        self.assertIn("b1_plus:idiomatic", audit["mesa reservada"])

    def test_full_rubric_report_assesses_every_built_phrase_or_chunk(self):
        build = load_build_module()
        build.reset_phrase_cefr_rubric_audit()
        lexemes, _sentences, _accepted, _sentence_lexeme, _conj, _exercises, _nodes = build.vetted_sample()
        report = build.build_phrase_cefr_rubric_report(lexemes)
        phrase_or_chunk_count = sum(
            1
            for row in lexemes
            if row.data["pos"] == "noun phrase" or " " in row.data["lemma"].strip()
        )

        self.assertEqual(phrase_or_chunk_count, report["itemCount"])
        self.assertEqual(1597, report["helperAssignedItemCount"])
        self.assertEqual(0, report["legacyExplicitBandAssessedItemCount"])
        self.assertEqual(1597, report["itemCount"])
        self.assertEqual(
            1597,
            report["itemsByAssignmentSource"]["phrase_pack_rubric"],
        )
        self.assertNotIn("legacy_explicit_band_assessed_not_rebanded", report["itemsByAssignmentSource"])
        self.assertEqual(
            phrase_or_chunk_count,
            len({entry["lexemeId"] for entry in report["items"]}),
        )


if __name__ == "__main__":
    unittest.main()

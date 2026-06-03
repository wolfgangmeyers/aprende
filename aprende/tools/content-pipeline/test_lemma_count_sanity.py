#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import copy
import tempfile
import os
import sys
import unittest


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


class LemmaCountSanityIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sanity = load_sanity_module()
        cls.report = cls.sanity.build_sanity_report()

    def test_current_assertion_uses_real_pipeline_report(self):
        self.sanity.assert_current(self.report)
        self.assertEqual(7431, self.report["reviewableItemSummary"]["totalReviewableItems"])
        self.assertEqual(7431, self.report["reviewableItemSummary"]["sourceContentRows"]["rawLexemes"])
        self.assertEqual(37278, self.report["reviewableItemSummary"]["sourceContentRows"]["totalContentRows"])
        self.assertEqual(
            7431,
            self.report["reviewGate"]["reviewableItems"]["countedReviewedRows"],
        )

    def test_target_gate_passes_recalibrated_phrase_and_b1_counts(self):
        self.assertEqual(2050, self.report["postRebandGate"]["a1A2PhraseOrChunkItems"])
        self.assertEqual(5007, self.report["postRebandGate"]["b1ReviewableItems"])
        failures = self.sanity.target_shape_failures(self.report)
        self.assertNotIn("A1+A2 phrase/chunk total 2050 < 1500", failures)
        self.assertNotIn("B1 reviewable total 5007 > 6000", failures)
        self.assertIn("on-ramp total reviewables below floor", failures)

    def test_target_shape_still_reports_phrase_gap_when_under_floor(self):
        report = copy.deepcopy(self.report)
        report["postRebandGate"]["a1A2PhraseOrChunkItems"] = 44
        with self.assertRaises(SystemExit) as raised:
            self.sanity.assert_target_shape(report)
        self.assertIn(
            "A1+A2 phrase/chunk total 44 < 1500",
            str(raised.exception),
        )

    def test_c1_plus_lane_is_reported_even_at_zero(self):
        lane = self.report["c1PlusLane"]
        self.assertEqual("explicit_gap", lane["status"])
        self.assertEqual(0, lane["reviewableItems"])
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
        self.assertEqual(3360, report["helperAssignedItemCount"])
        self.assertEqual(3316, report["legacyExplicitBandAssessedItemCount"])
        self.assertEqual(6676, report["itemCount"])
        self.assertEqual(
            3360,
            report["itemsByAssignmentSource"]["phrase_pack_rubric"],
        )
        self.assertIn("legacy_explicit_band_assessed_not_rebanded", report["itemsByAssignmentSource"])
        self.assertEqual(
            phrase_or_chunk_count,
            len({entry["lexemeId"] for entry in report["items"]}),
        )


if __name__ == "__main__":
    unittest.main()

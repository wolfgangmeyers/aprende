#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import copy
import os
import unittest


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SANITY_SCRIPT = os.path.join(SCRIPT_DIR, "lemma_count_sanity.py")


def load_sanity_module():
    spec = importlib.util.spec_from_file_location("lemma_count_sanity", SANITY_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SANITY_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
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

    def test_target_gate_fails_while_a1_a2_phrase_chunks_are_zero(self):
        self.assertEqual(0, self.report["postRebandGate"]["a1A2PhraseOrChunkItems"])
        with self.assertRaises(SystemExit) as raised:
            self.sanity.assert_target_shape(self.report)
        self.assertIn(
            "A1+A2 phrase/chunk total 0 < 1500",
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
        self.assertNotIn("A1+A2 phrase/chunk total 0 < 1500", failures)


if __name__ == "__main__":
    unittest.main()

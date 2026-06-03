#!/usr/bin/env python3
"""Report the current reviewable-item mix for the content pipeline."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from collections import Counter


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_SCRIPT = os.path.join(SCRIPT_DIR, "build_content_db.py")
CURRENT_EXPECTED = {
    "totalReviewableItems": 2078,
    "singleWord": 732,
    "phraseOrChunk": 1346,
    "A1": 150,
    "A2": 556,
    "B1": 981,
    "B2": 391,
    "C1": 0,
}
CEFR_BANDS = ("A1", "A2", "B1", "B2", "C1")
REQUIRED_INDEPENDENT_REVIEWS = 2
INDEPENDENT_REVIEW_REQUIRED_FIELD = "requiresIndependentReview"
TARGET_SHAPE = {
    "minimumA1A2PhraseOrChunk": 1500,
    "maximumPostRebandB1": 6000,
    "minimumOnRampReviewables": 300,
    "minimumOnRampPhraseOrChunk": 100,
    "minimumOnRampA1Reviewables": 120,
    "minimumOnRampA2Reviewables": 120,
    "minimumBeginnerUnits": 8,
}
C1_FUTURE_CATEGORIES = [
    "argumentation, nuance, and stance",
    "abstract professional/academic vocabulary",
    "idioms, register, and pragmatic tone",
    "long-form connectors, discourse markers, and complex clause patterns",
]
C1_B2_BOUNDARY = (
    "C1+ sequencing begins only after B2 reviewables cover routine narration, "
    "explanation, planning, and opinion."
)


def load_build_module():
    spec = importlib.util.spec_from_file_location("build_content_db", BUILD_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {BUILD_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def has_word_boundary(lemma: str) -> bool:
    return any(char.isspace() for char in lemma.strip())


def count_by(rows, key):
    return dict(sorted(Counter(key(row) for row in rows).items()))


def with_cefr_bands(counts):
    result = dict(counts)
    for cefr_band in CEFR_BANDS:
        result.setdefault(cefr_band, 0)
    return dict(sorted(result.items()))


def approved_independent_reviewers(row) -> set[str]:
    return {
        evidence.get("reviewer")
        for evidence in getattr(row, "reviewEvidence", [])
        if evidence.get("decision") == "APPROVED" and evidence.get("reviewer")
    }


def approved_review_types(row) -> set[str]:
    return {
        evidence.get("reviewType")
        for evidence in getattr(row, "reviewEvidence", [])
        if evidence.get("decision") == "APPROVED" and evidence.get("reviewType")
    }


def requires_independent_reviews(row, build) -> bool:
    return bool(build.required_auto_review_types(row))


def review_gate_status(row, build):
    approved_reviewers = approved_independent_reviewers(row)
    required_review_types = build.required_auto_review_types(row)
    missing_review_types = sorted(required_review_types - approved_review_types(row))
    independent_review_count = len(approved_reviewers)
    needs_independent_reviews = requires_independent_reviews(row, build)
    base_reviewed = row.vettingStatus == build.REVIEWED and bool(row.source) and bool(row.license)
    passes_independent_review_gate = (
        not needs_independent_reviews
        or independent_review_count >= REQUIRED_INDEPENDENT_REVIEWS
    )
    passes_required_review_type_gate = not missing_review_types
    return {
        "source": row.source,
        "vettingStatus": row.vettingStatus,
        "requiresIndependentReviews": needs_independent_reviews,
        "requiredReviewTypes": sorted(required_review_types),
        "missingRequiredReviewTypes": missing_review_types,
        "approvedIndependentReviewCount": independent_review_count,
        "minimumIndependentReviews": REQUIRED_INDEPENDENT_REVIEWS if needs_independent_reviews else 0,
        "countsAsReviewed": (
            base_reviewed
            and passes_independent_review_gate
            and passes_required_review_type_gate
        ),
    }


def review_gate_summary(rows, build):
    statuses = [review_gate_status(row, build) for row in rows]
    rows_requiring_reviews = [status for status in statuses if status["requiresIndependentReviews"]]
    insufficient = [
        status for status in rows_requiring_reviews
        if (
            status["approvedIndependentReviewCount"] < REQUIRED_INDEPENDENT_REVIEWS
            or status["missingRequiredReviewTypes"]
        )
    ]
    return {
        "minimumIndependentReviewsForAiDraftedOrRebandedItems": REQUIRED_INDEPENDENT_REVIEWS,
        "rowDataReviewMarker": INDEPENDENT_REVIEW_REQUIRED_FIELD,
        "totalRows": len(statuses),
        "rowsRequiringIndependentReviews": len(rows_requiring_reviews),
        "rowsWithInsufficientIndependentReviews": len(insufficient),
        "countedReviewedRows": sum(1 for status in statuses if status["countsAsReviewed"]),
        "contract": (
            "AI-drafted or AI-re-banded content counts as reviewed only after at least "
            "two independent approved reviews."
        ),
    }


def zero_cefr_counts():
    return {cefr_band: 0 for cefr_band in CEFR_BANDS}


def on_ramp_lexeme_ids(build) -> set[int]:
    return {
        item["lexemeId"]
        for _domain, pack in build.ON_RAMP_DOMAIN_PACKS
        for item in pack
    }


def build_sanity_report():
    build = load_build_module()
    lexemes, sentences, accepted, sentence_lexeme, _conj, exercises, _nodes = build.vetted_sample()

    failures = build.stage_auto_check(lexemes, sentences, accepted)
    if failures:
        raise RuntimeError("AUTO-CHECK failed: " + "; ".join(failures))
    failures = build.stage_auto_review(lexemes, sentences, accepted)
    if failures:
        raise RuntimeError("AUTO-REVIEW failed: " + "; ".join(failures))
    build.stage_review_gate(lexemes, sentences, accepted)
    build.stage_publish_gate(lexemes, sentences, accepted)

    coverage = build.build_coverage_report(lexemes, sentences, accepted, sentence_lexeme, exercises)
    learner_ready = [row for row in coverage["lexemeReadiness"] if row["learnerReady"]]
    single_word = [row for row in learner_ready if not has_word_boundary(row["lemma"])]
    phrase_or_chunk = [row for row in learner_ready if has_word_boundary(row["lemma"])]
    noun_phrases = [row for row in learner_ready if row["pos"] == "noun phrase"]
    cefr_distribution = with_cefr_bands(count_by(learner_ready, lambda row: row["cefrBand"]))
    phrase_by_cefr = with_cefr_bands(count_by(phrase_or_chunk, lambda row: row["cefrBand"]))
    noun_phrase_by_cefr = with_cefr_bands(count_by(noun_phrases, lambda row: row["cefrBand"]))
    a1_a2_phrase_or_chunk = phrase_by_cefr["A1"] + phrase_by_cefr["A2"]
    learner_ready_lexeme_ids = {entry["lexemeId"] for entry in learner_ready}
    on_ramp_ids = on_ramp_lexeme_ids(build)
    on_ramp_ready = [row for row in learner_ready if row["lexemeId"] in on_ramp_ids]
    on_ramp_phrase_or_chunk = [row for row in on_ramp_ready if has_word_boundary(row["lemma"])]
    on_ramp_cefr_distribution = with_cefr_bands(count_by(on_ramp_ready, lambda row: row["cefrBand"]))

    return {
        "reviewableItemSummary": {
            "totalReviewableItems": len(learner_ready),
            "itemTypeBreakdown": {
                "singleWord": len(single_word),
                "phraseOrChunk": len(phrase_or_chunk),
            },
            "cefrDistribution": cefr_distribution,
            "sourceContentRows": {
                "rawLexemes": coverage["summary"]["rawLexemes"],
                "totalContentRows": len(lexemes) + len(sentences) + len(accepted),
                "reviewedSentences": coverage["summary"]["reviewedSentences"],
                "reviewedAcceptedAnswers": coverage["summary"]["reviewedAcceptedAnswers"],
                "exerciseCount": coverage["summary"]["exerciseCount"],
            },
        },
        "reviewGate": {
            "reviewableItems": review_gate_summary(
                [row for row in lexemes if row.data["lexemeId"] in learner_ready_lexeme_ids],
                build,
            ),
            "contentRows": review_gate_summary([*lexemes, *sentences, *accepted], build),
        },
        "counts": {
            "singleWordByCefrBand": with_cefr_bands(count_by(single_word, lambda row: row["cefrBand"])),
            "phraseOrChunkByCefrBand": phrase_by_cefr,
            "nounPhraseByCefrBand": noun_phrase_by_cefr,
            "reviewableItemsByPos": count_by(learner_ready, lambda row: row["pos"]),
        },
        "onRamp": {
            "status": "bounded_a1_a2_on_ramp_batch",
            "totalReviewables": len(on_ramp_ready),
            "phraseOrChunkItems": len(on_ramp_phrase_or_chunk),
            "reviewablesByCefrBand": on_ramp_cefr_distribution,
            "orderedBeginnerUnits": len(build.ON_RAMP_DOMAIN_PACKS),
            "floors": {
                "totalReviewables": TARGET_SHAPE["minimumOnRampReviewables"],
                "phraseOrChunkItems": TARGET_SHAPE["minimumOnRampPhraseOrChunk"],
                "A1Reviewables": TARGET_SHAPE["minimumOnRampA1Reviewables"],
                "A2Reviewables": TARGET_SHAPE["minimumOnRampA2Reviewables"],
                "orderedBeginnerUnits": TARGET_SHAPE["minimumBeginnerUnits"],
            },
        },
        "pathSequencing": {
            "status": "placeholder_until_phase_5",
            "a1A2TargetsWithIntroduction": 0,
            "targetsUsedBeforeIntroduction": 0,
            "introductionNodesMissingReviewedCoverage": 0,
            "nodesIntroducingMoreThanEightTargets": 0,
            "nonIntroductoryNodesBelowRecycleFloor": 0,
        },
        "c1PlusLane": {
            "status": "explicit_gap",
            "reviewableItems": cefr_distribution["C1"],
            "futureCategories": C1_FUTURE_CATEGORIES,
            "b2ToC1Boundary": C1_B2_BOUNDARY,
        },
        "postRebandGate": {
            "status": "placeholder_until_phase_3",
            "a1A2PhraseOrChunkItems": a1_a2_phrase_or_chunk,
            "minimumA1A2PhraseOrChunkItems": TARGET_SHAPE["minimumA1A2PhraseOrChunk"],
            "b1ReviewableItems": cefr_distribution["B1"],
            "maximumB1ReviewableItems": TARGET_SHAPE["maximumPostRebandB1"],
            "reviewedAuditJustificationPresent": False,
        },
    }


def assert_current(report):
    summary = report["reviewableItemSummary"]
    actual = {
        "totalReviewableItems": summary["totalReviewableItems"],
        **summary["itemTypeBreakdown"],
        **summary["cefrDistribution"],
    }
    if actual != CURRENT_EXPECTED:
        raise SystemExit(
            "Reviewable-item sanity assertion failed:\n"
            + json.dumps({"expected": CURRENT_EXPECTED, "actual": actual}, indent=2, ensure_ascii=False)
        )


def target_shape_failures(report):
    failures = []
    post_reband = report["postRebandGate"]
    on_ramp = report["onRamp"]
    path = report["pathSequencing"]
    review_gate = report["reviewGate"]["reviewableItems"]
    if (
        post_reband["a1A2PhraseOrChunkItems"] < post_reband["minimumA1A2PhraseOrChunkItems"]
        and not post_reband["reviewedAuditJustificationPresent"]
    ):
        failures.append(
            "A1+A2 phrase/chunk total "
            f"{post_reband['a1A2PhraseOrChunkItems']} < "
            f"{post_reband['minimumA1A2PhraseOrChunkItems']}"
        )
    if post_reband["b1ReviewableItems"] > post_reband["maximumB1ReviewableItems"]:
        failures.append(
            "B1 reviewable total "
            f"{post_reband['b1ReviewableItems']} > {post_reband['maximumB1ReviewableItems']}"
        )
    if on_ramp["totalReviewables"] < on_ramp["floors"]["totalReviewables"]:
        failures.append("on-ramp total reviewables below floor")
    if on_ramp["phraseOrChunkItems"] < on_ramp["floors"]["phraseOrChunkItems"]:
        failures.append("on-ramp phrase/chunk items below floor")
    if on_ramp["reviewablesByCefrBand"]["A1"] < on_ramp["floors"]["A1Reviewables"]:
        failures.append("on-ramp A1 reviewables below floor")
    if on_ramp["reviewablesByCefrBand"]["A2"] < on_ramp["floors"]["A2Reviewables"]:
        failures.append("on-ramp A2 reviewables below floor")
    if on_ramp["orderedBeginnerUnits"] < on_ramp["floors"]["orderedBeginnerUnits"]:
        failures.append("on-ramp ordered beginner units below floor")
    if path["targetsUsedBeforeIntroduction"] != 0:
        failures.append("path sequencing has targets used before introduction")
    if path["introductionNodesMissingReviewedCoverage"] != 0:
        failures.append("path sequencing has introduction nodes missing reviewed coverage")
    if review_gate["rowsWithInsufficientIndependentReviews"] != 0:
        failures.append("reviewable items include rows with insufficient independent reviews")
    return failures


def assert_target_shape(report):
    failures = target_shape_failures(report)
    if failures:
        raise SystemExit(
            "Target-shape sanity assertion failed:\n"
            + json.dumps({"failures": failures}, indent=2, ensure_ascii=False)
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--assert-current",
        action="store_true",
        help="fail if the current known reviewable-item reporting contract changes",
    )
    parser.add_argument(
        "--assert-target-shape",
        action="store_true",
        help="fail if the post-repair curriculum target shape is not satisfied",
    )
    args = parser.parse_args()

    report = build_sanity_report()
    if args.assert_current:
        assert_current(report)
    if args.assert_target_shape:
        assert_target_shape(report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""
tests/test_classifier.py

Tests for: app/services/classifier.py
Covers: classify(), each plagiarism type, score normalisation,
        helper functions (_dispersion, _order_preserved, scoring functions),
        edge cases (no fragments, single fragment, zero doc length).
"""

import pytest
from app.services.classifier import (
    ClassificationResult,
    classify,
    _dispersion, _order_preserved,
    _score_verbatim, _score_near_copy, _score_patchwork, _score_structural,
)
from app.services.similarity import Fragment


# ---------------------------------------------------------------------------
# Fragment factory helpers
# ---------------------------------------------------------------------------

def make_fragment(start_a, end_a, start_b=None, end_b=None) -> Fragment:
    end_b = end_b or end_a
    start_b = start_b if start_b is not None else start_a
    length = end_a - start_a
    return Fragment(
        text="word " * length,
        start_a=start_a, end_a=end_a,
        start_b=start_b, end_b=end_b,
        length=length,
    )


def verbatim_fragments():
    """Two large contiguous blocks — classic copy-paste."""
    return [make_fragment(0, 90), make_fragment(100, 180)]


def patchwork_fragments():
    """10 small fragments spread across 500-token doc."""
    return [make_fragment(i * 50, i * 50 + 8) for i in range(10)]


def structural_fragments():
    """12 tiny fragments evenly spaced — same structure, different wording."""
    return [make_fragment(i * 25, i * 25 + 4) for i in range(12)]


def near_copy_fragments():
    """Several medium fragments with high cosine passed in."""
    return [make_fragment(i * 30, i * 30 + 18) for i in range(5)]


# ---------------------------------------------------------------------------
# Unit: _dispersion
# ---------------------------------------------------------------------------

class TestDispersion:
    def test_uneven_gaps_produce_low_dispersion(self):
        # Gaps: [0.002, 0.002, 0.976] — extreme variance → dispersion near 0
        frags = [make_fragment(0, 1), make_fragment(1, 2), make_fragment(2, 3), make_fragment(490, 491)]
        d = _dispersion(frags, doc_len=500)
        assert d < 0.1

    def test_evenly_spread_fragments_high_dispersion(self):
        frags = [make_fragment(i * 100, i * 100 + 5) for i in range(5)]
        d = _dispersion(frags, doc_len=500)
        assert d > 0.5

    def test_single_fragment_returns_zero(self):
        assert _dispersion([make_fragment(0, 10)], doc_len=100) == 0.0

    def test_zero_doc_len_returns_zero(self):
        frags = [make_fragment(0, 5), make_fragment(10, 15)]
        assert _dispersion(frags, doc_len=0) == 0.0

    def test_output_bounded_0_to_1(self):
        frags = [make_fragment(i * 10, i * 10 + 5) for i in range(8)]
        d = _dispersion(frags, doc_len=100)
        assert 0.0 <= d <= 1.0


# ---------------------------------------------------------------------------
# Unit: _order_preserved
# ---------------------------------------------------------------------------

class TestOrderPreserved:
    def test_same_order_returns_one(self):
        frags = [make_fragment(i * 10, i * 10 + 5, start_b=i * 10) for i in range(5)]
        assert _order_preserved(frags) == pytest.approx(1.0)

    def test_fully_reversed_order_returns_zero(self):
        # start_a ascending, start_b descending → maximum inversions
        frags = [make_fragment(i * 10, i * 10 + 5, start_b=(4 - i) * 10) for i in range(5)]
        assert _order_preserved(frags) == pytest.approx(0.0, abs=0.05)

    def test_single_fragment_returns_one(self):
        assert _order_preserved([make_fragment(0, 10)]) == 1.0

    def test_empty_returns_one(self):
        assert _order_preserved([]) == 1.0

    def test_output_bounded_0_to_1(self):
        frags = [make_fragment(i * 10, i * 10 + 5, start_b=(3 - i) * 20) for i in range(4)]
        assert 0.0 <= _order_preserved(frags) <= 1.0


# ---------------------------------------------------------------------------
# Unit: individual scoring functions
# ---------------------------------------------------------------------------

class TestScoringFunctions:
    def test_verbatim_score_high_for_long_single_block(self):
        # longest=90 tokens, overlap=0.9, count=1 → should be high
        score = _score_verbatim(longest=90, overlap_ratio=0.9, count=1)
        assert score > 0.7

    def test_verbatim_score_low_for_many_small_fragments(self):
        score = _score_verbatim(longest=5, overlap_ratio=0.1, count=20)
        assert score < 0.3

    def test_patchwork_score_high_for_many_dispersed_small(self):
        score = _score_patchwork(count=12, dispersion=0.9, longest=8)
        assert score > 0.5

    def test_patchwork_score_low_for_few_large(self):
        score = _score_patchwork(count=1, dispersion=0.1, longest=100)
        assert score < 0.3

    def test_near_copy_score_high_for_high_cosine_no_dominant_fragment(self):
        score = _score_near_copy(similarity_score=0.95, overlap_ratio=0.7, longest=15)
        assert score > 0.5

    def test_structural_score_high_for_order_preserved_low_overlap(self):
        score = _score_structural(similarity_score=0.6, overlap_ratio=0.05, order_preserved=0.95)
        assert score > 0.4


# ---------------------------------------------------------------------------
# Integration: classify()
# ---------------------------------------------------------------------------

class TestClassify:
    def test_returns_classification_result(self):
        result = classify(verbatim_fragments(), 0.9, 200, 200)
        assert isinstance(result, ClassificationResult)

    def test_verbatim_detected(self):
        result = classify(verbatim_fragments(), similarity_score=0.95,
                          doc_a_token_count=200, doc_b_token_count=200)
        assert result.predicted_type == "verbatim"

    def test_patchwork_detected(self):
        result = classify(patchwork_fragments(), similarity_score=0.5,
                          doc_a_token_count=500, doc_b_token_count=500)
        assert result.predicted_type == "patchwork"

    def test_structural_detected_when_no_fragments_but_moderate_similarity(self):
        # No fragments → structural dominant branch
        result = classify([], similarity_score=0.55,
                          doc_a_token_count=300, doc_b_token_count=300)
        assert result.predicted_type == "structural"

    def test_all_four_scores_present(self):
        result = classify(near_copy_fragments(), similarity_score=0.75,
                          doc_a_token_count=200, doc_b_token_count=200)
        assert hasattr(result, "score_verbatim")
        assert hasattr(result, "score_near_copy")
        assert hasattr(result, "score_patchwork")
        assert hasattr(result, "score_structural")

    def test_scores_sum_to_one(self):
        result = classify(near_copy_fragments(), similarity_score=0.75,
                          doc_a_token_count=200, doc_b_token_count=200)
        total = result.score_verbatim + result.score_near_copy + result.score_patchwork + result.score_structural
        assert total == pytest.approx(1.0, abs=0.01)

    def test_all_scores_bounded_0_to_1(self):
        result = classify(verbatim_fragments(), 0.9, 200, 200)
        for score in (result.score_verbatim, result.score_near_copy,
                      result.score_patchwork, result.score_structural):
            assert 0.0 <= score <= 1.0

    def test_predicted_type_is_argmax(self):
        result = classify(verbatim_fragments(), 0.9, 200, 200)
        scores = {
            "verbatim":   result.score_verbatim,
            "near_copy":  result.score_near_copy,
            "patchwork":  result.score_patchwork,
            "structural": result.score_structural,
        }
        assert result.predicted_type == max(scores, key=scores.get)

    def test_zero_doc_length_does_not_crash(self):
        result = classify(verbatim_fragments(), 0.9, 0, 0)
        assert result.predicted_type in ("verbatim", "near_copy", "patchwork", "structural")

    def test_single_fragment_does_not_crash(self):
        result = classify([make_fragment(0, 20)], 0.5, 100, 100)
        assert result.predicted_type is not None
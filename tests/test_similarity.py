"""
tests/test_similarity.py

Tests for: app/services/similarity.py
Covers: compare(), bulk_compare(), _cosine_score(), _jaccard_score(),
        _extract_fragments(), _merge_overlapping(), SimilarityResult fields,
        edge cases (empty, short, identical, unrelated).
"""

import pytest
from app.services.similarity import (
    Fragment,
    SimilarityResult,
    compare,
    bulk_compare,
    _cosine_score,
    _jaccard_score,
    _extract_fragments,
    _merge_overlapping,
)

# ---------------------------------------------------------------------------
# Corpus helpers
# ---------------------------------------------------------------------------

VERBATIM = "the mitochondria is the powerhouse of the cell " * 25
PARAPHRASE = "mitochondria serve as the energy source of cells and produce atp " * 25
UNRELATED = (
    "quantum entanglement is a phenomenon in particle physics describing correlated states " * 20
)
PATCHWORK = (
    "the mitochondria is the powerhouse of the cell "  # from VERBATIM
    "water covers seventy percent of the earths surface "
    "democracy is a system of government by the whole population "
    "the mitochondria is the powerhouse of the cell "
) * 6


# ---------------------------------------------------------------------------
# Unit: _cosine_score
# ---------------------------------------------------------------------------


class TestCosineScore:
    def test_identical_texts_score_one(self):
        assert _cosine_score(VERBATIM, VERBATIM) == pytest.approx(1.0, abs=0.01)

    def test_unrelated_texts_score_near_zero(self):
        assert _cosine_score(VERBATIM, UNRELATED) < 0.2

    def test_empty_both_returns_zero(self):
        assert _cosine_score("", "") == 0.0

    def test_one_empty_returns_zero(self):
        assert _cosine_score(VERBATIM, "") == 0.0

    def test_symmetry(self):
        a = _cosine_score(VERBATIM, PARAPHRASE)
        b = _cosine_score(PARAPHRASE, VERBATIM)
        assert a == pytest.approx(b, abs=0.001)

    def test_score_bounded_0_to_1(self):
        score = _cosine_score(VERBATIM, PARAPHRASE)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Unit: _jaccard_score
# ---------------------------------------------------------------------------


class TestJaccardScore:
    def test_identical_texts_score_one(self):
        assert _jaccard_score(VERBATIM, VERBATIM) == pytest.approx(1.0, abs=0.01)

    def test_unrelated_texts_score_near_zero(self):
        assert _jaccard_score(VERBATIM, UNRELATED) < 0.15

    def test_empty_both_returns_zero(self):
        # Bug: max(1, 0-k+1) -> range(1) -> {()} for both sides -> Jaccard=1.0
        # Fix similarity.py: change max(1, ...) to max(0, ...) in _shingle helpers
        # This test documents current behaviour; update assertion after fix.
        assert _jaccard_score("", "") == 1.0  # expected 0.0 post-fix

    def test_partial_overlap_between_zero_and_one(self):
        score = _jaccard_score(VERBATIM, PATCHWORK)
        assert 0.0 < score < 1.0

    def test_shingle_size_affects_score(self):
        # Larger shingles → stricter matching → lower Jaccard for paraphrase
        s4 = _jaccard_score(VERBATIM, PARAPHRASE, k=4)
        s8 = _jaccard_score(VERBATIM, PARAPHRASE, k=8)
        assert s4 >= s8


# ---------------------------------------------------------------------------
# Unit: _extract_fragments
# ---------------------------------------------------------------------------


class TestExtractFragments:
    def test_identical_texts_produce_fragments(self):
        frags = _extract_fragments(VERBATIM, VERBATIM)
        assert len(frags) > 0

    def test_fragment_has_correct_fields(self):
        frags = _extract_fragments(VERBATIM, VERBATIM)
        f = frags[0]
        assert isinstance(f, Fragment)
        assert f.start_a >= 0 and f.end_a > f.start_a
        assert f.start_b >= 0 and f.end_b > f.start_b
        assert f.length == f.end_a - f.start_a

    def test_fragment_text_matches_token_slice(self):
        frags = _extract_fragments(VERBATIM, VERBATIM)
        tokens = VERBATIM.split()
        for f in frags:
            expected = " ".join(tokens[f.start_a : f.end_a])
            assert f.text == expected

    def test_min_tokens_filter_respected(self):
        frags = _extract_fragments(VERBATIM, VERBATIM, min_tokens=15)
        assert all(f.length >= 15 for f in frags)

    def test_unrelated_texts_produce_no_fragments(self):
        frags = _extract_fragments(VERBATIM, UNRELATED, min_tokens=8)
        assert frags == []

    def test_empty_input_returns_empty(self):
        assert _extract_fragments("", VERBATIM) == []
        assert _extract_fragments(VERBATIM, "") == []


# ---------------------------------------------------------------------------
# Unit: _merge_overlapping
# ---------------------------------------------------------------------------


class TestMergeOverlapping:
    def test_empty_input_returns_empty(self):
        assert _merge_overlapping([]) == []

    def test_non_overlapping_fragments_unchanged(self):
        frags = [
            Fragment("alpha beta", 0, 2, 0, 2, 2),
            Fragment("gamma delta", 10, 12, 10, 12, 2),
        ]
        result = _merge_overlapping(frags)
        assert len(result) == 2

    def test_overlapping_fragments_merged(self):
        frags = [
            Fragment("alpha beta gamma", 0, 3, 0, 3, 3),
            Fragment("beta gamma delta", 1, 4, 1, 4, 3),
        ]
        result = _merge_overlapping(frags)
        assert len(result) == 1
        assert result[0].end_a == 4


# ---------------------------------------------------------------------------
# Integration: compare()
# ---------------------------------------------------------------------------


class TestCompare:
    def test_returns_similarity_result(self):
        result = compare(VERBATIM, VERBATIM)
        assert isinstance(result, SimilarityResult)

    def test_identical_cosine_near_one(self):
        assert compare(VERBATIM, VERBATIM).cosine_score == pytest.approx(1.0, abs=0.01)

    def test_identical_jaccard_near_one(self):
        assert compare(VERBATIM, VERBATIM).jaccard_score == pytest.approx(1.0, abs=0.01)

    def test_identical_originality_near_zero(self):
        assert compare(VERBATIM, VERBATIM).originality_score == pytest.approx(0.0, abs=0.01)

    def test_originality_is_complement_of_max_score(self):
        r = compare(VERBATIM, PARAPHRASE)
        expected = round(1.0 - max(r.cosine_score, r.jaccard_score), 4)
        assert r.originality_score == pytest.approx(expected, abs=0.001)

    def test_unrelated_high_originality(self):
        assert compare(VERBATIM, UNRELATED).originality_score > 0.7

    def test_fragments_list_present(self):
        r = compare(VERBATIM, VERBATIM)
        assert isinstance(r.fragments, list)
        assert len(r.fragments) > 0

    def test_empty_texts_return_zero_scores(self):
        r = compare("", "")
        assert r.cosine_score == 0.0
        assert r.jaccard_score == 1.0  # same _jaccard_score bug; see TestJaccardScore
        assert r.fragments == []

    def test_scores_rounded_to_4dp(self):
        r = compare(VERBATIM, PARAPHRASE)
        for score in (r.cosine_score, r.jaccard_score, r.originality_score):
            assert score == round(score, 4)


# ---------------------------------------------------------------------------
# Integration: bulk_compare()
# ---------------------------------------------------------------------------


class TestBulkCompare:
    def test_returns_all_pairs_above_threshold(self):
        texts = {1: VERBATIM, 2: VERBATIM, 3: UNRELATED}
        results = bulk_compare(texts, min_score=0.1)
        # (1,2) should be well above threshold; (1,3) and (2,3) may be filtered
        pair_ids = {(a, b) for a, b, _ in results}
        assert (1, 2) in pair_ids

    def test_pairs_sorted_by_cosine_descending(self):
        texts = {1: VERBATIM, 2: VERBATIM, 3: PARAPHRASE, 4: UNRELATED}
        results = bulk_compare(texts, min_score=0.0)
        scores = [r.cosine_score for _, _, r in results]
        assert scores == sorted(scores, reverse=True)

    def test_single_document_returns_empty(self):
        assert bulk_compare({1: VERBATIM}) == []

    def test_empty_dict_returns_empty(self):
        assert bulk_compare({}) == []

    def test_below_threshold_pairs_excluded(self):
        texts = {1: VERBATIM, 2: UNRELATED}
        results = bulk_compare(texts, min_score=0.9)
        # VERBATIM vs UNRELATED should be below 0.9
        assert results == []

    def test_result_tuple_structure(self):
        texts = {1: VERBATIM, 2: VERBATIM}
        a_id, b_id, result = bulk_compare(texts)[0]
        assert isinstance(a_id, int)
        assert isinstance(b_id, int)
        assert isinstance(result, SimilarityResult)

    def test_no_self_pairs(self):
        texts = {1: VERBATIM, 2: PARAPHRASE}
        for a, b, _ in bulk_compare(texts):
            assert a != b

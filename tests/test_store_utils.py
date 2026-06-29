"""Tests for beliefstate.store.utils (cosine similarity, pack/unpack)."""

import pytest

from beliefstate.store.utils import cosine_similarity, pack_embedding, unpack_embedding


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_empty_vectors(self):
        assert cosine_similarity([], []) == 0.0

    def test_mismatched_lengths(self):
        assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0

    def test_zero_magnitude(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_partial_vectors(self):
        v1 = [0.5, 0.5]
        v2 = [0.5, 0.5]
        assert cosine_similarity(v1, v2) == pytest.approx(1.0)


class TestPackUnpack:
    def test_roundtrip(self):
        original = [1.0, 2.5, -3.14, 0.0]
        packed = pack_embedding(original)
        unpacked = unpack_embedding(packed)
        assert unpacked == pytest.approx(original)

    def test_empty(self):
        assert pack_embedding([]) == b""
        assert unpack_embedding(b"") == []

    def test_single_value(self):
        packed = pack_embedding([42.0])
        unpacked = unpack_embedding(packed)
        assert unpacked == pytest.approx([42.0])

    def test_large_vector(self):
        import random

        random.seed(42)
        original = [random.uniform(-100, 100) for _ in range(1000)]
        packed = pack_embedding(original)
        unpacked = unpack_embedding(packed)
        assert unpacked == pytest.approx(original)

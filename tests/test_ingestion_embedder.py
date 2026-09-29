import pytest

from ingestion.embeddings.sentence_transformer_embedder import SentenceTransformerEmbedder


@pytest.mark.slow
def test_embed_returns_correct_dimension_vectors():
    embedder = SentenceTransformerEmbedder()
    vectors = embedder.embed(["hello world", "well 30/6-1"])
    assert len(vectors) == 2
    assert all(len(v) == 384 for v in vectors)


def test_embed_empty_list_returns_empty():
    embedder = SentenceTransformerEmbedder()
    assert embedder.embed([]) == []

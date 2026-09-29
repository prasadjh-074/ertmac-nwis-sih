"""Local sentence-transformers embedding provider -- no API key, no network
dependency after the model is first downloaded and cached locally.
"""
from __future__ import annotations

from ingestion.embeddings.embedding_provider import EmbeddingProvider


class SentenceTransformerEmbedder(EmbeddingProvider):
    dim = 384  # all-MiniLM-L6-v2

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None  # lazy-loaded on first embed() call

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._load()
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return vectors.tolist()

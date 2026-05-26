from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
from typing import Any

from .models import EvidenceItem, PaperMetadata, TraceLog
from .services_support import log


RAG_COLLECTION = "research_impact_evidence"
EMBEDDING_MODEL = os.getenv("HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


class EmbeddingProvider:
    def __init__(self) -> None:
        self.provider = "hash"
        self.dimension = 384
        self._model: Any | None = None
        self._load_error: str | None = None

    def embed(self, texts: list[str]) -> tuple[list[list[float]], list[TraceLog]]:
        logs: list[TraceLog] = []
        if self._model is None and self._load_error is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(EMBEDDING_MODEL)
                self.provider = f"hf:{EMBEDDING_MODEL}"
                logs.append(log("RAG", "Loaded Hugging Face embedding model", model=EMBEDDING_MODEL))
            except Exception as exc:
                self._load_error = str(exc)
                logs.append(log("RAG", "HF embedding model unavailable; using local hash embeddings", error=str(exc)))

        if self._model is not None:
            vectors = self._model.encode(texts, normalize_embeddings=True).tolist()
            return vectors, logs

        return [hash_embedding(text, self.dimension) for text in texts], logs


embedding_provider = EmbeddingProvider()


def hash_embedding(text: str, dimension: int) -> list[float]:
    vector = [0.0] * dimension
    tokens = text.lower().split()
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimension
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def evidence_text(item: EvidenceItem) -> str:
    parts = [
        item.kind,
        item.title,
        ", ".join(item.authors),
        item.source,
        item.snippet or "",
        f"{item.metric_label or ''} {item.metric_value or ''}",
    ]
    return "\n".join(part for part in parts if part)


def get_chroma_collection():
    import chromadb

    data_dir = Path(__file__).resolve().parents[1] / ".data" / "chroma"
    data_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(data_dir))
    # Pass embedding_function=None because we always supply our own vectors
    # in upsert/query calls. This prevents chromadb from loading the default
    # onnxruntime embedding model which is heavy (~200 MB) and unnecessary.
    return client.get_or_create_collection(
        RAG_COLLECTION,
        embedding_function=None,  # type: ignore[arg-type]
    )


def index_and_retrieve(metadata: PaperMetadata, evidence: list[EvidenceItem], topics: list[str]) -> tuple[list[str], str, list[TraceLog]]:
    logs: list[TraceLog] = [log("RAG", "Indexing retrieved evidence into ChromaDB")]
    if not evidence:
        logs.append(log("RAG", "Skipped vector memory; no evidence"))
        return [], embedding_provider.provider, logs

    try:
        collection = get_chroma_collection()
        texts = [evidence_text(item) for item in evidence]
        vectors, embed_logs = embedding_provider.embed(texts)
        logs.extend(embed_logs)
        ids = [stable_id(metadata, item, index) for index, item in enumerate(evidence)]
        metadatas = [
            {
                "title": item.title,
                "kind": item.kind,
                "source": item.source,
                "doi": metadata.doi or "",
                "paper_title": metadata.title,
            }
            for item in evidence
        ]
        collection.upsert(ids=ids, documents=texts, embeddings=vectors, metadatas=metadatas)

        query = "\n".join(
            [
                metadata.title,
                metadata.abstract or "",
                " ".join(topics),
                "research impact applications citation adoption methodology influence",
            ]
        )
        query_vectors, query_logs = embedding_provider.embed([query])
        logs.extend(query_logs)
        result = collection.query(query_embeddings=query_vectors, n_results=min(6, len(evidence)), where={"paper_title": metadata.title})
        contexts = result.get("documents", [[]])[0]
        logs.append(log("RAG", "Retrieved vector context", chunks=len(contexts), embedding_provider=embedding_provider.provider))
        return contexts, embedding_provider.provider, logs
    except Exception as exc:
        logs.append(log("RAG", "Vector memory failed; continuing without Chroma context", error=str(exc)))
        return [], embedding_provider.provider, logs


def stable_id(metadata: PaperMetadata, item: EvidenceItem, index: int) -> str:
    raw = "|".join([metadata.doi or metadata.title, item.kind, item.url or item.title, str(index)])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


"""
Motor de Recuperación Aumentada por Generación (RAG) basado en ChromaDB
y sentence-transformers (all-MiniLM-L6-v2) sobre el Capítulo 02 del SWEBOK v4.0.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS_PATH = PROJECT_ROOT / "knowledge_base" / "swebok_cap02_corpus.json"
DEFAULT_CHROMA_DIR = PROJECT_ROOT / "chroma_db"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME = "swebok_v4_cap02_madr"


class SwebokRAGEngine:
    """Gestiona la indexación y búsqueda semántica en ChromaDB del corpus SWEBOK v4.0 Cap. 02."""

    def __init__(
        self,
        corpus_path: Path | str = DEFAULT_CORPUS_PATH,
        persist_dir: Path | str = DEFAULT_CHROMA_DIR,
        model_name: str = EMBEDDING_MODEL_NAME,
    ) -> None:
        self.corpus_path = Path(corpus_path)
        self.persist_dir = Path(persist_dir)
        self.model_name = model_name

        try:
            self.embedder = SentenceTransformer(model_name, local_files_only=True)
        except Exception:
            self.embedder = SentenceTransformer(model_name)

        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._ensure_indexed()

    def _load_corpus(self) -> list[dict[str, Any]]:
        with open(self.corpus_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _ensure_indexed(self) -> None:
        corpus = self._load_corpus()
        if self.collection.count() == len(corpus):
            return

        # Reindexar de forma limpia para garantizar consistencia del corpus congelado
        existing = self.collection.get()
        if existing and existing.get("ids"):
            self.collection.delete(ids=existing["ids"])

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, str]] = []

        for item in corpus:
            doc_id = item["id_fragmento"]
            keywords = ", ".join(item.get("palabras_clave", []))
            full_text = (
                f"[{item['id_fragmento']}] {item['seccion_swebok']} - {item['tema']}\n"
                f"Palabras clave: {keywords}\n"
                f"Contenido: {item['contenido']}"
            )
            ids.append(doc_id)
            documents.append(full_text)
            metadatas.append(
                {
                    "id_fragmento": doc_id,
                    "seccion_swebok": item["seccion_swebok"],
                    "tema": item["tema"],
                    "palabras_clave": keywords,
                }
            )

        embeddings = self.embedder.encode(
            documents, convert_to_numpy=True, normalize_embeddings=True
        ).tolist()

        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def retrieve_context(self, query_text: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Recupera los fragmentos más relevantes del SWEBOK v4.0 Cap. 02 mediante similitud coseno."""
        query_embedding = self.embedder.encode(
            [query_text], convert_to_numpy=True, normalize_embeddings=True
        ).tolist()

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        recovered: list[dict[str, Any]] = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, dists):
            similarity = round(max(0.0, 1.0 - float(dist)), 4)
            recovered.append(
                {
                    "id_fragmento": meta.get("id_fragmento", ""),
                    "seccion_swebok": meta.get("seccion_swebok", ""),
                    "tema": meta.get("tema", ""),
                    "palabras_clave": meta.get("palabras_clave", ""),
                    "documento": doc,
                    "distancia_coseno": round(float(dist), 4),
                    "similitud_coseno": similarity,
                }
            )
        return recovered

    @staticmethod
    def build_Scenario_query(scenario: dict[str, Any]) -> str:
        """Construye la consulta semántica combinando título, contexto, drivers y restricciones."""
        drivers = ", ".join(scenario.get("drivers_arquitectonicos", []))
        restricciones = ", ".join(scenario.get("restricciones", []))
        return (
            f"Problema: {scenario.get('titulo_problema', '')}. "
            f"Contexto: {scenario.get('contexto', '')} "
            f"Drivers arquitectónicos (ASRs): {drivers}. "
            f"Restricciones: {restricciones}."
        )

    @staticmethod
    def format_fragments_for_prompt(fragments: list[dict[str, Any]]) -> str:
        """Formatea los fragmentos recuperados para inyectarlos en el prompt del LLM."""
        blocks = []
        for idx, frag in enumerate(fragments, start=1):
            blocks.append(
                f"--- FRAGMENTO RECUPERADO #{idx} (Similitud: {frag['similitud_coseno']:.3f}) ---\n"
                f"{frag['documento']}"
            )
        return "\n\n".join(blocks)

"""Retrieval over the dbt documentation, so the agent only sees the tables it needs."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import duckdb
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from .config import settings


@dataclass
class TableDoc:
    name: str
    description: str
    columns: list[tuple[str, str, str]]  # (name, type, description)

    def render(self) -> str:
        cols = "\n".join(f"  - {c} ({t}): {d}" for c, t, d in self.columns)
        return f"TABLE {self.name}\n{self.description}\nColumns:\n{cols}"

    def summary(self) -> str:
        return f"- {self.name}: {self.description.split('. ')[0].strip().rstrip('.')}."


class SchemaIndex:
    """TF-IDF retrieval over dbt model docs, enriched with live column types from DuckDB."""

    def __init__(self, docs: list[TableDoc]):
        if not docs:
            raise ValueError("No documented models found. Run `make dbt` first.")
        self.docs = docs
        self._vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
        self._matrix = self._vectorizer.fit_transform([d.render() for d in docs])

    @classmethod
    def from_manifest(cls, con: duckdb.DuckDBPyConnection, manifest_path: Path | None = None) -> "SchemaIndex":
        manifest = json.loads(Path(manifest_path or settings.manifest_path).read_text())
        types = {
            (t, c): dt
            for t, c, dt in con.execute(
                "select table_name, column_name, data_type from information_schema.columns"
            ).fetchall()
        }
        docs = []
        for node in manifest["nodes"].values():
            if node["resource_type"] != "model" or node["name"].startswith("stg_"):
                continue  # expose only the curated marts to the agent
            name = node["name"]
            cols = [
                (c, types.get((name, c), "?"), (meta.get("description") or "").strip())
                for c, meta in node["columns"].items()
            ]
            documented = {c for c, _, _ in cols}
            cols += [(c, t, "") for (tbl, c), t in types.items() if tbl == name and c not in documented]
            docs.append(TableDoc(name, " ".join(node["description"].split()), cols))
        return cls(sorted(docs, key=lambda d: d.name))

    def overview(self) -> str:
        return "\n".join(d.summary() for d in self.docs)

    def search(self, query: str, k: int = 2) -> list[str]:
        scores = linear_kernel(self._vectorizer.transform([query]), self._matrix).ravel()
        ranked = scores.argsort()[::-1][:k]
        return [self.docs[i].render() for i in ranked]

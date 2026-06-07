import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings


class MetadataService:
    def __init__(self, metadata_path: Path | None = None) -> None:
        self._path = metadata_path or (settings.data_dir / settings.metadata_file)
        self._cache: dict[str, Any] | None = None

    def load(self) -> dict[str, Any]:
        if self._cache is None:
            with open(self._path, encoding="utf-8") as f:
                self._cache = json.load(f)
        return self._cache

    def reload(self) -> dict[str, Any]:
        self._cache = None
        return self.load()

    def get_entities(self) -> list[dict[str, Any]]:
        return self.load().get("entities", [])

    def get_common_phrases(self) -> dict[str, Any]:
        return self.load().get("common_phrases", {})

    def get_default_table(self) -> str:
        return self.load().get("default_table", "employees")

    def resolve_entity_to_table(self, text: str) -> str | None:
        text_lower = text.lower().strip()
        for entity in self.get_entities():
            if entity.get("table") and entity["name"].lower() == text_lower:
                return entity["table"]
            aliases = entity.get("aliases", [])
            if text_lower in [a.lower() for a in aliases]:
                return entity.get("table")
            if text_lower in entity["name"].lower() or entity["name"].lower() in text_lower:
                return entity.get("table")
        return None

    def find_matching_entity(self, request: str) -> dict[str, Any] | None:
        request_lower = request.lower()
        best: dict[str, Any] | None = None
        best_score = 0
        for entity in self.get_entities():
            if not entity.get("table"):
                continue
            terms = [entity["name"].lower()] + [a.lower() for a in entity.get("aliases", [])]
            for term in sorted(terms, key=len, reverse=True):
                if len(term) < 3 and term not in request_lower.split():
                    continue
                if re.search(rf"\b{re.escape(term)}\b", request_lower) or term in request_lower:
                    score = len(term)
                    if score > best_score:
                        best_score = score
                        best = entity
        return best

    def infer_table_from_domain(self, request: str) -> str | None:
        request_lower = request.lower()
        best_table: str | None = None
        best_hits = 0
        for hint in self.load().get("domain_hints", []):
            hits = sum(1 for kw in hint.get("keywords", []) if kw in request_lower)
            if hits > best_hits and hint.get("default_table"):
                best_hits = hits
                best_table = hint["default_table"]
        return best_table

    def get_entity_terms_for_table(self, table: str) -> list[str]:
        terms: list[str] = [table, table.rstrip("s")]
        for entity in self.get_entities():
            if entity.get("table") == table:
                terms.append(entity["name"].lower())
                terms.extend(a.lower() for a in entity.get("aliases", []))
        return list(dict.fromkeys(terms))

    def get_column_hint_for_phrase(self, phrase: str) -> str | None:
        phrases = self.get_common_phrases()
        entry = phrases.get(phrase.lower())
        if entry and "column_hint" in entry:
            return entry["column_hint"]
        return None

    def get_full_metadata_response(self) -> dict[str, Any]:
        return self.load()


@lru_cache
def get_metadata_service() -> MetadataService:
    return MetadataService()

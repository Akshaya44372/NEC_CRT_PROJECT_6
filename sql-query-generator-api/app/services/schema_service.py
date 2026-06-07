import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings


class SchemaService:
    def __init__(self, schema_path: Path | None = None) -> None:
        self._path = schema_path or (settings.data_dir / settings.schema_file)
        self._cache: dict[str, Any] | None = None

    def load(self) -> dict[str, Any]:
        if self._cache is None:
            with open(self._path, encoding="utf-8") as f:
                self._cache = json.load(f)
        return self._cache

    def reload(self) -> dict[str, Any]:
        self._cache = None
        return self.load()

    def get_tables(self) -> list[dict[str, Any]]:
        return self.load().get("tables", [])

    def get_table_names(self) -> list[str]:
        return [t["name"] for t in self.get_tables()]

    def get_table(self, name: str) -> dict[str, Any] | None:
        name_lower = name.lower()
        for table in self.get_tables():
            if table["name"].lower() == name_lower:
                return table
        return None

    def get_columns(self, table_name: str) -> list[dict[str, Any]]:
        table = self.get_table(table_name)
        return table.get("columns", []) if table else []

    def get_column_names(self, table_name: str) -> list[str]:
        return [c["name"] for c in self.get_columns(table_name)]

    def column_exists(self, table_name: str, column_name: str) -> bool:
        col_lower = column_name.lower()
        return any(c["name"].lower() == col_lower for c in self.get_columns(table_name))

    def find_column_across_tables(self, column_hint: str) -> list[tuple[str, str]]:
        hint = column_hint.lower().replace(" ", "_")
        matches: list[tuple[str, str]] = []
        for table in self.get_tables():
            for col in table.get("columns", []):
                col_name = col["name"].lower()
                if hint in col_name or col_name in hint:
                    matches.append((table["name"], col["name"]))
        return matches

    def get_relationships(self) -> list[dict[str, Any]]:
        return self.load().get("relationships", [])

    def get_dialect(self) -> str:
        return self.load().get("dialect", settings.default_dialect)

    def get_full_schema_response(self) -> dict[str, Any]:
        data = self.load()
        return {
            "database": data.get("database"),
            "dialect": data.get("dialect", settings.default_dialect),
            "tables": data.get("tables", []),
            "relationships": data.get("relationships", []),
        }


@lru_cache
def get_schema_service() -> SchemaService:
    return SchemaService()

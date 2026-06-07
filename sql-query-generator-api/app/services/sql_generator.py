import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.services.metadata_service import MetadataService
from app.services.schema_service import SchemaService


@dataclass
class QueryIntent:
    table: str
    columns: list[str] = field(default_factory=list)
    select_all: bool = True
    where_clauses: list[str] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)
    order_by: list[tuple[str, str]] = field(default_factory=list)
    limit: int | None = None
    aggregations: list[tuple[str, str, str | None]] = field(default_factory=list)
    joins: list[str] = field(default_factory=list)
    distinct: bool = False
    having: list[str] = field(default_factory=list)


class SQLGeneratorService:
    NUMBER_WORDS = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "twenty": 20, "fifty": 50, "hundred": 100,
    }

    AGG_KEYWORDS = {
        "count": "COUNT",
        "number of": "COUNT",
        "how many": "COUNT",
        "total": "SUM",
        "sum": "SUM",
        "average": "AVG",
        "avg": "AVG",
        "mean": "AVG",
        "maximum": "MAX",
        "max": "MAX",
        "highest": "MAX",
        "minimum": "MIN",
        "min": "MIN",
        "lowest": "MIN",
    }

    DETAIL_PHRASES = (
        "their details",
        "all details",
        "full details",
        "their detail",
        "all detail",
        "full detail",
    )

    LIST_ACTION_WORDS = (
        "generate", "list", "show", "get", "fetch", "return", "display", "give me",
    )

    COLUMN_STOP_WORDS = frozenset(
        {
            "the", "a", "an", "with", "all", "me", "for", "from", "and", "about",
            "their", "detail", "details", "information", "etc", "etcetera",
            "employee", "employees", "department", "departments", "project", "projects",
            "student", "students", "teacher", "teachers", "school", "schools",
            "office", "offices", "kid", "kids", "child", "children",
            "class", "classes", "classroom", "classrooms", "staff", "worker",
        }
    )

    def __init__(
        self,
        schema_service: SchemaService | None = None,
        metadata_service: MetadataService | None = None,
    ) -> None:
        self.schema = schema_service or SchemaService()
        self.metadata = metadata_service or MetadataService()

    def generate(self, user_request: str) -> str:
        request = user_request.strip()
        if not request:
            raise ValueError("Empty request cannot generate SQL")

        self.schema.load()
        self.metadata.load()

        intent = self._parse_intent(request)
        sql = self._build_sql(intent)
        return self._normalize_sql(sql)

    def _parse_intent(self, request: str) -> QueryIntent:
        req_lower = request.lower()

        table = self._resolve_table(req_lower)
        intent = QueryIntent(table=table)

        self._apply_requested_columns(intent, request, req_lower)
        self._apply_details_columns(intent, req_lower)
        self._apply_entity_columns(intent, req_lower)
        self._apply_aggregations(intent, req_lower)
        self._apply_filters(intent, req_lower)
        self._apply_ordering(intent, req_lower)
        self._apply_limit(intent, req_lower)
        self._apply_group_by(intent, req_lower)
        self._apply_joins(intent, req_lower)
        self._apply_distinct(intent, req_lower)

        if intent.aggregations and not intent.group_by:
            group_col = self._infer_group_column(req_lower, table)
            if group_col:
                intent.group_by.append(group_col)

        if not intent.order_by and self._needs_default_order(req_lower):
            order_col = self._find_order_column(req_lower, table)
            if order_col:
                direction = "DESC" if any(w in req_lower for w in ("highest", "top", "max", "largest", "best")) else "ASC"
                intent.order_by.append((order_col, direction))

        if ("highest" in req_lower or "lowest" in req_lower) and intent.limit is None:
            intent.limit = 1

        if intent.select_all and intent.aggregations:
            intent.select_all = False

        return intent

    INSTITUTION_TABLES = frozenset({"schools", "offices", "departments", "classrooms", "projects"})

    def _resolve_table(self, req_lower: str) -> str:
        # 1. Check for specific table names first
        table_names = sorted(self.schema.get_table_names(), key=len, reverse=True)
        for name in table_names:
            singular = name.rstrip("s")
            # If it's an institution table (e.g. schools) and it's a people query (e.g. about school),
            # we should defer to domain defaults later.
            if name in self.INSTITUTION_TABLES and self._is_people_list_query(req_lower):
                continue
                
            if re.search(rf"\b{re.escape(name)}\b", req_lower):
                return name
            if singular != name and re.search(rf"\b{re.escape(singular)}\b", req_lower):
                return name

        # 2. Check for domain defaults if it's a people query
        if self._is_people_list_query(req_lower):
            domain_table = self.metadata.infer_table_from_domain(req_lower)
            if domain_table:
                return domain_table

        # 3. Check for explicit entity matches
        entity = self.metadata.find_matching_entity(req_lower)
        if entity and entity.get("table"):
            return entity["table"]

        # 4. Final resolve from words or default
        for word in req_lower.split():
            resolved = self.metadata.resolve_entity_to_table(word)
            if resolved:
                return resolved
                
        # 5. Last chance for institution tables if nothing else matched
        for name in table_names:
            if name in self.INSTITUTION_TABLES:
                singular = name.rstrip("s")
                if re.search(rf"\b{re.escape(name)}\b", req_lower) or (singular != name and re.search(rf"\b{re.escape(singular)}\b", req_lower)):
                    return name

        return self.metadata.get_default_table()

    def _is_people_list_query(self, req_lower: str) -> bool:
        if "give me" in req_lower and any(
            w in req_lower for w in ("names", "name", "id", "details", "detail", "information")
        ):
            return True
        people_terms = (
            "student", "students", "teacher", "teachers", "kid", "kids",
            "child", "children", "employee", "employees", "staff", "worker",
        )
        return any(re.search(rf"\b{re.escape(t)}\b", req_lower) for t in people_terms)

    def _apply_requested_columns(
        self, intent: QueryIntent, request: str, req_lower: str
    ) -> None:
        """Parse 'give me names id etc' and 'with id, name, salary' column lists."""
        raw_clause: str | None = None
        has_etc = False

        give_match = re.search(
            r"give\s+me\s+(?:the\s+)?(.+?)(?:\s+their\s+details|\s+their\s+detail|\s+all\s+details|\s+full\s+details|\s+from\b|$)",
            req_lower,
        )
        if give_match:
            raw_clause = give_match.group(1).strip()
            has_etc = self._clause_has_etc(raw_clause)

        if not raw_clause:
            with_match = re.search(
                r"\bwith\s+(.+?)(?:\s+from\b|\s+where\b|\s+for\b|$)",
                req_lower,
            )
            if with_match:
                raw_clause = with_match.group(1).strip()
                has_etc = self._clause_has_etc(raw_clause)

        if not raw_clause:
            return

        tokens, has_etc = self._tokenize_column_hints(raw_clause, has_etc)
        explicit_cols: list[str] = []
        for token in tokens:
            explicit_cols.extend(self._resolve_column_hint(intent.table, token))

        explicit_cols = list(dict.fromkeys(explicit_cols))
        wants_details = self._request_wants_details(req_lower)
        expand_etc = has_etc and ("give me" in req_lower or wants_details)

        if wants_details and self._is_list_entity_query(req_lower, intent.table):
            detail_cols = self._get_detail_columns(intent.table)
            intent.columns = self._merge_columns(explicit_cols, detail_cols)
            intent.select_all = False
        elif expand_etc:
            intent.columns = self._get_detail_columns(intent.table)
            intent.select_all = False
        elif explicit_cols:
            intent.columns = explicit_cols
            intent.select_all = False

    def _apply_details_columns(self, intent: QueryIntent, req_lower: str) -> None:
        """
        When the request asks for details on a list/show/generate entity query,
        select all meaningful schema columns (never SELECT *).
        """
        if intent.columns and not self._request_wants_details(req_lower):
            return

        if not self._request_wants_details(req_lower):
            return

        if not self._is_list_entity_query(req_lower, intent.table):
            return

        detail_cols = self._get_detail_columns(intent.table)
        if intent.columns:
            intent.columns = self._merge_columns(intent.columns, detail_cols)
        else:
            intent.columns = detail_cols
        intent.select_all = False

    def _request_wants_details(self, req_lower: str) -> bool:
        if any(phrase in req_lower for phrase in self.DETAIL_PHRASES):
            return True
        if re.search(r"\b(?:their|all|full)\s+details?\b", req_lower):
            return True
        if re.search(r"\bdetails?\b", req_lower) and "give me" in req_lower:
            return True
        if re.search(r"\binformation\b", req_lower):
            return True
        return False

    def _is_list_entity_query(self, req_lower: str, table: str) -> bool:
        has_action = any(action in req_lower for action in self.LIST_ACTION_WORDS)
        terms = self.metadata.get_entity_terms_for_table(table)
        has_entity = any(
            re.search(rf"\b{re.escape(term)}\b", req_lower) or term in req_lower
            for term in terms
            if len(term) >= 2
        )
        if not has_entity and self.metadata.infer_table_from_domain(req_lower) == table:
            has_entity = True
        return has_action and has_entity

    def _clause_has_etc(self, clause: str) -> bool:
        return bool(re.search(r"\betc\.?\b", clause, re.IGNORECASE))

    def _tokenize_column_hints(
        self, raw_clause: str, has_etc: bool
    ) -> tuple[list[str], bool]:
        cleaned = re.sub(r"\betc\.?\b", " ", raw_clause, flags=re.IGNORECASE)
        cleaned = cleaned.replace(",", " ")
        cleaned = re.sub(r"\s+and\s+", " ", cleaned)
        tokens: list[str] = []
        for part in cleaned.split():
            part = part.strip().lower()
            if not part or part in self.COLUMN_STOP_WORDS:
                continue
            if part in ("etc", "etcetera"):
                has_etc = True
                continue
            tokens.append(part)
        return tokens, has_etc

    def _resolve_column_hint(self, table: str, hint: str) -> list[str]:
        hint = hint.lower().strip()
        if hint in ("names", "name"):
            cols: list[str] = []
            for col in ("first_name", "last_name"):
                if self.schema.column_exists(table, col):
                    cols.append(col)
            return cols
        if hint in ("id", "ids", "identifier"):
            pk = self._get_primary_key_column(table)
            return [pk] if pk else []
        resolved = self._resolve_column(table, hint)
        return [resolved] if resolved else []

    def _get_primary_key_column(self, table: str) -> str | None:
        for col in self.schema.get_columns(table):
            if col.get("primary_key"):
                return col["name"]
        names = self.schema.get_column_names(table)
        return names[0] if names else None

    def _get_detail_columns(self, table: str) -> list[str]:
        """Meaningful columns for a table (excludes self-referential FKs like manager_id)."""
        detail_cols: list[str] = []
        schema_cols = self.schema.get_columns(table)
        relationships = self.schema.get_relationships()
        
        # Identify columns that are self-referential FKs
        self_ref_cols = set()
        for rel in relationships:
            if rel.get("from_table") == table and rel.get("to_table") == table:
                self_ref_cols.add(rel.get("from_column"))

        for col in schema_cols:
            name = col["name"]
            # Skip if it is a self-referential FK or marked as one in schema if available
            fk = col.get("foreign_key")
            if fk and fk.get("table") == table:
                continue
            if name in self_ref_cols:
                continue
            
            # Additional common self-referential patterns
            if name == "manager_id" and table == "employees":
                continue
            if name == "parent_id" and table == "categories": # Example of common pattern
                continue
                
            detail_cols.append(name)
        return detail_cols

    def _merge_columns(self, explicit: list[str], details: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for col in details:
            if col not in seen:
                merged.append(col)
                seen.add(col)
        for col in explicit:
            if col not in seen:
                merged.append(col)
                seen.add(col)
        return merged

    def _apply_entity_columns(self, intent: QueryIntent, req_lower: str) -> None:
        if intent.columns:
            return

        entity = self.metadata.find_matching_entity(req_lower)
        if entity and entity.get("column"):
            col = entity["column"]
            if self.schema.column_exists(intent.table, col):
                intent.columns.append(col)
                intent.select_all = False

        col_match = re.search(
            r"(?:show|list|get|display|select)\s+(?:only\s+)?([\w\s,]+?)(?:\s+from|\s+where|\s+for|$)",
            req_lower,
        )
        if col_match:
            raw_cols = col_match.group(1).strip()
            if raw_cols not in ("all", "*", "everything"):
                for part in re.split(r"\s*,\s*|\s+and\s+", raw_cols):
                    part = part.strip()
                    if part and part.lower() not in self.COLUMN_STOP_WORDS:
                        resolved = self._resolve_column(intent.table, part)
                        if resolved:
                            intent.columns.append(resolved)
                            intent.select_all = False

    def _apply_aggregations(self, intent: QueryIntent, req_lower: str) -> None:
        for phrase, agg in self.AGG_KEYWORDS.items():
            if phrase not in req_lower:
                continue

            col = self._find_agg_column(req_lower, intent.table)
            if "count" in phrase or agg == "COUNT":
                if col:
                    intent.aggregations.append((agg, col, f"{col}_count"))
                else:
                    intent.aggregations.append((agg, "*", "count"))
                intent.select_all = False
            elif col:
                safe_alias = f"{agg.lower()}_{col}"
                intent.aggregations.append((agg, col, safe_alias))
                intent.select_all = False
            break

        if "department wise" in req_lower or "per department" in req_lower or "by department" in req_lower:
            if self.schema.column_exists(intent.table, "department_id"):
                if not any(a[0] == "COUNT" for a in intent.aggregations):
                    intent.aggregations.append(("COUNT", "*", "employee_count"))
                intent.group_by.append("department_id")
                intent.select_all = False

        if "school wise" in req_lower or "per school" in req_lower or "by school" in req_lower:
            if self.schema.column_exists(intent.table, "school_id"):
                if not any(a[0] == "COUNT" for a in intent.aggregations):
                    intent.aggregations.append(("COUNT", "*", "record_count"))
                intent.group_by.append("school_id")
                intent.select_all = False

        if "grade wise" in req_lower or "per grade" in req_lower or "by grade" in req_lower:
            if self.schema.column_exists(intent.table, "grade"):
                if not any(a[0] == "COUNT" for a in intent.aggregations):
                    intent.aggregations.append(("COUNT", "*", "student_count"))
                intent.group_by.append("grade")
                intent.select_all = False

        count_match = re.search(
            r"(?:count|number)\s+of\s+(\w+)",
            req_lower,
        )
        if count_match and not intent.aggregations:
            intent.aggregations.append(("COUNT", "*", f"{count_match.group(1)}_count"))
            intent.select_all = False

    def _apply_filters(self, intent: QueryIntent, req_lower: str) -> None:
        phrases = self.metadata.get_common_phrases()

        if "this year" in req_lower:
            col = self._resolve_date_column(intent.table, "hire")
            intent.where_clauses.append(f"YEAR({col}) = YEAR(CURRENT_DATE)")

        if "last year" in req_lower:
            col = self._resolve_date_column(intent.table, "hire")
            intent.where_clauses.append(f"YEAR({col}) = YEAR(CURRENT_DATE) - 1")

        if "this month" in req_lower:
            col = self._resolve_date_column(intent.table, "date")
            intent.where_clauses.append(
                f"YEAR({col}) = YEAR(CURRENT_DATE) AND MONTH({col}) = MONTH(CURRENT_DATE)"
            )

        if "active" in req_lower and self.schema.column_exists(intent.table, "status"):
            intent.where_clauses.append(f"{intent.table}.status = 'active'")

        if "inactive" in req_lower and self.schema.column_exists(intent.table, "status"):
            intent.where_clauses.append(f"{intent.table}.status = 'inactive'")

        salary_match = re.search(r"salary\s*(>|<|>=|<=|=)\s*(\d+(?:\.\d+)?)", req_lower)
        if salary_match and self.schema.column_exists(intent.table, "salary"):
            op, val = salary_match.group(1), salary_match.group(2)
            intent.where_clauses.append(f"salary {op} {val}")

        salary_between = re.search(r"salary\s+between\s+(\d+)\s+and\s+(\d+)", req_lower)
        if salary_between:
            intent.where_clauses.append(
                f"salary BETWEEN {salary_between.group(1)} AND {salary_between.group(2)}"
            )

        dept_match = re.search(r"department\s+(?:id\s+)?(?:=|is)\s*(\d+)", req_lower)
        if dept_match and self.schema.column_exists(intent.table, "department_id"):
            intent.where_clauses.append(f"department_id = {dept_match.group(1)}")

        dept_name = re.search(r"department\s+(?:named?|called)\s+['\"]?(\w+)['\"]?", req_lower)
        if dept_name:
            intent.joins.append(
                f"INNER JOIN departments ON {intent.table}.department_id = departments.department_id"
            )
            intent.where_clauses.append(f"departments.department_name = '{dept_name.group(1)}'")

        for phrase, meta in phrases.items():
            if phrase in req_lower and "filter" in meta:
                filt = meta["filter"]
                col_hint = meta.get("column_hint", "")
                col = self._resolve_column(intent.table, col_hint) if col_hint else col_hint
                filt = filt.replace("{column}", col or "hire_date").replace("{table}", intent.table)
                if filt not in intent.where_clauses:
                    intent.where_clauses.append(filt)

        name_match = re.search(r"(?:named?|called)\s+['\"]([^'\"]+)['\"]", req_lower)
        if name_match:
            if self.schema.column_exists(intent.table, "first_name"):
                parts = name_match.group(1).split()
                if len(parts) >= 2:
                    intent.where_clauses.append(
                        f"first_name = '{parts[0]}' AND last_name = '{' '.join(parts[1:])}'"
                    )
                else:
                    intent.where_clauses.append(f"first_name = '{parts[0]}'")

    def _apply_ordering(self, intent: QueryIntent, req_lower: str) -> None:
        order_patterns = [
            (r"(?:order(?:ed)?\s+by|sort(?:ed)?\s+by)\s+(\w+)(?:\s+(asc|desc))?", None),
            (r"(?:top|highest|maximum|largest)\s+\d*\s*(?:\w+\s+)*by\s+(\w+)", "DESC"),
            (r"(?:bottom|lowest|minimum|smallest)\s+\d*\s*(?:\w+\s+)*by\s+(\w+)", "ASC"),
            (r"by\s+(\w+)\s+(?:desc|descending|high to low)", "DESC"),
            (r"by\s+(\w+)\s+(?:asc|ascending|low to high)", "ASC"),
        ]

        for pattern, default_dir in order_patterns:
            match = re.search(pattern, req_lower)
            if match:
                col = self._resolve_column(intent.table, match.group(1))
                if col:
                    groups = match.groups()
                    explicit_dir = groups[1] if len(groups) > 1 else None
                    direction = (explicit_dir or default_dir or "ASC").upper()
                    intent.order_by.append((col, direction))
                break

        if "salary" in req_lower and ("highest" in req_lower or "top" in req_lower):
            if self.schema.column_exists(intent.table, "salary") and not intent.order_by:
                intent.order_by.append(("salary", "DESC"))

        if "salary" in req_lower and "lowest" in req_lower and not intent.order_by:
            intent.order_by.append(("salary", "ASC"))

        if "hire_date" in req_lower or "recently hired" in req_lower:
            col = self._resolve_date_column(intent.table, "hire")
            intent.order_by.append((col, "DESC"))

    def _apply_limit(self, intent: QueryIntent, req_lower: str) -> None:
        limit_match = re.search(
            r"(?:top|first|generate|get|show|list|fetch|return)\s+(\d+)\b",
            req_lower,
        )
        if limit_match:
            intent.limit = min(int(limit_match.group(1)), settings.max_limit)
            return

        for word, num in self.NUMBER_WORDS.items():
            if re.search(rf"\b{word}\b", req_lower) and any(
                w in req_lower for w in ("generate", "get", "show", "list", "top", "first")
            ):
                intent.limit = min(num, settings.max_limit)
                return

        top_n = re.search(r"top\s+(\d+)", req_lower)
        if top_n:
            intent.limit = min(int(top_n.group(1)), settings.max_limit)

        if "highest" in req_lower or "lowest" in req_lower:
            if intent.limit is None:
                intent.limit = 1

    def _apply_group_by(self, intent: QueryIntent, req_lower: str) -> None:
        if any(w in req_lower for w in ("top ", "highest", "lowest", "order by", "sort by")):
            return
        group_patterns = [
            r"group\s+by\s+(\w+)",
            r"(\w+)\s+wise",
            r"per\s+(\w+)",
        ]
        for pattern in group_patterns:
            match = re.search(pattern, req_lower)
            if match:
                hint = match.group(1)
                if hint in ("department", "departments"):
                    col = "department_id"
                else:
                    col = self._resolve_column(intent.table, hint)
                if col and col not in intent.group_by:
                    intent.group_by.append(col)
                    if intent.aggregations:
                        intent.select_all = False

    def _apply_joins(self, intent: QueryIntent, req_lower: str) -> None:
        if "department" in req_lower and intent.table == "employees":
            if "name" in req_lower or "department_name" in req_lower:
                join_sql = (
                    "INNER JOIN departments ON employees.department_id = departments.department_id"
                )
                if join_sql not in intent.joins:
                    intent.joins.append(join_sql)
                    if not intent.columns:
                        intent.columns.extend(
                            ["employees.*", "departments.department_name"]
                        )
                        intent.select_all = False

        if "project" in req_lower and intent.table == "employees":
            join_sql = (
                "INNER JOIN employee_projects ON employees.employee_id = employee_projects.employee_id "
                "INNER JOIN projects ON employee_projects.project_id = projects.project_id"
            )
            if join_sql not in intent.joins:
                intent.joins.append(join_sql)

    def _apply_distinct(self, intent: QueryIntent, req_lower: str) -> None:
        if "distinct" in req_lower or "unique" in req_lower:
            intent.distinct = True

    def _build_sql(self, intent: QueryIntent) -> str:
        parts: list[str] = []

        select_items: list[str] = []
        if intent.select_all and not intent.aggregations:
            select_items.append("*")
        else:
            if intent.aggregations:
                for agg, col, alias in intent.aggregations:
                    expr = f"{agg}({col})"
                    if alias:
                        expr += f" AS {alias}"
                    select_items.append(expr)
            if intent.group_by:
                for g in intent.group_by:
                    if g not in [s.split(" AS ")[0].strip() for s in select_items]:
                        select_items.append(g)
            if intent.columns:
                for c in intent.columns:
                    if c not in select_items:
                        select_items.append(c)
            if not select_items:
                select_items.append("*")

        distinct_kw = "DISTINCT " if intent.distinct else ""
        parts.append(f"SELECT {distinct_kw}{', '.join(select_items)}")
        parts.append(f"FROM {intent.table}")

        if intent.joins:
            for join in intent.joins:
                parts.append(join)

        if intent.where_clauses:
            parts.append("WHERE " + " AND ".join(intent.where_clauses))

        if intent.group_by:
            parts.append("GROUP BY " + ", ".join(intent.group_by))

        if intent.having:
            parts.append("HAVING " + " AND ".join(intent.having))

        if intent.order_by:
            order_str = ", ".join(f"{col} {dir}" for col, dir in intent.order_by)
            parts.append(f"ORDER BY {order_str}")

        if intent.limit is not None:
            parts.append(f"LIMIT {intent.limit}")

        return "\n".join(parts) + ";"

    def _normalize_sql(self, sql: str) -> str:
        lines = [line.rstrip() for line in sql.strip().splitlines()]
        return "\n".join(lines)

    def _resolve_column(self, table: str, hint: str) -> str | None:
        hint = hint.lower().strip().replace(" ", "_")
        columns = self.schema.get_column_names(table)
        for col in columns:
            if col.lower() == hint:
                return col
        for col in columns:
            if hint in col.lower() or col.lower() in hint:
                return col
        matches = self.schema.find_column_across_tables(hint)
        for t, c in matches:
            if t == table:
                return c
        return matches[0][1] if matches else None

    def _resolve_date_column(self, table: str, hint: str) -> str:
        for col in self.schema.get_column_names(table):
            if "date" in col.lower() and hint in col.lower():
                return col
        for col in self.schema.get_column_names(table):
            if "date" in col.lower():
                return col
        return "hire_date"

    def _find_agg_column(self, req_lower: str, table: str) -> str | None:
        for word in ("salary", "budget", "hours", "amount"):
            if word in req_lower:
                resolved = self._resolve_column(table, word)
                if resolved:
                    return resolved
        return None

    def _find_order_column(self, req_lower: str, table: str) -> str | None:
        return self._find_agg_column(req_lower, table)

    def _infer_group_column(self, req_lower: str, table: str) -> str | None:
        if "department" in req_lower:
            return self._resolve_column(table, "department_id")
        if "status" in req_lower:
            return self._resolve_column(table, "status")
        return None

    def _needs_default_order(self, req_lower: str) -> bool:
        return any(
            w in req_lower
            for w in ("highest", "lowest", "top", "bottom", "best", "worst", "maximum", "minimum")
        )

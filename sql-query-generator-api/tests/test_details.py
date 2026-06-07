import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.sql_generator import SQLGeneratorService

generator = SQLGeneratorService()
client = TestClient(app)

DETAILS_QUERY = (
    "generate 50 employees give me the names id etc their details"
)

EXPECTED_COLUMNS = [
    "employee_id",
    "first_name",
    "last_name",
    "email",
    "phone",
    "hire_date",
    "salary",
    "department_id",
    "job_title",
    "status",
]


def _select_list(sql: str) -> str:
    match = re.search(r"SELECT\s+(.+?)\s+FROM", sql, re.IGNORECASE | re.DOTALL)
    assert match, f"No SELECT clause found in: {sql}"
    return match.group(1)


def test_details_query_columns_and_limit():
    sql = generator.generate(DETAILS_QUERY)
    assert "LIMIT 50" in sql
    assert "FROM employees" in sql
    assert "SELECT *" not in sql

    select_clause = _select_list(sql)
    for col in EXPECTED_COLUMNS:
        assert col in select_clause, f"Missing column {col} in: {select_clause}"

    assert "manager_id" not in select_clause


def test_details_query_column_order():
    sql = generator.generate(DETAILS_QUERY)
    select_clause = _select_list(sql)
    positions = [select_clause.index(col) for col in EXPECTED_COLUMNS]
    assert positions == sorted(positions)


def test_details_query_api_json():
    r = client.post("/generate", json={"query": DETAILS_QUERY})
    assert r.status_code == 200
    sql = r.json()["sql"]
    assert "LIMIT 50" in sql
    for col in EXPECTED_COLUMNS:
        assert col in sql


def test_details_query_api_plain_sql():
    r = client.post("/generate/sql", json={"query": DETAILS_QUERY})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "employee_id" in r.text
    assert "LIMIT 50" in r.text


@pytest.mark.parametrize(
    "query",
    [
        "list employees their details",
        "show employees all details",
        "generate 10 staff full details",
    ],
)
def test_details_phrases_use_detail_columns(query: str):
    sql = generator.generate(query)
    assert "SELECT *" not in sql
    assert "employee_id" in sql
    assert "first_name" in sql


def test_give_me_etc_without_details_expands_columns():
    sql = generator.generate("generate 20 employees give me the names id etc")
    assert "SELECT *" not in sql
    assert "first_name" in sql
    assert "employee_id" in sql
    assert "email" in sql

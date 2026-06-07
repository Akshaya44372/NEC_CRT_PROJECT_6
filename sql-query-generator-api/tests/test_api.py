import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_schema_endpoint():
    r = client.get("/schema")
    assert r.status_code == 200
    data = r.json()
    assert "tables" in data
    assert any(t["name"] == "employees" for t in data["tables"])


def test_metadata_endpoint():
    r = client.get("/metadata")
    assert r.status_code == 200
    data = r.json()
    assert "entities" in data
    assert "default_table" in data


def test_ui_root():
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


@pytest.mark.parametrize(
    "query,expected_fragments",
    [
        ("Generate 50 employees", ["SELECT", "FROM employees", "LIMIT 50"]),
        ("Show highest salary employee", ["ORDER BY salary DESC", "LIMIT 1"]),
        ("Show top 10 employees by salary", ["ORDER BY salary DESC", "LIMIT 10"]),
        ("List employees hired this year", ["YEAR(hire_date)", "CURRENT_DATE"]),
        (
            "Show department wise employee count",
            ["department_id", "COUNT", "GROUP BY department_id"],
        ),
    ],
)
def test_generate_examples(query: str, expected_fragments: list[str]):
    r = client.post("/generate", json={"query": query})
    assert r.status_code == 200
    sql = r.json()["sql"].upper()
    for frag in expected_fragments:
        assert frag.upper() in sql, f"Expected '{frag}' in SQL for query: {query}\nGot: {r.json()['sql']}"


def test_generate_sql_plain():
    r = client.post(
        "/generate/sql",
        json={"query": "Generate 50 employees"},
        headers={"Accept": "text/plain"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "SELECT" in r.text
    assert "LIMIT 50" in r.text
    assert "{" not in r.text


def test_generate_get():
    r = client.get("/generate", params={"q": "Show top 5 employees by salary"})
    assert r.status_code == 200
    assert "LIMIT 5" in r.text


def test_empty_query_rejected():
    r = client.post("/generate", json={"query": ""})
    assert r.status_code == 422

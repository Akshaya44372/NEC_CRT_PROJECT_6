import pytest

from app.services.sql_generator import SQLGeneratorService

generator = SQLGeneratorService()


@pytest.mark.parametrize(
    "query,expected_table,expected_in_sql",
    [
        (
            "Generate 30 students from school give me names id their details",
            "students",
            ["student_id", "first_name", "LIMIT 30"],
        ),
        (
            "List 20 teachers with names and subject",
            "teachers",
            ["teachers", "subject", "LIMIT 20"],
        ),
        (
            "Show 15 kids give me names id details",
            "students",
            ["students", "LIMIT 15"],
        ),
        (
            "Generate 10 offices with all details",
            "offices",
            ["offices", "LIMIT 10"],
        ),
        (
            "List all schools",
            "schools",
            ["schools"],
        ),
        (
            "Generate 50 employees give me the names id etc their details",
            "employees",
            ["employee_id", "LIMIT 50"],
        ),
    ],
)
def test_multi_domain_queries(query: str, expected_table: str, expected_in_sql: list[str]):
    sql = generator.generate(query)
    assert f"FROM {expected_table}" in sql
    upper = sql.upper()
    for frag in expected_in_sql:
        assert frag.upper() in upper, f"Missing {frag} in:\n{sql}"


def test_about_school_defaults_to_students():
    sql = generator.generate("Generate 25 about school give me names id details")
    assert "FROM students" in sql
    assert "LIMIT 25" in sql

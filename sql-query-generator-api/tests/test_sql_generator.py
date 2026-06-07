import pytest

from app.services.sql_generator import SQLGeneratorService

generator = SQLGeneratorService()


@pytest.mark.parametrize(
    "request_text,checks",
    [
        (
            "Generate 50 employees",
            lambda s: "LIMIT 50" in s and "employees" in s.lower(),
        ),
        (
            "Show highest salary employee",
            lambda s: "ORDER BY salary DESC" in s and "LIMIT 1" in s,
        ),
        (
            "Show top 10 employees by salary",
            lambda s: "LIMIT 10" in s and "salary" in s.lower(),
        ),
        (
            "List employees hired this year",
            lambda s: "YEAR(hire_date)" in s and "CURRENT_DATE" in s,
        ),
        (
            "Show department wise employee count",
            lambda s: "GROUP BY department_id" in s and "COUNT" in s,
        ),
    ],
)
def test_generator_examples(request_text: str, checks):
    sql = generator.generate(request_text)
    assert sql.endswith(";")
    assert checks(sql)


def test_sql_ends_with_semicolon():
    sql = generator.generate("Get 5 employees")
    assert sql.strip().endswith(";")

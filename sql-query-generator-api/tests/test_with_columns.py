from app.services.sql_generator import SQLGeneratorService

generator = SQLGeneratorService()


def test_generate_with_specific_columns():
    sql = generator.generate("Generate 50 employees with id, name, salary")
    assert "LIMIT 50" in sql
    assert "employee_id" in sql
    assert "first_name" in sql
    assert "last_name" in sql
    assert "salary" in sql
    assert "SELECT *" not in sql


def test_generate_with_space_separated_columns():
    sql = generator.generate("Generate 50 employees with id name salary")
    assert "LIMIT 50" in sql
    assert "employee_id" in sql
    assert "salary" in sql
    assert "SELECT *" not in sql

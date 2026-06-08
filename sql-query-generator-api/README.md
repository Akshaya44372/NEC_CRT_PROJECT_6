# SQL Query Generator API

Converts natural language requests into **valid, executable SQL only**. Supports **school, office, employees, students, teachers, kids**, and more. Uses schema and metadata APIs before generation.

## Features

- **GET /schema** — tables, columns, keys, relationships
- **GET /metadata** — business entities, aliases, phrase mappings
- **POST /generate** — JSON `{"sql": "..."}`
- **POST /generate/sql** — raw SQL only (`text/plain`)
- **GET /generate?q=...** — quick SQL-only testing                  
- **GET /** — Web UI (textarea + Execute → SQL-only output)

## Quick Start

```bash
cd sql-query-generator-api
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
python run.py
```

- **Web UI:** http://localhost:8000  
- **API docs:** http://localhost:8000/docs

## Example Requests

| Natural language | Generated SQL |
|------------------|---------------|
| Generate 50 employees | `SELECT * FROM employees LIMIT 50;` |
| Generate 50 employees give me the names id etc their details | Explicit detail columns + `LIMIT 50` |
| Generate 50 employees with id, name, salary | `employee_id`, `first_name`, `last_name`, `salary` |
| Show highest salary employee | `ORDER BY salary DESC LIMIT 1` |
| Show top 10 employees by salary | `ORDER BY salary DESC LIMIT 10` |
| List employees hired this year | `YEAR(hire_date) = YEAR(CURRENT_DATE)` |
| Show department wise employee count | `GROUP BY department_id` + `COUNT` |

### Details / column hints

- **names** → `first_name`, `last_name`
- **id** → primary key (`employee_id`)
- **their details**, **all details**, **etc** (with *give me*) → all meaningful columns from schema (not `SELECT *`)

### cURL

```bash
curl http://localhost:8000/schema
curl http://localhost:8000/metadata

curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"Show top 10 employees by salary\"}"

curl -X POST http://localhost:8000/generate/sql \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"generate 50 employees give me the names id etc their details\"}"

curl "http://localhost:8000/generate?q=Show%20highest%20salary%20employee"
```

## Project Structure

```
sql-query-generator-api/
├── app/
│   ├── api/routes/       # schema, metadata, generate
│   ├── core/config.py
│   ├── data/             # schema.json, metadata.json
│   ├── services/         # SQLGeneratorService
│   ├── static/           # Web UI (index.html, style.css, app.js)
│   └── main.py
├── tests/
├── scripts/create_zip.py
├── requirements.txt
├── run.py
└── README.md
```

## Tests

```bash
pytest tests/ -v
```

## Customize Schema

Edit `app/data/schema.json` and `app/data/metadata.json` to match your database. Table and column names in generated SQL match the schema file exactly.

## License

MIT

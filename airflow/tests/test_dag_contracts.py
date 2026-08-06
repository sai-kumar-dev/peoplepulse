from __future__ import annotations

import ast
from pathlib import Path

DAG_DIR = Path(__file__).parents[1] / "dags"


def test_required_dags_exist_and_parse_as_python() -> None:
    required = {
        "people_data_ingestion.py",
        "people_data_transformation.py",
        "people_data_quality.py",
        "people_data_end_to_end.py",
    }
    assert required <= {path.name for path in DAG_DIR.glob("*.py")}
    for filename in required:
        ast.parse((DAG_DIR / filename).read_text(encoding="utf-8"))


def test_dags_do_not_contain_inline_database_passwords() -> None:
    content = "\n".join(path.read_text(encoding="utf-8") for path in DAG_DIR.glob("*.py"))
    assert "postgresql://" not in content
    assert "SNOWFLAKE_PASSWORD=" not in content

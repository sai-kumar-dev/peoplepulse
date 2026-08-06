"""Print the stable local demo entry points and intentionally local credentials."""

from __future__ import annotations


def main() -> None:
    print(
        """
PeoplePulse demo is starting:
  API docs:    http://localhost:8000/docs
  Dashboard:   http://localhost:8501
  Airflow:     http://localhost:8080

Local-only credentials:
  Airflow:     admin / admin
  Admin token: local-admin-change-me

Verify:
  curl http://localhost:8000/health/live
  curl http://localhost:8000/api/v1/workforce/summary
  docker compose ps
""".strip()
    )


if __name__ == "__main__":
    main()

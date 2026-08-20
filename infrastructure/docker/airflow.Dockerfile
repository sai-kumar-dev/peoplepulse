# syntax=docker/dockerfile:1.7
FROM apache/airflow:3.3.1-python3.12

USER root
COPY --chown=airflow:root . /opt/peoplepulse
WORKDIR /opt/peoplepulse

USER airflow
RUN pip install --no-cache-dir \
    "psycopg[binary]>=3.2,<4" \
    "pydantic>=2.10,<3" \
    "dbt-core>=1.9,<1.10" \
    "dbt-postgres>=1.9,<1.10" \
    -e .

ENV AIRFLOW_HOME=/opt/airflow \
    PYTHONPATH=/opt/peoplepulse


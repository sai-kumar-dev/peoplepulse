# syntax=docker/dockerfile:1.7
FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/peoplepulse

RUN addgroup --system --gid 10001 peoplepulse \
    && adduser --system --uid 10001 --ingroup peoplepulse --home /opt/peoplepulse peoplepulse

COPY pyproject.toml README.md LICENSE ./
COPY peoplepulse ./peoplepulse
COPY data_generator ./data_generator
COPY ingestion ./ingestion
COPY api ./api
COPY dashboard ./dashboard

FROM base AS runtime
RUN pip install --upgrade pip \
    && pip install .
USER peoplepulse
EXPOSE 8000 8501

FROM base AS dbt
COPY dbt ./dbt
RUN pip install --upgrade pip \
    && pip install ".[dbt]"
USER peoplepulse
ENTRYPOINT ["dbt"]

FROM base AS test
COPY airflow ./airflow
COPY tests ./tests
COPY scripts ./scripts
COPY dbt ./dbt
RUN pip install --upgrade pip \
    && pip install ".[dev,dbt]"
USER peoplepulse


# Data flow and lineage

```mermaid
flowchart TB
  subgraph Source
    EMP[HRIS employees]
    DEP[HRIS departments]
    HIRE[HRIS hire events]
    TERM[HRIS termination events]
  end
  subgraph Raw
    REMP[raw_hris.employees]
    RDEP[raw_hris.departments]
    RHIRE[raw_hris.hires]
    RTERM[raw_hris.terminations]
  end
  subgraph Transform
    SEMP[stg_hris__employees]
    INT[int_employee_history]
    DIM[dim_employee SCD2]
    FH[fact_hire]
    FT[fact_termination]
    FS[fact_employee_snapshot]
  end
  subgraph Consume
    HC[mart_headcount]
    AT[mart_attrition]
    WS[mart_workforce_summary]
    API[FastAPI aggregate endpoints]
    UI[Streamlit dashboard]
  end
  EMP --> REMP --> SEMP --> INT --> DIM
  DEP --> RDEP --> INT
  HIRE --> RHIRE --> FH
  TERM --> RTERM --> FT
  DIM --> FS
  FH --> HC
  FT --> AT
  FS --> HC
  HC --> WS
  AT --> WS
  WS --> API --> UI
```

Lineage is declared in dbt `ref()`/`source()` relationships and exposed through
the manifest and governance API. The batch identifier links each raw record to
`audit.pipeline_batch`; model build artifacts link transformations to their
invocation.

Business-effective dates (`hire_date`, `termination_date`, `valid_from`,
`valid_to`) stay separate from technical load timestamps (`_ingested_at`,
`loaded_at`). Point-in-time queries use effective ranges, while freshness and
recovery use technical timestamps.


# E2EPS — Architecture and Workflow

## 1. E2EPS software architecture

Stateless, vectorised physics core; orchestration splits the time axis into
chunks and runs them in parallel; data layer owns persistence.

```mermaid
flowchart TB
  subgraph IF[Interface layer]
    CLI[CLI / batch jobs]
    API[REST API]
    UI[Notebooks / dashboards]
  end
  subgraph ORCH[Orchestration]
    SM[Scenario Manager<br/>validate, version config]
    SO[Simulation Orchestrator<br/>time grid, chunking, retries]
    WK[Compute workers<br/>Dask / Ray]
  end
  subgraph CORE[Physics core - stateless, vectorised NumPy]
    TF[Time & Frames<br/>UTC, GMST, ECI/ECEF, WGS84]
    OP[Orbit Propagator<br/>Walker gen, Kepler+J2, SGP4 plug-in]
    VG[Visibility & Geometry<br/>az/el/range, masks, passes]
    RF[RF Link Budget<br/>FSPL, atmos, C/N, MODCOD]
    RA[Beam & Resource Allocator<br/>association, handover, capacity share]
    LT[Latency & Routing<br/>path length, ISL graph]
  end
  subgraph AN[Analytics]
    KPI[KPI Aggregator<br/>capacity, throughput, availability, latency]
  end
  subgraph DATA[Data]
    REF[(Reference data<br/>ephemerides, antenna patterns,<br/>MODCOD, rain maps, terminals)]
    RES[(Results store<br/>Parquet / Zarr + run metadata)]
    CACHE[(Ephemeris cache)]
  end
  CLI & API & UI --> SM --> SO --> WK
  WK --> OP --> VG --> RF --> RA --> KPI
  VG --> LT --> KPI
  TF -.-> OP & VG
  REF -.-> OP & RF & RA
  OP <--> CACHE
  KPI --> RES --> API
```


## 2. Workflow and data exchanged

```mermaid
flowchart TD
  A[Scenario file<br/>constellation, terminals, RF params, time window] --> B[Scenario Manager: validate + version]
  B --> C[Orchestrator: build time grid, split into chunks]
  C --> D{{For each time chunk - in parallel}}
  D --> E[Orbit Propagator]
  E -- "sat positions ECEF [T,N,3]" --> F[Visibility & Geometry]
  F -- "az, el, range [T,G,N] + visible mask" --> G[Association / handover<br/>serving sat per terminal]
  G -- "serving link list" --> H[RF Link Budget]
  H -- "C/N, MODCOD, link rate" --> I[Resource Allocator<br/>share beam capacity among users]
  G -- "slant range" --> J[Latency estimator]
  I -- "user throughput" --> K[KPI partials per chunk]
  J -- "one-way delay" --> K
  K --> L[Reduce across chunks]
  L --> M[(Results: KPI tables, time series, pass lists)]
  M --> N[Reports / dashboards / API]
```

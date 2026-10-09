# E2EPS — Architecture, Workflow & Digital Twin

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

## 3. Digital Twin solutions architecture

```mermaid
flowchart TB
  USERS[Engineering: Systems, Network, RF<br/>Operations, Product]
  subgraph PRES[Presentation]
    PORTAL[Web portal + 3D globe view]
    DASH[KPI dashboards / notebooks]
    GW[API gateway + IAM]
  end
  subgraph CTRL[Twin control plane]
    SCN[Scenario & Config Service<br/>versioned scenarios]
    WF[Workflow Orchestrator<br/>Argo / Airflow, parameter sweeps]
    BUS[Co-simulation bus<br/>time sync + events: Kafka / DDS]
  end
  subgraph SIM[Simulators and emulators]
    E2E[E2EPS<br/>analytical performance]
    SPACE[Space Segment Emulator<br/>bus, payload, power/thermal, flight SW SIL/HIL]
    GND[Ground Segment Emulator<br/>gateways, TT&C, NOC, SDN controller]
    UT[User Terminal Emulator<br/>antenna tracking, terminal SW]
    NET[Network Emulator<br/>packet-level: ns-3 / OMNeT++ / containers]
  end
  subgraph DATAP[Data platform]
    LAKE[(Data lake: Parquet on object storage)]
    TSDB[(Time-series DB)]
    CAT[(Reference catalogue<br/>orbits, antennas, terminals)]
  end
  subgraph REAL[Real-world integration]
    TLM[Live telemetry ingest]
    FDS[Flight Dynamics System<br/>real ephemerides]
    OSS[OSS/BSS: demand, customers]
  end
  subgraph PLAT[Platform]
    K8S[Kubernetes on cloud + HPC/GPU pool]
    OBS[CI/CD, observability, security]
  end
  USERS --> PORTAL & DASH --> GW --> SCN & WF
  WF --> E2E & SPACE & GND & UT & NET
  SPACE & GND & UT & NET <--> BUS
  E2E -- "capacity / link-rate tables" --> NET
  E2E & SPACE & GND & UT & NET --> LAKE
  TLM --> TSDB --> LAKE
  FDS --> CAT --> E2E & SPACE
  OSS -- "demand maps" --> E2E
  LAKE --> DASH
  SIM -.runs on.-> K8S
```


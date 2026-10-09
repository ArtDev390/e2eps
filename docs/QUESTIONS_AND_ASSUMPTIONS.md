# E2EPS — Open Questions & Working Assumptions

The brief does not give every parameter, so to move forward I made the
assumptions below. Each one says why it is reasonable, what changes if it is
wrong, and where it lives in the code, so it can be swapped once Engineering
confirms the real value. The questions in §3 are the ones I would take to each
team. Each is tagged with the assumption it would replace (`A#`).

Reference numbers used below (1050 km circular orbit, computed with this code):
orbital period **106.2 min**, ground speed of the sub-satellite point ≈ 7.3 km/s
(**220 km per 30 s step**). Slant range / one-way delay / free-space path loss
at 20 GHz:

| Elevation | Slant range | One-way delay | FSPL @ 20 GHz |
|---|---|---|---|
| 90° | 1050 km | 3.50 ms | 178.9 dB |
| 25° | 1970 km | 6.57 ms | 184.4 dB |
| 10° | 2858 km | 9.53 ms | 187.6 dB |

The 5.5 dB swing between zenith and a 25° mask is why elevation and range are
the core outputs of the Visibility module.

---

## 1. Scope assumptions

| ID | Assumption | Justification |
|---|---|---|
| S1 | E2EPS models **physics-level** performance (geometry, RF, capacity sharing), not packet-level transport. | Stated in the brief. Packet-level behaviour belongs in the Digital Twin's Network Emulator, which consumes E2EPS link-rate tables (see `ARCHITECTURE.md` §3). |
| S2 | The current KPIs are **geometry-level upper bounds**. | With no satellite above the mask there is no service, whatever the link budget. RF and the Resource Allocator can only lower availability, never raise it. |
| S3 | Gateways and user terminals share one `Terminal` model, told apart by `kind` and `min_el_deg`. | The geometry is the same for both. Feeder-link-specific behaviour (site diversity, rain fade) belongs in later modules. |

## 2. Technical assumptions

| ID | Assumption (value in code) | Justification | Impact if wrong | Where to change |
|---|---|---|---|---|
| A1 | **Constellation:** 2 shells at 1050 km, 12 planes × 24 sats each = 576 sats. Polar shell 88° (Walker star), inclined shell 65° (Walker delta). | In line with publicly reported figures (~600 LEO sats), to be confirmed. Marked **illustrative** in the scenario file. | All KPIs change. The model does not: shells are pure input data. | `scenarios/*.json` |
| A2 | **Orbits are circular with J2 secular drift only.** No drag, eccentricity or station-keeping. | The standard design-phase model: closed form and fully vectorised. RAAN drift is the main effect on coverage over days (tested: −4.49°/day at 550 km, 53°). | Position error grows over weeks. Fine for coverage statistics, not for antenna pointing or conjunction work. | Swap in SGP4 or real ephemerides through the `Propagator` protocol in `orbit.py`. |
| A3 | **Frames:** ECI→ECEF uses GMST only. No precession, nutation or polar motion. | The Walker constellation is defined directly in this frame, so leaving these out only rotates the whole pattern. Coverage statistics are unaffected. | **Must be fixed before comparing with real ephemerides:** precession alone since J2000 is ≈ 0.36°, about 47 km at orbit radius. | `frames.py` (e.g. an IAU-2006 implementation or `astropy`). |
| A4 | **Earth:** WGS84 ellipsoid, no terrain, buildings or foliage masking. | Terrain data is site-specific and not provided. The elevation mask stands in for typical blockage. | Availability is optimistic in mountains and cities. | Per-terminal azimuth/elevation horizon mask in `visibility.py`. |
| A5 | **Minimum elevation:** 25° for user terminals, 10° for gateways. | Typical LEO user-terminal values. Gateways sit on clear sites with large dishes. A lower mask means longer range and more atmosphere (see table above). | Strong effect on visible-satellite counts and availability. | `min_el_deg` per terminal in the scenario. |
| A6 | **Serving satellite = highest elevation**, re-evaluated every step with no hysteresis. | Shortest range and least atmosphere, so the best link budget. A neutral baseline until the real policy is known. | **Over-counts handovers.** Ignores load balancing and beam capacity. | Resource Allocator (planned). For now, `compute_visibility` in `visibility.py`. |
| A7 | **Time grid:** 30 s step over a 2 h window. | 2 h covers more than one orbit (106 min). 30 s keeps outputs small for review. | An outage shorter than one step can be missed, and handover times are only accurate to ±30 s. Statistics need **≥ 24 h** because the ground track takes days to repeat. | `time` in the scenario, or `--hours` / `--step` on the CLI. |
| A8 | **Access delay** = one-way user↔satellite slant range ÷ c. | It is the only latency part that geometry alone can bound. | Not end-to-end: the feeder link, ISL hops, processing and queuing are added by the Latency & Routing module. | `kpi.py` |
| A9 | **Epoch** 2026-01-01T00:00Z is arbitrary. | With a uniform Walker pattern, statistics over a full window barely depend on the start time. | None for statistics. Matters once real ephemerides are used. | `epoch` in the scenario. |
| A10 | **Performance target:** a full run on a laptop in seconds, and memory bounded by chunk size. | The brief mentions computing limits. Vectorised kernels plus a chunked time axis (see `benchmarks/`). | If the real target is global grids × 24 h × many sweeps, we need the distributed path in `ARCHITECTURE.md`. | `--chunk` on the CLI. Orchestrator (planned). |

## 3. Questions for Engineering

### Systems Engineering
1. What are the **official shell parameters** (altitude, inclination, planes, sats/plane, Walker phasing F), and how does the **deployment phase in** over time? → A1. The phase-in drives the `what_if_polar_only` style of scenario.
2. Which **KPIs and targets** are contractual or design-driving? For example: availability % at what elevation, latitude band, time percentile; throughput per user vs per cell; latency at which percentile. → S2, A8
3. What **accuracy vs runtime** trade-off is acceptable per study type (quick design sweep vs final sign-off)? → A2, A7, A10
4. Should eclipse or power constraints on the payload limit capacity (sats off or degraded in eclipse)? → future Resource Allocator

### RF / Payload Engineering
5. **Frequency bands** for the user link and the feeder link (Ka? Ku?) and their bandwidth per beam. → RF Link Budget
6. **Satellite EIRP and G/T, user-terminal and gateway antenna patterns** (gain vs off-boresight angle, scan loss for phased arrays). → RF Link Budget, A5
7. **Beam layout:** number of beams, fixed or steerable, frequency reuse scheme, beam-hopping? → Resource Allocator, interference (C/(N+I))
8. **MODCOD table and ACM thresholds** (e.g. DVB-S2X), plus margins. → RF Link Budget → link rate
9. **Propagation models:** ITU-R P.618 rain, P.676 gases, P.840 clouds, P.531 scintillation? Which availability percentile? → RF Link Budget
10. **Elevation masks** per terminal type, and is there a maximum scan angle tighter than the mask? → A5

### Network Engineering
11. **ISL topology:** how many optical terminals per sat, intra- and cross-plane links, are polar-crossing / seam links kept? → Latency & Routing
12. **Gateway / PoP locations** and the backhaul to the core. → A8, Latency & Routing
13. **Routing policy:** shortest path, load-aware, or traffic-engineered? Is end-to-end latency user→PoP or user→user? → A8
14. **Satellite selection and handover policy:** hysteresis, make-before-break, scheduled (time-planned) handovers? → A6

### Ground Segment & Operations
15. Gateway **site diversity** and the rain-fade switchover policy. → S3
16. Can we get **real ephemerides** (CCSDS OEM or TLEs from Flight Dynamics) for validation? → A2. Also used for the Digital Twin's live mode.
17. Telemetry formats and rates, so E2EPS predictions can be compared with measured link performance. → Digital Twin calibration loop

### Product / Commercial
18. **Demand model:** where are the users (government, enterprise, maritime, aero), how many per cell, what traffic profile? → Resource Allocator, capacity KPIs
19. Which **regions / terminal locations** are priority for studies (latitude bands, sea lanes, specific customers)? → terminal sets in scenarios

### Software / Digital Twin platform
20. Who are the users and how do they run it: CLI batch, API, notebooks, or a web portal? → interface layer in `ARCHITECTURE.md` §1
21. Where does it run (cloud provider, on-prem HPC, GPU available)? Any data-classification limits? → A10, deployment
22. What are the **interface contracts** with other Digital Twin parts (Network Emulator input format, co-simulation time sync)? → `ARCHITECTURE.md` §3
23. Validation: is there an existing tool (STK, an in-house tool) whose outputs we should match? → test strategy

---

**Owner:** E2EPS software team. When a question is answered, update its
assumption row with the confirmed value and the source (document or person,
date), then change the scenario or code and add a test.

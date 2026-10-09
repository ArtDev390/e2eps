# AI Prompts

This is my prompts in claude.

| Prompt |
|---|
| `Add focused tests for the CLI startup path, KPI calculations, and scenario loading. Cover current expected behavior and the regression fixed in the previous commit. Keep tests deterministic and avoid changing production behavior unless needed for testability.` |
| `Add validation for invalid simulation scenarios. Reject cases such as zero planes, non-positive timestep, and other clearly invalid numeric inputs with explicit errors instead of hangs or incorrect results. Add tests for each validation rule. Keep valid scenarios unchanged.` |
| `Expand the E2EPS module documentation to clearly define inputs, outputs, units, ownership, and why each data item matters. Focus on the implemented modules and their interfaces. Reference assumption IDs where relevant. Keep it architectural, not implementation-heavy.` |
| `Results must not vary with the host timezone, so make time handling explicit and deterministic. Replace crashes and silently ignored inputs with clear errors. Add regression tests for each issue found. Avoid unrelated refactors.` |
| `Strengthen the E2EPS architecture documentation around module boundaries, interfaces, scalability, and performance. Explain how to evolve the Python physics prototype into an operational tool for a 600-satellite constellation. Cover vectorization, partitioning, parallelism, caching, storage, observability, and optional native/GPU acceleration without overdesigning.` |
| `Add CI that runs the full test suite on every push and pull request. Add reproducible executable builds for Windows, Linux, and macOS using the confirmed packaging approach. Keep workflows minimal, cache dependencies where useful, and document produced artifacts.` |
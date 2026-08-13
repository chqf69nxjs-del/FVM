# Stage 7 U3 B2 A1 finite-compression Increment 8C B1-contract binding correction

## Status

`IMPLEMENTATION_CORRECTION_ONLY / FIXED_BEFORE_EXECUTION_RESULT`

Read-back review of the Increment 8C dynamic hook found that its call to the already-fixed Increment 8A root diagnostic supplied `self.adapter.contract`. That adapter contract is not the authoritative B1 critical-state contract argument originally passed to the dynamic hook.

The correction stores the unchanged B1 contract argument during hook construction and binds that exact object into each Increment 8A diagnostic call. It does not modify the B1 contract, the B2 contract, the adapter, Hugoniot physics, Guard-front refinement, root tolerances, chi limits, flux construction, solver update or post-step gates.

The correction is applied through a narrow wrapper around the Increment 8C entry point. The underlying 8-step runner and all evidence requirements remain unchanged.

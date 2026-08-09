# Stage 7 U3 B2 — FVM discharge-face Adapter

## 1. Status

```text
IMPLEMENTATION CANDIDATE
FACE / ONE-STEP AUTHORITY REQUIRED
FINITE-PIPE NOT EXECUTED
```

This increment connects the accepted U3 B1 single-phase discharge component to
the right external face of the conservative one-dimensional FVM solver. It is a
verification-only increment and does not approve a physical CO2 blowdown
boundary.

## 2. Locked authority

```text
Issue:
#135

B2 Contract PR / source / merge:
#136 / 75661d9464ea079203b97e8274321d7d7ab2b9c1 / cffc32c257f58942e602614d69b6dad49bd1add8

B2 Reference PR / source / merge:
#138 / 0e2c8188961175b3c2cd56836296e713735bf8d9 / 4a70a831bb317ea70218e93801c469a12d7e046e

Reference authority run / Artifact:
31203989733 / 9007750537

Reference Artifact ZIP SHA256:
1816e60920052391cb9ffde9242597b56571c9ed113c60ece8aa9f32cdb8c7cd
```

The B1 equation, coefficient placement, critical-search rules, case conditions,
Guard disposition and accepted tolerances remain unchanged.

## 3. Independence boundary

```text
Adapter imports U3 B2 Reference module:       false
shared B2 face-mapping helper:                 false
shared B2 one-step helper:                     false
shared B2 inventory helper:                    false
shared B2 acoustic helper:                     false
accepted B1 Adapter reused as upstream law:    true
Reference used only as comparison target:      true
```

The production-side property path uses CoolProp `AbstractState` through
`Dmass / Umass` for the adjacent static state and `Hmass / Smass` for the
stagnation state. The independent B2 Reference retains its separate `PropsSI`
path.

## 4. Solver integration order

```text
ghost-state Rusanov
→ internal-interface override
→ B2 right external-face override
→ trial conservative update
→ single-phase / positivity validation
→ accepted boundary budget
→ committed conservative state
```

When the optional hook is `None`, the historical solver path is retained.

The candidate time step is limited by:

```text
dt = min(
    existing CFL dt,
    boundary mass-removal dt,
    boundary energy-removal dt,
    t_end - t
)
```

Mass and energy removal remain limited to 10% of the adjacent-cell inventory
per accepted step. A rejected trial is retried with deterministic halving, at
most 12 times. Exhaustion returns
`BOUNDARY_UPDATE_POSITIVITY_FAILURE` without committing boundary budget, solver
state, solver time or step count.

## 5. Direct right-face mapping

```text
A_open   = A_pipe * opening
A_closed = A_pipe - A_open

I_dot_total
  = m_dot_B1 * u_eff_B1
  + p_d * A_open
  + p_i * A_closed

F_right
  = [m_dot_B1 / A_pipe,
     I_dot_total / A_pipe,
     E_dot_B1 / A_pipe,
     0]
```

No discharge ghost primitive is synthesized. The advective momentum stream and
static pressure forces remain separately traceable.

## 6. Exact identity boundary

Closed and locked static-coordinate zero-drop cases retain:

```text
F_right = [0, p_i, 0, 0] exact
```

The B2-02 correction is limited to the exact locked case identity, exact
nominal pressure, opening, discharge coefficient, exact-zero adjacent velocity
and an already-successful raw B1 outcome. The raw B1 outcome and
static/stagnation pressure-coordinate difference remain in provenance.

## 7. Face / one-step authority contract

The dedicated workflow must regenerate the independent Reference from source
identical to pinned SHA `0e2c818...` and then demonstrate:

```text
13 face rows
52 conserved-flux comparisons
1 actual 32-cell / CFL 0.10 FvmSolver step
7 Guard outcomes
12-halving atomic exhaustion
exact single-phase rho*xv = 0
```

Required test layers:

```text
dedicated Adapter tests
related U3 tests
full-repository tests
JUnit skips / failures / errors = 0 / 0 / 0
```

Required evidence includes:

```text
summary.json
runtime_and_git_provenance.json
benchmark_contract.json
event_provenance_contract.json
b1_component_contract.json
adapter_face_results.csv
reference_adapter_face_flux_comparison.csv
one_step_conservative_update_comparison.csv
guard_outcomes.csv
locked_checks.csv
reference_adapter_face_flux_parity.png
report.md
dedicated_junit.xml
related_junit.xml
full_repository_junit.xml
artifact_sha256.txt
```

## 8. Candidate promotion boundary

Only after authoritative evidence and expected-head merge may this increment
support:

```text
u3_b2_fvm_adapter_implemented = true
single_phase_fvm_discharge_mapping_verified = true
```

The following remain false:

```text
u3_b2_finite_pipe_execution_complete = false
single_phase_finite_pipe_coupling_verified = false
u3_b2_verification_benchmark_accepted = false
physical_discharge_boundary_approved = false
two_phase_critical_discharge_accuracy_approved = false
integrated_blowdown_model_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

No mesh/CFL independence, finite-pipe response, acoustic-arrival agreement,
physical accuracy, commercial-code agreement, experimental Validation, design
applicability or production readiness is claimed by this increment.

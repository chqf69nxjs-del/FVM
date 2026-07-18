# V-013 MOC / Linear-Acoustic Cross-Verification Specification

## 1. Status

`PLANNED; IMPLEMENTATION READY`

This document defines Stage 7 / V-013. The implementation shall provide an
independent method-of-characteristics and linear-acoustic comparison path for the
existing single-phase FVM wave and boundary-reflection software.

V-013 is software / numerical verification only. It is not:

- physical Validation;
- design-use acceptance;
- an approved water-hammer or plant-transient model;
- an equipment-fidelity assessment;
- a production alternative to the FVM solver;
- a two-phase, flashing, cavitation, HEM, HNE, ESD, or pump-trip verification.

## 2. Objective

The objective is to determine whether the FVM implementation produces the same
small-amplitude one-dimensional acoustic behaviour as an independently implemented
linear reference path.

The first V-013 increment shall address only:

1. incident-wave propagation in a uniform pipe;
2. reflection at a rigid wall;
3. reflection at a fixed-pressure boundary.

Nonlinear internal-valve cases from V-012 are deliberately excluded. Their Kv law,
complete-closure branch, hydraulic separation, and prescribed opening schedules are
not linear-acoustic reference problems.

## 3. Independence requirements

The value of cross verification depends on implementation independence. The MOC /
linear reference shall therefore obey all of the following rules.

### 3.1 Prohibited dependencies

The reference implementation shall not import or call:

- `FvmSolver`;
- the FVM numerical flux or Riemann-flux implementation;
- production boundary-condition classes;
- internal-interface or valve classes;
- existing FVM case runners;
- FVM timestep logic;
- FVM probe or boundary telemetry recorders;
- a comparison routine that modifies either solution before evaluation.

A failure to maintain these separations is a stop condition.

### 3.2 Explicit reference inputs

The reference path shall receive explicit scalar inputs:

- base pressure `p0`;
- base density `rho0`;
- base sound speed `c0`;
- pipe length `L`;
- initial characteristic profile;
- boundary type;
- requested observation locations and times.

The MOC module shall not call CoolProp. The FVM source case may use
`coolprop_co2`, while the reference receives recorded scalar `rho0` and `c0` values
with provenance. This keeps thermodynamic property evaluation outside the numerical
cross-check.

### 3.3 Independent numerical structure

The reference shall have its own:

- grid definition;
- time-index convention;
- characteristic update;
- boundary reflection formulas;
- reconstruction of pressure and velocity;
- CSV / JSON artifact schema;
- pure unit tests.

Shared generic formatting utilities are allowed only if they cannot affect numerical
values.

## 4. Linear-acoustic model

The reference problem is a constant-coefficient linearization around a uniform,
stationary, single-phase state.

Let

```text
p' = p - p0
u' = u
```

The governing equations are

```text
∂p'/∂t + rho0 c0^2 ∂u'/∂x = 0
∂u'/∂t + (1/rho0) ∂p'/∂x = 0
```

Define pressure-dimension characteristic amplitudes

```text
A+ = 0.5 (p' + rho0 c0 u')
A- = 0.5 (p' - rho0 c0 u')
```

Then

```text
∂A+/∂t + c0 ∂A+/∂x = 0
∂A-/∂t - c0 ∂A-/∂x = 0
```

and reconstruction is

```text
p' = A+ + A-
u' = (A+ - A-) / (rho0 c0)
```

`A+` travels toward increasing `x`; `A-` travels toward decreasing `x`.

## 5. Two independent reference levels

V-013 shall use two related but separately testable references.

### 5.1 Analytical characteristic evaluator

For the specified smooth initial pulse and at most one reflection, evaluate `A+` and
`A-` directly from translated initial profiles and reflection-image formulas.

This evaluator is the primary linear-PDE reference at requested `(x, t)` points. It
shall not use a time-marching solver.

### 5.2 Discrete MOC translator

Implement a nodal MOC update with

```text
Delta t_MOC = Delta x_MOC / c0
CFL_MOC = 1
```

At interior nodes, the characteristic values move exactly one reference cell per
step. Boundary nodes apply the formulas in Section 7.

The discrete MOC path is not automatically labelled as truth. It shall first be
cross-checked against the analytical evaluator at grid-aligned times and locations.

## 6. Common physical profile

The initial implementation shall use a smooth low-amplitude pressure pulse in a
uniform 100 m pipe.

Recommended default profile:

```text
L = 100 m
p0 = 8 MPa
T0 = 280 K
initial velocity = 0 outside the prescribed travelling pulse
pulse type = Gaussian
pulse pressure amplitude = 100 Pa
pulse standard deviation = 2 m
```

For a pure right-going incident wave,

```text
A+(x, 0) = pulse(x)
A-(x, 0) = 0
p'(x, 0) = pulse(x)
u'(x, 0) = pulse(x) / (rho0 c0)
```

The amplitude shall remain within the linear regime. The source-case configuration
shall record:

- maximum `|p'| / p0`;
- maximum acoustic Mach number;
- single-phase state status;
- CoolProp backend name and version for the FVM path.

The initial target limits are descriptive guardrails, not design criteria:

```text
max |p'| / p0 <= 1e-4
max acoustic Mach <= 1e-3
```

## 7. Boundary formulas

### 7.1 Rigid wall

At a wall, `u' = 0`.

At the right boundary, an outgoing `A+` produces

```text
A-_reflected = A+_incident
```

At the left boundary, an outgoing `A-` produces

```text
A+_reflected = A-_incident
```

Expected reflection behaviour:

```text
pressure reflection coefficient = +1
velocity reflection coefficient = -1
```

### 7.2 Fixed-pressure boundary

At a fixed-pressure boundary, `p' = 0`.

At the right boundary,

```text
A-_reflected = -A+_incident
```

At the left boundary,

```text
A+_reflected = -A-_incident
```

Expected reflection behaviour:

```text
pressure reflection coefficient = -1
velocity reflection coefficient = +1
```

### 7.3 Transmissive observation boundary

For an outgoing wave that is not intended to reflect during the accepted observation
window, the incoming characteristic perturbation is zero.

The accepted window shall end before an unintended return from the opposite boundary.

## 8. Verification cases

### V-013A — Incident-wave propagation

Purpose:

- compare FVM, analytical characteristics, and MOC before any boundary reflection;
- verify propagation direction, wave speed, timing, amplitude, and numerical
  diffusion.

Suggested initial pulse centre:

```text
x0 = 20 m
```

Suggested probes:

```text
x/L = 0.35, 0.50, 0.65, 0.80
```

The observation shall end before the pulse reaches the right boundary.

### V-013B — Rigid-wall reflection

Purpose:

- verify positive pressure reflection;
- verify velocity sign reversal;
- compare incident and reflected characteristic amplitudes;
- compare FVM and independent reference fields after one reflection and before a
  second-boundary return.

Suggested pulse centre:

```text
x0 = 65 m
```

The right boundary is rigid. The left boundary shall not contaminate the accepted
window.

### V-013C — Fixed-pressure reflection

Purpose:

- verify negative pressure reflection;
- verify velocity reflection with positive coefficient;
- compare incident and reflected characteristic amplitudes;
- compare FVM and independent reference fields after one reflection and before a
  second-boundary return.

Use the same initial pulse as V-013B and replace only the right boundary type.

## 9. Initial observation matrix

The first observation shall use:

```text
FVM meshes: n = 100, 200, 400
FVM CFL: 0.5
MOC meshes: n = 100, 200, 400
MOC CFL: 1.0
cases: V-013A, V-013B, V-013C
```

The MOC mesh matching an FVM mesh is a convenient comparison grid, not evidence that
one result is exact.

No additional mesh or CFL run shall be added until the initial matrix is reviewed.

## 10. Required matched-sample comparisons

FVM, MOC, and analytical results shall be evaluated at explicitly recorded common
locations and times.

Time matching shall not silently shift one signal to minimize error. Any interpolation
method shall be fixed before results are inspected and recorded in the metrics.

Required field metrics:

- normalized `L1`, `L2`, and `Linf` error for pressure perturbation;
- normalized `L1`, `L2`, and `Linf` error for velocity;
- `A+` and `A-` field errors;
- peak pressure-amplitude ratio and error;
- peak velocity-amplitude ratio and error;
- peak-location error;
- p10 / p50 / p90 arrival-time offsets at each probe;
- fitted propagation-speed error;
- opposite-direction characteristic leakage;
- acoustic-energy-proxy difference.

The acoustic energy proxy is

```text
E_ac = integral [p'^2 / (2 rho0 c0^2) + rho0 u'^2 / 2] dx
```

It is a linear diagnostic, not the FVM conserved total-energy budget.

## 11. Reflection metrics

For V-013B and V-013C, record separately:

- incident pressure and velocity peaks;
- reflected pressure and velocity peaks;
- pressure reflection coefficient;
- velocity reflection coefficient;
- reflected characteristic direction;
- reflection timing relative to the analytical boundary-contact time;
- near-boundary pressure and velocity condition residuals;
- FVM-versus-analytical field norms;
- MOC-versus-analytical field norms;
- FVM-versus-MOC field norms.

Sign checks are mandatory:

| Case | pressure coefficient | velocity coefficient |
|---|---:|---:|
| V-013B rigid wall | positive | negative |
| V-013C fixed pressure | negative | positive |

## 12. Reference self-tests

Before comparison with FVM, the reference implementation shall pass pure tests for:

- `A+ / A-` reconstruction of `p'` and `u'`;
- pure right-going and pure left-going profiles;
- exact one-cell MOC translation at `CFL=1`;
- analytical translation of the Gaussian profile;
- rigid-wall boundary identity;
- fixed-pressure boundary identity;
- pressure and velocity reflection signs;
- MOC-versus-analytical agreement at grid-aligned samples;
- no mutation of input arrays;
- deterministic artifact output.

Reference self-tests shall not import the production FVM solver.

## 13. FVM health requirements

Every FVM run participating in V-013 shall retain the existing software-health gates:

- target time reached;
- maximum step count not exceeded;
- finite histories;
- positive pressure, temperature, density, and sound speed;
- single-phase state retained;
- no required budget fields missing;
- property backend identity recorded;
- `property_backend_design_status = not_approved_for_design_use`;
- no unexpected limiter or Mach-cap activation;
- accepted window free of secondary-boundary contamination.

## 14. Observation policy

The first V-013 implementation is an observation increment.

Do not define final CI-light or design thresholds before reviewing the initial matrix.
The following may be asserted before observation:

- exact analytical and MOC algebraic identities;
- boundary-condition signs;
- reference self-test tolerances near floating-point roundoff;
- finite, positive, and single-phase software-health requirements;
- absence of unintended shared implementation dependencies.

FVM error bands shall be proposed only after the `100 / 200 / 400` results are
available.

The finest FVM or MOC mesh is not an exact solution. The analytical evaluator solves
the specified linearized PDE, not the nonlinear real-fluid equations.

## 15. Required artifacts

Recommended aggregate directory:

```text
verification/v013_moc_linear_acoustic_cross_verification/
```

Required top-level artifacts:

```text
v013_config.json
v013_reference_constants.json
v013_run_plan.json
v013_summary.csv
v013_metrics.json
v013_observation_report.md
```

Required per-case artifacts:

```text
fvm_config.json
fvm_metrics.json
fvm_probe_history.csv
fvm_field_history.npz
moc_config.json
moc_metrics.json
moc_history.npz
analytical_samples.csv
matched_samples.csv
comparison_metrics.json
```

Required figures:

- incident pressure and velocity profiles;
- incident `A+ / A-` profiles;
- probe histories with analytical timing markers;
- field-error norms versus mesh;
- wave-speed and arrival-time error versus mesh;
- rigid-wall incident/reflected profiles;
- fixed-pressure incident/reflected profiles;
- reflection coefficients versus mesh;
- acoustic-energy-proxy comparison.

Plots shall be generated from saved artifacts without rerunning either solver.

## 16. Traceability

Each result row shall record:

- verification item;
- implementation identifier (`fvm`, `moc`, or `analytical`);
- source commit;
- case and output schema version;
- mesh and timestep information;
- `rho0`, `c0`, and their provenance;
- observation-window limits;
- interpolation method, if any;
- backend name and CoolProp version for FVM;
- explicit statement that the MOC path did not call CoolProp;
- physical Validation and design-acceptance flags, both false.

## 17. Stop conditions

Stop implementation, preserve artifacts, and report if:

- the MOC/reference path must import FVM solver or boundary code;
- the same numerical helper computes both the FVM result and the reference result;
- scalar `rho0` or `c0` differs between compared paths without explicit provenance;
- a comparison window contains a secondary boundary return;
- the pulse leaves the stated linear-amplitude regime;
- FVM becomes non-finite, non-positive, or unexpectedly two phase;
- expected characteristic directions or reflection signs are ambiguous;
- reference parameters must be tuned after seeing FVM output;
- time shifting is introduced solely to reduce comparison error;
- final regression bands would need to be chosen before observation review.

## 18. Implementation sequence

1. implement pure characteristic-variable and reconstruction helpers;
2. implement the analytical Gaussian translation evaluator;
3. implement the independent `CFL=1` MOC translator;
4. add rigid-wall and fixed-pressure reference boundary formulas;
5. pass the complete reference self-test suite;
6. define stable V-013 case IDs and run-plan helpers;
7. connect V-013A to a small-amplitude FVM source case without changing solver
   physics;
8. execute and review V-013A propagation;
9. execute and review V-013B rigid-wall reflection;
10. execute and review V-013C fixed-pressure reflection;
11. run the `100 / 200 / 400` observation matrix;
12. generate aggregate metrics and figures from saved artifacts;
13. document whether additional mesh/CFL observation is required;
14. only after review, propose CI-light bands and formalization work.

## 19. Completion criteria for the specification PR

The specification increment is ready for review when:

- the independence rules are explicit;
- governing equations and characteristic conventions are fixed;
- analytical and discrete-MOC reference roles are separated;
- the three initial cases and their windows are fixed;
- comparison metrics, artifacts, and plots are defined;
- stop conditions and implementation order are recorded;
- MASTER VERIFICATION INDEX identifies V-013 as the active Stage 7 item;
- no production solver behaviour is changed.

## 20. Completion criteria for V-013

V-013 may move to `COMPLETE` only after:

- reference self-tests pass;
- all planned FVM, MOC, and analytical artifacts are traceable;
- propagation and both reflection cases are observed;
- mesh behaviour is reviewed without declaring the finest mesh exact;
- reflection directions and signs are correct;
- formal regression bands are justified from observations;
- a permanent CI-light workflow passes without skips;
- a formal report and SHA256 manifest are generated;
- MASTER VERIFICATION INDEX and Stage 7 logs are synchronized.

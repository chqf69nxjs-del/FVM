# Stage 7 — Liquid-to-Two-Phase State-Pair Survey Increment

## Status

`VALIDATED DRAFT; PROPERTY-LEVEL SCREENING ONLY; NOT AN FVM CROSSING`

This increment follows merged PR #67. It creates the first reproducible, logged
survey of pure-CO2 liquid initial-state candidates and ordered left/right pairs
for the later first-order liquid-to-two-phase FVM dry run.

Base:

```text
main: 74b019993823ec4c52f1be38fa8c12580f560686
PR #67: mixed liquid/open-two-phase accepted-state verification EOS
```

## Objective

Build a narrow survey that answers three questions before any FVM step is
attempted:

```text
1. Which pressure/subcooling states are valid LIQUID_CANDIDATE states?
2. Which ordered liquid pairs remain inside the current software and acoustic guards?
3. Which pairs merit a later minimal FVM dry run?
```

The survey must be deterministic and must retain every attempted candidate and
pair, including rejection reasons.

## Deliberate scope boundary

This increment does:

- construct a small fixed set of liquid candidates from pressure and subcooling;
- convert each candidate to canonical `rho/e`;
- re-evaluate each candidate through the reviewed phase path;
- require finite positive pressure, temperature, density, and sound speed;
- retain the current `e >= 0` solver integration constraint;
- screen ordered pairs with a stationary conservative-blend proxy;
- record liquid, endpoint, open-two-phase, forbidden, guard, and backend outcomes;
- rank only property-level candidates for a later dry run;
- write JSON, CSV, Markdown, and NPZ evidence.

This increment does not:

- call `FvmSolver.step()`;
- claim that a conservative blend is an FVM solution;
- connect the transition classifier or projection to `FvmSolver`;
- change Rusanov flux, CFL, boundary, source, budget, EOS, or acoustic algorithms;
- tune tolerances to obtain a preferred outcome;
- freeze Case A or Case B;
- prove liquid-to-two-phase crossing;
- approve production HEM, physical Validation, design use, or an acoustic band.

## Candidate construction

Each `LiquidCandidateSpec` defines:

```text
candidate ID
pressure
subcooling margin
```

The survey obtains the saturated-liquid temperature at the specified pressure:

```text
T_sat = CoolProp(P, Q=0)
T_candidate = T_sat - subcooling
```

It then obtains:

```text
rho = CoolProp(P, T_candidate)
e   = CoolProp(P, T_candidate)
```

The `p/T` pair is used only for state construction. Every candidate is
re-evaluated from canonical `rho/e` before acceptance.

## Candidate acceptance

A candidate is accepted only when all of the following hold:

```text
finite state
rho > 0
e >= 0
temperature above triple temperature
scope_status = supported_candidate
derived region = LIQUID_CANDIDATE
q_eq = 0 by the existing software convention
alpha = 0
finite positive equilibrium sound speed
phase classifier and acoustic center phase agree
```

The survey records distances from the critical temperature, critical pressure,
and triple temperature for traceability. These distances are diagnostic; they
do not replace the existing phase-classification guard.

Candidate outcomes are:

```text
ACCEPTED_LIQUID
ENDPOINT_LANDING
OPEN_TWO_PHASE
FORBIDDEN_REGION
GUARD_FAILURE
BACKEND_FAILURE
```

A rejected candidate is retained in the ledger and prevents every pair that
references it from being presented as a dry-run candidate.

## Fixed first survey

The fixed candidate set covers a deliberately small pressure/subcooling matrix:

```text
5 MPa: 10 K, 5 K subcooling
4 MPa:  5 K, 2 K subcooling
3 MPa:  5 K, 2 K, 1 K subcooling
2 MPa:  5 K, 2 K, 1 K, 0.5 K subcooling
```

The ordered pair set is not a full cross product. It contains controlled
pressure-span and subcooling variants. Each pair carries:

```text
pair ID
left candidate
right candidate
changed parameter
change note
```

The purpose is to preserve a readable trial ledger rather than maximize the
number of combinations.

## Conservative-blend screening proxy

For each accepted stationary endpoint:

```text
U = [rho, 0, rho*e, 0]
```

The survey samples:

```text
U(lambda) = (1 - lambda) U_left + lambda U_right
```

at fixed `lambda` values from 0 to 1.

Every blend is re-evaluated from canonical `rho/e`.

This blend is only a deterministic numerical-mixing proxy. It is not:

```text
an FVM update
an exact Rusanov update
an isentropic path
an isenthalpic path
a physical process trajectory
formal crossing evidence
```

Its only purpose is to identify pairs that deserve the next, more expensive
minimal FVM dry run.

## Blend-point outcomes

Each sampled blend is recorded as one of:

```text
LIQUID_POINT
ENDPOINT_LANDING
OPEN_TWO_PHASE
FORBIDDEN_REGION
GUARD_FAILURE
BACKEND_FAILURE
```

Supported liquid and open-two-phase points use the same existing callable:

```text
estimate_coolprop_equilibrium_sound_speed
```

No runtime branch to CoolProp single-phase `A` is introduced.

Exact saturated-liquid endpoints do not receive an invented acoustic value.
They are recorded as:

```text
ENDPOINT_LANDING
endpoint_acoustic_closure_not_established
```

## Pair outcome

Pair outcome priority is:

```text
BACKEND_FAILURE
GUARD_FAILURE
FORBIDDEN_REGION
OPEN_TWO_PHASE
ENDPOINT_LANDING
ALL_LIQUID
```

A pair is marked `promising_for_dry_run` only when:

```text
pair outcome = OPEN_TWO_PHASE
max screened q_eq >= crossing_evidence_min_quality
every sampled open-two-phase point has finite positive sound speed
```

The fixed evidence threshold remains:

```text
crossing_evidence_min_quality = 1e-6
```

This threshold is a screening/test value only. It is not used by solver, EOS,
projection, or transition-classifier branching.

A promising pair is not an approved Case A. It is only a candidate for the next
minimal FVM dry-run increment.

## Outputs

The runner writes:

```text
stage7_lco2_hem_liquid_state_pair_survey.json
stage7_lco2_hem_liquid_state_pair_survey_candidates.csv
stage7_lco2_hem_liquid_state_pair_survey_pairs.csv
stage7_lco2_hem_liquid_state_pair_survey_blend_points.csv
stage7_lco2_hem_liquid_state_pair_survey.md
stage7_lco2_hem_liquid_state_pair_survey.npz
```

Required summary fields include:

```text
candidate count and status counts
accepted liquid candidate count
pair count and outcome counts
promising pair IDs
highest screened equilibrium quality
screening_is_fvm_solution = false
fvm_step_exercised = false
case_a_frozen = false
case_b_frozen = false
algorithms_or_tolerances_tuned = false
approval flags
```

## Tests

Dependency-free tests use injected fake property, phase, and acoustic evaluators
to cover:

- invalid survey definitions;
- candidate ID and pair-reference validation;
- accepted liquid candidates;
- open-two-phase blend proxy;
- endpoint-only proxy;
- all-liquid proxy;
- vapor and guarded-state rejection;
- negative-energy guard failure;
- backend failure recording;
- acoustic failure recording;
- artifact content and approval flags.

Installed-CoolProp tests run a smaller real-fluid survey and must execute with
zero skips.

The temporary validation workflow additionally runs the complete fixed default
survey and uploads all ledgers.

## Validation evidence — 2026-07-23

Authoritative temporary-workflow validation:

```text
validated head:       cac6887fee4f6accc4be77d59075e0da08fab77d
workflow run:         30008209125
artifact ID:          8563976259
artifact SHA256:      688b7e0c79647a9c203f24317e7404f34e5a471c22852095796f72391ca36f02
CoolProp:             8.0.0
focused tests:        18 passed, 0 skipped
related Stage 7 HEM:  159 passed, 0 skipped
full repository:      601 passed, 0 skipped
failures / errors:    0 / 0
```

The fixed candidate matrix produced:

```text
candidate count:             11
accepted liquid candidates:  11
endpoint candidates:          0
guard failures:               0
backend failures:             0
```

The fixed pair screen produced:

```text
pair count:                   9
ALL_LIQUID:                   1
OPEN_TWO_PHASE:               8
endpoint-only pairs:          0
guard/backend/forbidden:      0
```

The strongest screened pair was:

```text
left:                         5 MPa / 5 K subcooling
right:                        2 MPa / 5 K subcooling
first sampled open fraction:  lambda = 0.1
maximum screened q_eq:        1.3397273027615007e-3
all sampled open acoustics:   finite and positive
```

The moderate-span candidate:

```text
left:                         5 MPa / 5 K subcooling
right:                        3 MPa / 5 K subcooling
first sampled open fraction:  lambda = 0.2
maximum screened q_eq:        5.331295761643359e-4
```

The nearest-span comparison remained liquid at every sampled blend:

```text
left:                         5 MPa / 5 K subcooling
right:                        4 MPa / 5 K subcooling
outcome:                      ALL_LIQUID
maximum screened q_eq:        0
```

These observations nominate the 5-to-2 MPa pair as the leading Case A dry-run
candidate and the 5-to-4 MPa pair as a useful no-crossing comparison candidate.
They do not freeze either case. The next FVM dry-run increment must still test
whether the actual first-order Rusanov update reproduces the screening trend.

Within the fixed survey, increasing pressure span was more influential than
reducing the lower-pressure subcooling margin. This is an observation from the
screening ledger, not a new physical rule or solver branch. No algorithm,
tolerance, or acceptance threshold was changed after observing the result.

## Completion criteria

The increment is review-ready when:

```text
source compiles
git diff --check is clean
dependency-free focused tests pass
installed-CoolProp focused tests pass with zero skips
related Stage 7 HEM tests pass
full repository tests pass
fixed survey runner completes
survey artifacts are uploaded
permanent workflows pass on the final head
temporary validation workflow is removed
final diff contains only source, tests, and verification documents
```

## Approval boundary

```text
verification_only = true
screening_is_fvm_solution = false
fvm_step_exercised = false
case_a_frozen = false
case_b_frozen = false
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
two_phase_acoustic_accuracy_band_approved = false
```

## Next increment after merge

1. review the candidate and pair ledger;
2. select a small number of dry-run candidates without changing algorithms;
3. run a minimal first-order transmissive FVM dry run;
4. vary one case condition at a time and record the outcome;
5. freeze Case A and matched Case B only after repeatable behavior is obtained.

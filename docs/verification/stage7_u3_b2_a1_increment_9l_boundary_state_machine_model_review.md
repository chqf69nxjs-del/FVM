# Stage 7 U3 B2 A1 Increment 9L boundary state machine

## Status

`MODEL_REVIEW_ONLY / TWO_STATE_ENGINEERING_CONTROLLER / WORKING_TOOL_PRIORITY / NOT_VERIFICATION`

Increment 9L generalizes the successful Increment 9K hard continuation into an explicit boundary-state controller. The objective is to remove any solver-step-number switch and let the boundary select its engineering state from the retained outward-branch result.

This increment does not modify the locked B2 contract, B1 equations or search rules, the production B2 adapter, or the `FvmSolver` core.

## Development gates

Increment 9L is divided into two gates.

```text
Gate A: authoritative transition segment
Gate B: initial-state end-to-end integration
```

Gate A starts from the authoritative Increment 9H step-636 state. It must execute at least one accepted `OUTWARD_FLOW` step, detect the retained near-zero branch-exhaustion outcome without inspecting the solver step number, transition once to `ZERO_TRANSFER_CLOSED`, and reach the nominal `2L/c0` target.

Gate B may start only after Gate A passes. It will integrate the same controller into the complete initial-state runner. Gate A is not itself the full initial-state goal and shall not be described as such.

## Gate A authoritative parent

```text
parent source SHA: 8e2825d0a6708dd287276181eee55f9459b04ce1
parent workflow run: 31669680994
parent job: 94351542532
parent artifact: 9169230736
parent artifact name: u3-b2-a1-finite-compression-increment-9h-rerun-31669680994
parent artifact SHA256: a627e2b1720429f79fd80699cb117ddc74c7b931d78c482c27aee98933ece42b
starting solver step: 636
starting solver time: 0.004262873917468169 s
nominal 2L/c0 target: 0.004285834855172021 s
```

This parent was selected because its next accepted state is the already-authoritative outward-flow step 637. The following requested step then reaches the previously observed near-zero branch boundary. This isolates the state transition while proving that the controller is not a hard-coded step-637 closure.

## Controller states

The minimum controller contains only:

```text
OUTWARD_FLOW
ZERO_TRANSFER_CLOSED
```

The only permitted transition is:

```text
OUTWARD_FLOW -> ZERO_TRANSFER_CLOSED
```

The closed state is latched for the remainder of Increment 9L. Re-entry and reverse mass transfer are outside scope.

## OUTWARD_FLOW behavior

`OUTWARD_FLOW` delegates to the existing corrected dynamic finite-compression Hugoniot/B1 boundary path. All existing root, B1, local-admissibility, phase, subsonic, positivity, residual, and conservation gates remain unchanged.

A successful outward step remains an actual `FvmSolver` step. No excluded B1 candidate may be used as a compatibility root or flux state.

## Permitted engineering transition trigger

Gate A permits transition only for the exact retained branch-exhaustion condition:

```text
classification: NO_ADMISSIBLE_ISLAND
message contains: dynamic seeded interval contains no admissible island
```

and only when all of the following are true before state mutation:

```text
at least one OUTWARD_FLOW step has been accepted by this controller
current conserved state is finite
all densities are positive
all internal energies are positive
rho*xv is exact zero
outlet normalized phase is liquid
outlet velocity is not reverse beyond the locked velocity tolerance
outlet Mach is finite and 0 <= Mach < 1
```

The trigger is an engineering branch-end rule. It is not a claim that a mathematically unique zero-flow endpoint has been verified.

The controller shall not inspect `solver.step_count` when deciding the transition.

## Fail-closed outcomes

The following must stop rather than transition:

```text
unknown exception or unknown classification
multiple admissible islands
multiple compatibility roots
nonmonotone root topology
B1 or EOS failure outside the exact retained trigger
phase departure
two-phase transition
nonfinite state
positivity failure
reverse state outside scope
failed conservation or post-step gate
```

A closure transition may not conceal one of these failures.

## ZERO_TRANSFER_CLOSED behavior

The closed branch uses the same provisional engineering wall identity demonstrated in Increment 9K:

```text
F_rho    = 0
F_rho_u  = p_i
F_rho_E  = 0
F_rho_xv = 0
```

where `p_i` is reconstructed from the current adjacent interior state.

After transition:

```text
no B1 state is constructed
no Hugoniot root is constructed
no mass transfer occurs
no advected energy transfer occurs
no vapor transfer occurs
reverse mass transfer is not constructed
```

The interior fluid may respond acoustically to the closed pressure-traction boundary.

## Atomic transition rule

The transition is latched inside the boundary controller before an external flux is returned for the trial. The same closed flux rule is used for any deterministic-halving retry. No solver state, time, budget, or step count may be mutated until the `FvmSolver` accepts the trial.

The transition event record must include:

```text
state before
state after
requested solver step
solver time
exception type
classification
message
outlet pressure, velocity, Mach, and phase
state SHA256 before transition
```

## Gate A success criteria

Gate A passes only if:

```text
parent step-636 state is reproduced exactly
no transition decision uses a solver-step-number condition
at least one actual OUTWARD_FLOW step is accepted
exactly one OUTWARD_FLOW -> ZERO_TRANSFER_CLOSED transition occurs
at least one actual ZERO_TRANSFER_CLOSED step is accepted
no re-entry or branch chatter occurs
nominal 2L/c0 is reached by actual FvmSolver steps
final step is target-clipped
all per-step conservation gates pass
all states remain finite and positive
all cells remain normalized liquid
rho*xv remains exact zero
closed-branch mass, energy, and vapor fluxes are exact zero
closed-branch momentum flux equals current interior static pressure exactly
```

A passing Gate A result may be called:

```text
INCREMENT 9L GATE A TRANSITION WORKING SLICE
```

It is not the full initial-state Gate B result.

## Required evidence

```text
state_machine_steps.csv
boundary_state_history.csv
transition_event.json
authority_verification.json
technical_issue.json
state_machine_full_horizon_states.npz
summary.json
report.md
artifact_sha256.txt
```

## Gate B target

After Gate A passes, Gate B shall connect the same state machine to the complete `LIQUID_SMALL_DROP` initial-state trajectory. The intended sequence is:

```text
initial state
-> retained outward boundary path
-> automatically detected near-zero branch exhaustion
-> ZERO_TRANSFER_CLOSED hold
-> nominal 2L/c0
```

Gate B must reuse the controller proved by Gate A rather than adding a second transition rule.

## Formal-state boundary

Regardless of Gate A or Gate B execution, retain:

```text
finite_compression_branch_approved = false
multi_step_finite_compression_continuation_authorized = false
full_two_l_over_c0_passed = false
formal_state_promoted = false
u3_b2_finite_pipe_execution_complete = false
single_phase_finite_pipe_coupling_verified = false
u3_b2_verification_benchmark_accepted = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

A separate verification and validation program is required before those states may change.

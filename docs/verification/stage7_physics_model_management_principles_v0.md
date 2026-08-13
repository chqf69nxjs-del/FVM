# Stage 7 Physics Model Management Principles v0

## Status

`DESIGN PRINCIPLES / ARCHITECTURE GUIDANCE / NOT VERIFICATION`

## Purpose

The transient solver is not required to force every physically distinct regime through one universal closure model. When a retained model leaves its documented scope, the tool may transition to another engineering or physics model that is better suited to the new regime.

The transition itself is part of the model and must therefore be explicit, conservative, auditable, and bounded in complexity.

## Principle 1 — conservation laws are the common currency

Where practical, model transitions shall preserve a common conservative state such as:

```text
mass
momentum
total energy
transported composition / phase inventory variables
```

Changing the active physics model shall not by itself create or destroy conserved quantities.

If two models use different primitive variables or degrees of freedom, an explicit transition map shall reconstruct the receiving-model variables from the conserved state and documented closure relations.

## Principle 2 — model scope is explicit

Every model shall document at least:

```text
applicable thermodynamic regime
applicable flow direction / Mach scope
required EOS domain
required constitutive relations
entry conditions
exit conditions
known unsupported states
fail-closed conditions
```

The project shall prefer a small model with a clear scope over an apparently universal model whose validity cannot be established.

## Principle 3 — transitions are classification driven

A transition shall be triggered by a state or model classification, not by a hard-coded solver step, elapsed-time identity, or case-specific checkpoint.

Preferred pattern:

```text
state reconstruction
    -> applicability / admissibility classification
    -> retained transition rule
    -> receiving-model state map
    -> transition gates
    -> solver continuation
```

Unexpected exceptions or unknown classifications are not transition rules and remain fail-closed.

## Principle 4 — continuity is checked, not assumed

At each model transition, distinguish:

```text
conservation continuity
thermodynamic consistency
primitive-variable continuity
flux continuity
wave / characteristic compatibility
```

Not every primitive variable must be mathematically continuous across a genuine physical regime change, but any jump introduced solely by the numerical model switch shall be identified and justified.

A transition shall record pre- and post-map residuals for the conserved quantities that are intended to remain continuous.

## Principle 5 — add degrees of freedom only when required

The preferred development sequence is:

```text
lowest adequate model freedom
    -> identify a demonstrated missing mechanism
    -> add the minimum new degree of freedom
    -> define closure and transition map
    -> establish a working vertical slice
    -> verify / validate before further expansion
```

Examples:

```text
single-phase -> homogeneous two-phase
homogeneous two-phase -> drift / slip model
drift model -> two-fluid model
```

The more detailed model shall not be introduced merely because it is more general.

## Principle 6 — separate orthogonal regime axes

Avoid one combinatorially large state machine. Represent physically different concerns as separate model axes where practical.

Candidate axes:

```text
Thermodynamic regime
    LIQUID / TWO_PHASE / VAPOR

Bulk-flow model
    SINGLE_PHASE / HEM / DRIFT_FLUX / TWO_FLUID

Boundary regime
    OUTWARD / CRITICAL / ZERO_TRANSFER_CLOSED / REVERSE

Heat-transfer regime, when required
    SINGLE_PHASE / NUCLEATE_BOILING / FILM_BOILING / ...
```

Only combinations explicitly supported by the model manager are admissible.

## Principle 7 — control chatter and hysteresis explicitly

If a transition can reverse, entry and exit criteria shall be treated independently when needed.

Before enabling re-entry:

```text
hysteresis policy
minimum hold criteria if physically justified
chatter detection
transition-count diagnostics
conservation checks across repeated transitions
```

shall be defined.

Until a re-entry model is justified, a one-way transition may be retained as an explicit engineering limitation.

## Principle 8 — numerical search and physical model limits remain distinct

The tool shall distinguish at least:

```text
physical / model scope departure
numerical root-search limitation
implementation / bookkeeping defect
workflow / infrastructure defect
```

A numerical-search failure shall not automatically be reinterpreted as a physical transition. A physical transition requires a predeclared supported classification or an explicitly documented provisional engineering closure.

## Principle 9 — provisional engineering closures are allowed but labelled

When strict verification is not presently achievable and project value favors a working tool, a provisional engineering model may be used if:

```text
the unresolved issue is recorded
the engineering assumption is explicit
its application scope is bounded
conservation and positivity gates remain active
unsupported behavior is fail-closed
the result is not promoted to VERIFIED / ACCEPTED / VALIDATED / APPROVED
```

This mechanism is a controlled technical-debt decision, not evidence that the unresolved physics has been solved.

## Principle 10 — model transitions are first-class evidence

Every transition-capable run should emit an event record containing, where applicable:

```text
solver time and observed step
from / to regime
trigger classification
pre-transition conserved state identity
transition map used
post-transition conserved state identity
conservation-map residuals
EOS / phase consistency
failed candidate used as root or flux = false when relevant
absolute step-number trigger used = false
re-entry / reverse-flow policy
```

The step number is evidence, not the transition criterion.

## Current minimal demonstrated pattern

Increment 9L provides the first end-to-end engineering example of this architecture:

```text
OUTWARD_FLOW
    THREE_BRANCH_WAVE_MODEL
        connected rarefaction
        neutral endpoint
        weak compression

    -> FINITE_COMPRESSION_MODEL_REQUIRED

OUTWARD_FLOW
    GENERAL_EOS_FINITE_COMPRESSION

    -> expected near-zero branch exhaustion classification

ZERO_TRANSFER_CLOSED
```

The public boundary transition is currently one-way. Re-entry and reverse mass transfer remain outside the demonstrated scope.

## Two-phase development implication

A future liquid-to-two-phase increment should not begin by adding all possible two-phase freedoms. A preferred staged route is:

```text
single-phase liquid
    -> explicit phase-boundary transition map
    -> minimal homogeneous two-phase working slice
    -> verification of transition conservation / EOS consistency
    -> only then assess demonstrated need for slip / drift freedom
    -> only then assess demonstrated need for two-fluid freedom
```

This preserves flexibility while controlling model-space growth.

## Status discipline

Model-manager implementation state and physical authority remain separate:

```text
IMPLEMENTED
WORKING VERTICAL SLICE
VERIFIED
ACCEPTED
VALIDATED
APPROVED
```

A successful model transition or end-to-end calculation does not automatically promote any later state.

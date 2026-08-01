# Stage 7 Gate 9 D2 — Exact production-Rusanov decomposition, increment 1

## Status

```text
Issue:                         #110
prerequisite D1:               merged through PR #116
increment:                     D2 / CFL 0.10 identity column
production flux expression:    UNCHANGED
EOS calls for decomposition:   NONE
wave-speed recomputation:      NONE
CFL 0.05 / 0.025 execution:    NOT STARTED
D3 acoustic history:           NOT STARTED
D4 event window:               NOT STARTED
Gate 9 execution complete:     false
```

## Purpose

D1 proved that retained-result instrumentation can be added without changing the
CFL `0.10` solver result, but its `RAW_POST_FVM` conservative values are reconstructed
from retained cell fields. Those reconstructed values are not sufficient for the
locked D2 reconstruction guard.

D2 therefore observes the Rusanov calculation at the production evaluation point,
after the existing production flux has been computed and before it is returned to
the solver. It captures the exact arrays already present there:

```text
U_left
U_right
F_left
F_right
a_max
production Rusanov flux
```

The diagnostic decomposition uses only these captured arrays. It does not call the
EOS, recalculate sound speed, replace the numerical flux, or write into solver state.

## Read-only observer mechanism

`flux.py` retains the existing Rusanov expression:

\[
F_{\mathrm{prod}}
= \frac{1}{2}(F_L+F_R)
- \frac{1}{2}a_{\max}(U_R-U_L).
\]

After `F_prod` is computed, an optional `ContextVar` observer receives independent
copies of the input and output arrays. Every copy is marked non-writeable. The
observer is disabled by default and is restored exactly on context exit, including
nested contexts.

This design avoids changes to:

```text
FvmSolver constructor
FvmSolver step equation
pipeline case configuration
boundary implementation
phase classifier
quality projection
sound-speed evaluator
formal stop logic
```

## Diagnostic reconstruction

For each captured focused interface, D2 computes:

\[
F_{\mathrm{central}}=\frac{1}{2}(F_L+F_R),
\]

\[
F_{\mathrm{dissipative}}
=-\frac{1}{2}a_{\max}(U_R-U_L),
\]

\[
F_{\mathrm{reconstructed}}
=F_{\mathrm{central}}+F_{\mathrm{dissipative}}.
\]

The normalized residual is the locked Gate 9 definition:

\[
r = \max_i
\frac{|F_{\mathrm{reconstructed},i}-F_{\mathrm{prod},i}|}
{\max(1,
|F_{\mathrm{reconstructed},i}|,
|F_{\mathrm{prod},i}|,
|F_{\mathrm{central},i}|,
|F_{\mathrm{dissipative},i}|)}.
\]

The fixed acceptance guard is:

```text
r <= 5e-13
```

A violation is categorized as a D2 reconstruction failure; it is not repaired by
changing a flux, state, threshold, or tolerance.

## Interface mapping

For the fixed 32-cell, two-ghost-cell case, the observed extended-array flux indices
are mapped as follows:

| Gate 9 interface | observed flux index | left cell | right cell |
|---|---:|---:|---:|
| `27|28` | 29 | 27 | 28 |
| `28|29` | 30 | 28 | 29 |
| `29|30` | 31 | 29 | 30 |
| `30|31` | 32 | 30 | 31 |
| `RIGHT_BOUNDARY` | 33 | 31 | prescribed ghost state |

The interface evaluation occurs at the retained `time_before_s`. The record also
retains the accepted step `dt` and the production-flux contribution over `dt/dx`:

```text
left adjacent cell:   -(dt/dx) F_prod
right adjacent cell:  +(dt/dx) F_prod
```

The prescribed right-boundary state is retained as the right conserved state, but
there is no right internal-cell increment.

## Increment-1 execution boundary

This increment executes only the immutable Gate 8 CFL `0.10` identity column. It
requires exact reproduction of:

```text
formal outcome:      ACCEPTED_FIRST_CROSSING
candidate step:      125
candidate time:      0.0007999325695335248 s
candidate cell:      29
maximum q_eq:        3.773646403587342e-06
```

Diagnostics OFF and ON must also agree exactly in:

```text
formal identity and failure reason
step count and final time
candidate metadata
final state SHA and run signature
full time history
full pressure history
full accepted-state history
```

The expected D2 evidence volume is:

```text
125 production Rusanov evaluations
5 focused interfaces per accepted step
625 focused interface records
```

## Explicitly pending

D2 increment 1 does not provide:

```text
CFL 0.05 or 0.025 interface histories
candidate-preceding/following eight-step extraction
exact first/second projection intermediate arrays
acoustic trial and twelve-halving history
cross-CFL correlation labels
root-cause approval
mitigation approval
physical validation
design-use acceptance
production activation
```

No causal statement about numerical dissipation is authorized from the CFL `0.10`
column alone.

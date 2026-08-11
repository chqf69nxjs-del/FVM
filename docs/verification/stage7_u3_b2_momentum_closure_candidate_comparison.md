# Stage 7 U3 B2 — momentum closure candidate comparison

## 1. Status and governance boundary

```text
review type:                         MODEL_REVIEW_ONLY
source main:                         aa108961762c9ae70ee9940405024eb5188064b8
parent model-review commit:          d2e3c9a8b4b4691feb7e44ec43b8b392f54c564e
B2 Contract modification:            none
B1 modification:                     none
Adapter modification:                none
solver modification:                 none
tolerance modification:              none
formal finite-pipe promotion:        none
physical validation:                 false
design use:                          false
production activation:               false
```

This note compares candidate momentum closures after the control-volume review
identified that the accepted B1 `momentum_stream_transfer` is a lumped stream
quantity and is not, by itself, sufficient to define the pipe-side Euler
momentum port of an unresolved restriction.

No candidate is accepted by this note.  The purpose is to eliminate closures
which fail exact identities or basic limiting behaviour before any Contract or
production code is changed.

---

## 2. Common notation

```text
P        upstream pipe/component interface
R        unresolved restriction/orifice/nozzle region
E        downstream discharge-stream section
A        A_pipe
Ao       A_open
Ac       A_closed = A - Ao
f        Ao/A
p_i      adjacent pipe-cell static pressure
u_i      adjacent pipe-cell velocity
h0_i     adjacent pipe-cell stagnation enthalpy
p_d      B1 retained discharge-state pressure
u_eff    B1 effective discharge-stream velocity
m_dot    positive outward B1 mass-transfer rate
Pi_P     pipe-side momentum port
Pi_E     downstream stream-plus-pressure momentum port
R_w      net axial force exerted by unresolved restriction walls/geometry on fluid
```

For the downstream open stream, the natural control-volume quantity is

$$
\Pi_E = \dot m u_{\mathrm{eff}} + p_d A_o.
$$

When `Ao < A`, pressure acting on the blocked/solid part belongs to the
restriction-wall force bookkeeping rather than to a downstream fluid stream.
The restriction control volume satisfies

$$
\boxed{\Pi_E = \Pi_P + R_w}.
$$

Thus a pipe-side port and a downstream stream port need not be identical.

---

## 3. Five mandatory checks

Every candidate is compared against the following result-independent checks.

### C1 — closed identity

For `Ao = 0`,

$$
\dot m=0,
\qquad
\mathbf F_P = [0,\ p_i,\ 0,\ 0]^T
$$

must hold exactly at the pipe boundary.

### C2 — zero-pressure-drop identity

For finite opening, `u_i = 0`, and `p_b = p_i`, the same exact wall identity
must be recovered.

### C3 — forward small-pressure-drop limit

For `Delta p = p_i-p_b > 0` and an initially stationary uniform pipe, the
closure must not impose a deterministic initial **negative** pipe velocity.
The intended response is a pressure reduction at the outlet followed by a
positive-outward rarefaction velocity.

### C4 — choked compatibility

The closure must preserve the accepted B1 choked mass/energy law and its
below-critical plateau.  A pipe-side momentum treatment may change, but it may
not silently alter B1 critical pressure, `m_dot`, coefficient placement, or
`m_dot*h0`.

### C5 — global momentum conservation

For a larger control volume containing the pipe-side port, restriction and
outlet stream,

$$
\Pi_E-\Pi_P-R_w=0
$$

must close with an explicit and auditable reaction term.  A closure is not
allowed to make the restriction reaction disappear merely by identifying P and
E without justification.

---

## 4. Existing B2 direct mapping — baseline for comparison

The locked B2 v1 mapping uses

$$
\Pi_P^{\mathrm{current}}
=\dot m u_{\mathrm{eff}}
+p_d A_o+p_iA_c.
$$

At the initially stationary uniform pipe,

$$
\Pi_L\simeq p_i A,
$$

so

$$
\Pi_P^{\mathrm{current}}-\Pi_L
=\dot m u_{\mathrm{eff}}-(p_i-p_d)A_o.
$$

For the liquid small-drop B0/B1 law,

$$
\dot m u_{\mathrm{eff}}
=2C_d^2\Delta p A_o,
$$

therefore

$$
\boxed{
\Pi_P^{\mathrm{current}}-\Pi_L
=(2C_d^2-1)\Delta p A_o
}.
$$

With the locked `Cd=0.8`, this coefficient is `+0.28`, which forces a
negative first-step momentum in B2-10A.  The diagnostic reproduced the update
with zero prediction residual.

Classification:

```text
C1 closed identity:                  PASS
C2 zero-drop identity:               PASS
C3 small-drop forward sign:          FAIL (structural for Cd > 1/sqrt(2))
C4 choked compatibility:             PARTIAL (B2-10C happened to complete)
C5 global momentum reaction ledger:  FAIL / NOT EXPLICIT
```

The current mapping therefore cannot be promoted as a finite-pipe closure
without Contract-level revision.

---

# Candidate A — separated upstream pipe port

The control-volume architecture is changed conceptually, not numerically yet:

```text
pipe FVM        P |        unresolved R        | E      discharge stream
------------------|----------------------------|------------------------>
                  Pi_P                         Pi_E
                         R_w = Pi_E - Pi_P
```

B1 continues to provide the component mass and energy transfers and the
observable downstream stream quantity.  B2 separately defines the upstream
pipe port and records the implied restriction reaction.

This architecture has two materially different sub-options.

---

## 5. Candidate A0 — upstream conservative sink port

Define the pipe-side conservative transfer as

$$
\boxed{
\mathbf F_P^{A0}
=
\begin{bmatrix}
\dot m/A\\
(\dot m u_i+p_iA)/A\\
\dot m h_{0,i}/A\\
0
\end{bmatrix}
}.
$$

This means that the component removes mass carrying the **local upstream
specific momentum** `u_i` and stagnation enthalpy `h0_i`.  It is a lumped
component sink port.  It is not claimed to be a primitive Euler boundary state
because generally

$$
\dot m \ne \rho_i u_i A.
$$

### 5.1 Exact local source behaviour

Let

$$
q=\frac{\dot m}{A\Delta x}>0
$$

be the volumetric mass-removal rate associated with the last cell.  Ignoring
neighbouring-face transport for this local argument,

$$
\frac{d\rho}{dt}=-q,
$$

$$
\frac{d(\rho u)}{dt}=-q u,
$$

$$
\frac{d(\rho E)}{dt}=-q h_0.
$$

The first two equations give

$$
\boxed{\frac{du}{dt}=0}
$$

for the sink operation itself: removing mass at local specific momentum does
not give the remaining fluid an artificial recoil.

Using

$$
E=e+\frac{u^2}{2},
\qquad
h_0=e+\frac{p}{\rho}+\frac{u^2}{2},
$$

and `du/dt=0`, the energy equation gives

$$
\frac{de}{dt}
=\frac{p}{\rho^2}\frac{d\rho}{dt}.
$$

From the Gibbs relation

$$
de=Tds+\frac{p}{\rho^2}d\rho,
$$

it follows that

$$
\boxed{\frac{ds}{dt}=0}
$$

for the local sink operation.  Thus the mass/enthalpy removal produces an
isentropic density/pressure reduction rather than a direct velocity kick.
For a stable single-phase state with

$$
c_s^2=\left(\frac{\partial p}{\partial\rho}\right)_s>0,
$$

one obtains

$$
\boxed{\frac{dp}{dt}=c_s^2\frac{d\rho}{dt}<0}.
$$

The expected sequence is therefore

```text
mass + h0 removal
→ local isentropic pressure decrease
→ pressure gradient into the outlet cell
→ positive-outward acceleration from the FVM dynamics
→ rarefaction propagation upstream
```

rather than an imposed negative recoil.

### 5.2 Reaction ledger

Use the downstream B1 stream port

$$
\Pi_E=\dot m u_{\mathrm{eff}}+p_dA_o
$$

and the upstream A0 port

$$
\Pi_P^{A0}=\dot m u_i+p_iA.
$$

Then

$$
\boxed{
R_w^{A0}=\Pi_E-\Pi_P^{A0}
}
$$

is retained explicitly as the unresolved restriction force on the fluid.
For a closed element it naturally contains the blocked-face pressure reaction;
for an open element it contains contraction/nozzle/valve reaction effects not
resolved by the pipe mesh.

### 5.3 Five-check result

```text
C1 closed identity:                  PASS exact
C2 zero-drop identity:               PASS exact
C3 small-drop forward sign:          PASS qualitative / analytic no-recoil
C4 choked compatibility:             PASS at B1-law level; finite-pipe test required
C5 global momentum conservation:     PASS bookkeeping with explicit R_w
```

Important limitation:

```text
A0 is a conservative component sink port.
A0 is NOT yet justified as a true local Euler face state.
```

Therefore A0 is suitable as a **diagnostic/minimal coupling candidate**, not yet
as the preferred physical boundary formulation.

---

## 6. Candidate A1 — characteristic-compatible upstream Euler port

A physically stronger version of the same separated-port architecture is to
solve an actual pipe-side boundary state

$$
(\rho_P,u_P,p_P,h_P)
$$

such that the Euler flux at P is

$$
\boxed{
\Pi_P^{A1}=\rho_Pu_P^2A+p_PA
}
$$

and the mass/energy ports satisfy

$$
\dot m=\rho_Pu_PA,
$$

$$
\dot E=\dot m\left(h_P+\frac{u_P^2}{2}\right).
$$

The state must also be compatible with the outgoing characteristic information
from the adjacent pipe and with the B1 component flow law.  In other words,
`m_dot` is not simply pasted onto an unrelated cell-centre state; the boundary
state is solved so that pipe acoustics and component discharge are mutually
consistent.

A1 is intentionally not fully specified in this note.  The next derivation
must determine a minimal nonlinear boundary system using, for example:

```text
interior outgoing characteristic / Riemann invariant
single-phase EOS
pipe-side total enthalpy relation
B1 component mass-flow relation
external back pressure / choking classification from B1
```

without modifying the accepted B1 component law.

### 6.1 Five-check result

```text
C1 closed identity:                  REQUIRED / constructible
C2 zero-drop identity:               REQUIRED / constructible
C3 small-drop forward sign:          EXPECTED from rarefaction-compatible state
C4 choked compatibility:             COMPATIBLE in principle; nonlinear solve required
C5 global momentum conservation:     PASS architecture with explicit R_w
```

A1 is the **leading physical-model direction**, but it is not yet Contract-ready
because the characteristic boundary equations have not yet been locked or
verified.

---

# Candidate B — localized restriction source / interface jump

## 7. Definition

Retain distinct upstream and downstream momentum ports and insert their jump as
an interface/source contribution:

$$
\Pi_E-\Pi_P=R_w.
$$

The pipe-side numerical flux remains an Euler-compatible flux.  The unresolved
restriction contributes an explicit momentum source/jump rather than being
collapsed into the same face value.

Conceptually:

```text
left pipe flux → [ interface R ] → downstream stream port
                    + R_w
```

This is attractive for an internal valve/restriction element because it makes
the force jump auditable and allows an equal-and-opposite structural load to be
reported separately.

However, a source/jump formulation still needs a constitutive rule for either
`Pi_P` or `R_w`.  Merely adding a source variable does not close the model.

### Five-check result

```text
C1 closed identity:                  PASS if wall branch is explicit
C2 zero-drop identity:               PASS if zero-flow source is exact
C3 small-drop forward sign:          CONDITIONAL on Pi_P / R_w closure
C4 choked compatibility:             COMPATIBLE with unchanged B1
C5 global momentum conservation:     PASS by construction when jump is audited
```

Classification:

```text
physically clean architecture
but underdetermined without the same pipe-side closure required by A1
```

Candidate B is therefore complementary to A1 rather than a complete alternative.

---

# Candidate C — explicit short nozzle/orifice control volume

## 8. Definition

Add a small resolved or lumped region R between the pipe and discharge stream.
The region carries its own state and momentum balance, potentially including:

```text
area variation
pressure distribution
wall axial force
loss / entropy production
critical transition
possibly a vena-contracta section
```

Then P and E are physically separated and the acceleration from pipe velocity
to discharge velocity occurs inside the model rather than instantaneously at a
single boundary face.

### Five-check result

```text
C1 closed identity:                  PASS in a well-posed implementation
C2 zero-drop identity:               PASS in a well-posed implementation
C3 small-drop forward sign:          PASS expected from resolved pressure acceleration
C4 choked compatibility:             PASS possible, but requires a new nozzle/restriction model
C5 global momentum conservation:     PASS naturally when wall forces are retained
```

Cost / governance impact:

```text
new geometry assumptions
new state variables or component dynamics
new loss model
new Verification contract
likely new Validation burden
```

Candidate C is the most physically explicit path, but is disproportionate as
the first repair of the current B2 single-phase coupling benchmark.

---

# Candidate D — coefficient decomposition

## 9. Definition

Replace the interpretation of a single `Cd` by physically separate
coefficients/geometry, for example contraction and velocity effects in an
orifice-like model:

```text
Cd = function(Cc, Cv, geometry, flow regime, ...)
A_stream != A_open in general
u_stream need not equal Cd*u_ideal as a literal local velocity
```

Such a decomposition may permit construction of a more defensible downstream
state and wall reaction.

However the accepted B0/B1 contract provides only the lumped `Cd`; it does not
provide a unique `Cc`, `Cv`, vena-contracta area, or axial wall-force law.
Different decompositions can reproduce the same mass-flow coefficient while
producing different momentum ports.

### Five-check result

```text
C1 closed identity:                  PASS possible
C2 zero-drop identity:               PASS possible
C3 small-drop forward sign:          UNDETERMINED with Cd alone
C4 choked compatibility:             REQUIRES compressible extension / new data
C5 global momentum conservation:     REQUIRES explicit force/geometry closure
```

Candidate D is therefore **not identifiable from the current accepted inputs**.
It belongs to later physical-model refinement / Validation, not the minimal B2
Verification repair.

---

## 10. Comparison matrix

| Candidate | C1 closed | C2 zero-drop | C3 small-drop | C4 choked | C5 global momentum | Current disposition |
|---|---|---|---|---|---|---|
| Existing direct B2 | PASS | PASS | **FAIL structural** | PARTIAL | reaction hidden | contract review required |
| A0 upstream sink port | PASS | PASS | PASS analytic no-recoil | compatible, test needed | PASS with `R_w` ledger | diagnostic/minimal candidate |
| A1 characteristic upstream port | required/passable | required/passable | expected PASS | compatible in principle | PASS with `R_w` ledger | **leading physical direction** |
| B localized interface source | PASS possible | PASS possible | conditional | compatible | PASS | architecture, needs A1-like closure |
| C explicit restriction CV | PASS | PASS | PASS expected | possible | PASS | future/high-cost path |
| D coefficient decomposition | possible | possible | underdetermined | new model required | closure required | defer |

---

## 11. Important refinement of the previous upstream-port proposal

The earlier control-volume review suggested

$$
\Pi_P=\dot m u_i+p_iA
$$

as a natural upstream port.  The present comparison refines that statement:

> This expression is well behaved as a **conservative lumped sink port**, but it
> must not be mislabeled as a literal Euler face state unless
> `m_dot = rho_i*u_i*A` also holds.

That distinction matters because the project is specifically verifying a
compressible finite-volume pipe.  The cleanest physical endpoint is therefore
not to stop at A0, but to use A0 as a diagnostic bridge while deriving A1, a
characteristic-compatible upstream boundary state.

---

## 12. Leading model architecture after the five checks

The five checks support the following architecture as the next derivation target:

```text
B1 component remains immutable
        |
        | supplies m_dot, h0 transfer, choking classification,
        | downstream stream diagnostics
        v
solve pipe-side characteristic-compatible state at P
        |
        | produces Euler-consistent F_P
        v
FVM pipe

separately:
R_w = Pi_E - Pi_P
        |
        +--> restriction/support reaction diagnostic
```

This architecture separates three concepts which the current B2 direct mapping
collapsed together:

```text
1. pipe-side Euler transport
2. discharge-stream momentum
3. restriction / support reaction
```

No numerical value or tolerance is changed by making this distinction.

---

## 13. Next derivation required before any Contract revision

The next model-review increment should derive the minimal A1 boundary system.
It must answer, before code is written:

1. Which characteristic invariant is inherited from the last interior cell for
   subsonic outward discharge?
2. Which pipe-side thermodynamic quantity is held along the boundary relation
   (`h0`, entropy, or another explicitly justified pair)?
3. How is the B1 algebraic mass-flow law coupled to the unknown boundary state
   without double-using the cell-centre pressure?
4. How does the system change between unchoked and choked B1 classification?
5. Does the resulting boundary state recover exact closed and zero-drop
   identities and the linear acoustic sign `delta p < 0`, `delta u > 0`?
6. Is there a unique admissible single-phase root over the locked B2 state
   families?

Only after those questions are answered should a Contract-revision candidate be
written.

---

## 14. Formal state remains unchanged

```text
u3_b2_fvm_adapter_implemented = true
single_phase_fvm_discharge_mapping_verified = true

u3_b2_finite_pipe_execution_complete = false
single_phase_finite_pipe_coupling_verified = false
u3_b2_verification_benchmark_accepted = false

physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

# Stage 7 U3 B2 — characteristic-compatible upstream port derivation

## 1. Status and governance boundary

```text
review type:                         MODEL_REVIEW_ONLY
source main:                         aa108961762c9ae70ee9940405024eb5188064b8
candidate architecture:              A1 characteristic-compatible upstream port
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

This note derives a minimal pipe-side boundary system for the leading A1 model
architecture identified by the momentum-closure candidate comparison.  It does
not approve the model and does not modify the locked B2 Contract.

The derivation is restricted to the single-phase inviscid one-dimensional
Euler structure already used by the B2 finite-pipe benchmark.

---

## 2. Boundary characteristic count

For one-dimensional Euler flow, the characteristic speeds are

$$
u-c,\qquad u,\qquad u+c.
$$

At the **right boundary** with subsonic outward flow

$$
0\le u<c,
$$

the signs are

$$
u-c<0,
\qquad
u>0,
\qquad
u+c>0.
$$

Thus one acoustic characteristic enters the computational domain from the
boundary while the entropy/contact characteristic and the opposite acoustic
characteristic carry information out of the domain.  Only one independent
physical relation should therefore be supplied by the external component for a
subsonic outlet; the rest of the boundary state is constrained by interior
characteristic information.

For U3 B2, the natural external physical relation is the accepted B1 component
mass-flow law.

---

## 3. Interior quantities and unknown pipe-side state

Let the adjacent last-cell primitive state be

$$
(\rho_i,u_i,p_i,s_i,h_i,c_i).
$$

The unknown pipe-side state immediately upstream of the unresolved restriction
is

$$
(\rho_P,u_P,p_P,s_P,h_P,c_P).
$$

The boundary area at P is the full pipe area

$$
A=A_{\mathrm{pipe}}.
$$

The restriction opening remains a B1/B2 component parameter

$$
A_o=fA.
$$

The downstream external pressure remains `p_b` and the accepted B1 coefficient
placement, critical search, guards and tolerances remain unchanged.

---

## 4. Entropy carried from the pipe interior

For outward subsonic flow, the entropy/contact characteristic leaves the pipe
domain.  The minimal inviscid single-phase boundary therefore inherits

$$
\boxed{s_P=s_i}.
$$

This is not an added external boundary condition; it is interior information.

For any trial pressure `p_P`, the EOS on the inherited isentrope determines

$$
\rho_P=\rho(p_P,s_i),
$$

$$
h_P=h(p_P,s_i),
$$

$$
c_P=c(p_P,s_i).
$$

All states must remain in the locked B2 single-phase family.

---

## 5. Outgoing acoustic invariant inherited from the interior

For the isentropic one-dimensional Euler acoustic subsystem,

$$
\frac{\partial u}{\partial t}
+u\frac{\partial u}{\partial x}
+\frac{1}{\rho}\frac{\partial p}{\partial x}=0,
$$

$$
\frac{\partial p}{\partial t}
+u\frac{\partial p}{\partial x}
+\rho c^2\frac{\partial u}{\partial x}=0.
$$

Along the right-running characteristic `dx/dt=u+c`, these equations give the
compatibility relation

$$
du+\frac{dp}{\rho c}=0.
$$

At a right subsonic boundary, this characteristic carries information from the
interior to the boundary.  Therefore define, on the inherited entropy `s_i`,

$$
\Phi(p;s_i)
=\int^{p}\frac{dp'}{\rho(p',s_i)c(p',s_i)}.
$$

The boundary relation is

$$
\boxed{
u_P+\Phi(p_P;s_i)
=u_i+\Phi(p_i;s_i)
}.
$$

Equivalently,

$$
\boxed{
u_P
=u_i+
\int_{p_P}^{p_i}
\frac{dp}{\rho(p,s_i)c(p,s_i)}
}.
$$

Hence a boundary pressure reduction

$$
p_P<p_i
$$

produces

$$
u_P>u_i.
$$

The linear limit is

$$
\boxed{
\delta u=-\frac{\delta p}{\rho_i c_i}
},
$$

so a rarefaction with `delta p < 0` gives positive outward `delta u > 0`, which
matches the sign required by the locked B2 acoustic contract.

---

## 6. Boundary stagnation state supplied to the immutable B1 law

For each trial `p_P`, compute

$$
h_{0,P}=h_P+\frac{u_P^2}{2},
$$

$$
s_{0,P}=s_P=s_i.
$$

The corresponding stagnation pressure and temperature can be reconstructed by
the same CoolProp `Hmass/Smass` route already used by the production-side B2
Adapter:

$$
(h_{0,P},s_i)
\longrightarrow
(p_{0,P},T_{0,P}).
$$

The accepted B1 component is then evaluated **without changing its law** using
this trial upstream stagnation state, the existing opening fraction,
discharge coefficient and external back pressure.

Denote the resulting accepted B1 mass-transfer function by

$$
\dot m_{B1}
=\mathcal G_{B1}
(h_{0,P},s_i,p_b,f,C_d).
$$

The function includes the existing B1 unchoked/choked classification and the
existing critical-state search.  No B1 coefficient placement is changed.

---

## 7. One scalar compatibility equation

The pipe-side Euler state itself carries mass through the full pipe area at

$$
\dot m_P=\rho_Pu_PA.
$$

A physically compatible coupling requires

$$
\dot m_P=\dot m_{B1}.
$$

Since `rho_P` and `u_P` are already functions of the one trial variable `p_P`,
the complete subsonic boundary solve reduces to

$$
\boxed{
R(p_P)
=ho(p_P,s_i)
\,u_P(p_P;s_i,p_i,u_i)
\,A
-
\mathcal G_{B1}
(h_{0,P}(p_P),s_i,p_b,f,C_d)
=0.
}
$$

Thus the leading A1 formulation is a **one-dimensional nonlinear root problem**
for `p_P`.

No independent momentum formula is prescribed.  Once the root is found, the
pipe-side Euler momentum port follows from that state.

---

## 8. Pipe-side conservative flux after the root

At an admissible root,

$$
\dot m=\rho_Pu_PA.
$$

The pipe-side conservative external flux is then

$$
\boxed{
\mathbf F_P^{A1}
=
\begin{bmatrix}
\rho_Pu_P\\[3pt]
\rho_Pu_P^2+p_P\\[3pt]
\rho_Pu_P h_{0,P}\\[3pt]
0
\end{bmatrix}
}
$$

or, using the common mass rate,

$$
\boxed{
\Pi_P^{A1}
=\dot m u_P+p_PA
}.
$$

The energy flux satisfies

$$
\dot E_P
=\dot m h_{0,P},
$$

which has the same structural form as the accepted B1 energy-transfer law.

The downstream B1 stream diagnostic remains

$$
\Pi_E
=\dot m u_{\mathrm{eff}}+p_dA_o.
$$

The unresolved restriction reaction is retained separately as

$$
\boxed{
R_w=\Pi_E-\Pi_P^{A1}.
}
$$

The equal-and-opposite structural/support load is outside the present fluid-only
Verification claim, but the reaction must remain observable in the ledger.

---

## 9. Exact closed branch

A fully closed element is not solved by the open-boundary nonlinear equation.
It takes an explicit exact wall branch:

```text
if opening_fraction == 0:
    m_dot = 0
    F_P = [0, p_i, 0, 0] exact
```

This preserves the existing locked closed identity and avoids manufacturing an
open-boundary characteristic state for a physical wall.

---

## 10. Exact zero-drop state

For

$$
u_i=0,
\qquad
p_b=p_i,
$$

choose

$$
p_P=p_i.
$$

Then the characteristic relation gives

$$
u_P=0,
$$

and the trial stagnation state equals the static state.  The immutable B1 law
returns exact zero transfer, hence

$$
R(p_i)=0
$$

and

$$
\boxed{
\mathbf F_P=[0,p_i,0,0]^T
}
$$

exactly.

Thus the locked zero-drop wall identity is recoverable without tolerance
relaxation.

---

## 11. Small-pressure-drop asymptotic behaviour

Consider the liquid limiting state with

$$
u_i=0,
$$

$$
\Delta p=p_i-p_b>0,
$$

and let

$$
\delta=p_i-p_P.
$$

For sufficiently small perturbations,

$$
u_P
=\frac{\delta}{\rho_i c_i}
+O(\delta^2).
$$

Therefore the pipe-side mass rate is

$$
\dot m_P
=A\frac{\delta}{c_i}
+O(\delta^2).
$$

Along the inherited isentrope, the stagnation pressure differs from `p_P` only
at second order in the small boundary velocity, so

$$
p_{0,P}
=p_i-\delta+O(\delta^2).
$$

The pressure drop available to the B1 small-drop restriction law is therefore

$$
\varepsilon
=p_{0,P}-p_b
=\Delta p-\delta+O(\delta^2).
$$

B1 gives

$$
\dot m_{B1}
=C_dfA\sqrt{2\rho_i\varepsilon}
+\text{higher-order terms}.
$$

Equating pipe and B1 mass rates gives, at leading order,

$$
\frac{\delta}{c_i}
=C_df\sqrt{2\rho_i(\Delta p-\delta)}.
$$

Squaring,

$$
\boxed{
\Delta p-\delta
=\frac{\delta^2}
{2C_d^2f^2\rho_i c_i^2}
}.
$$

Hence as

$$
\Delta p\rightarrow0^+,
$$

one obtains

$$
\boxed{
\delta=\Delta p+O(\Delta p^2)
}
$$

and therefore

$$
\boxed{
u_P
=\frac{\Delta p}{\rho_i c_i}
+O(\Delta p^2)
}
$$

and

$$
\boxed{
\dot m
=\frac{A\Delta p}{c_i}
+O(\Delta p^2).
}
$$

This is an **acoustic-impedance-limited initial response**, linear in `Delta p`,
rather than the instantaneous `sqrt(Delta p)` quasi-steady orifice response
obtained by applying B1 directly to an unchanged cell-centre state.

The remaining pressure drop across the restriction satisfies

$$
\varepsilon=O(\Delta p^2).
$$

Interpretation:

```text
at t = 0+ for an infinitesimal pressure release,
pipe compressibility/acoustic communication limits how fast mass can arrive at P;
the boundary pressure falls and launches the rarefaction first;
the quasi-steady restriction law and pipe dynamics then evolve together.
```

This asymptotic behaviour has the locked acoustic sign

```text
delta p < 0
 delta u > 0 outward
```

and contains no `Cd > 1/sqrt(2)` reverse-velocity threshold.

---

## 12. Choked B1 compatibility

A restriction may be choked while the upstream pipe-side state remains
subsonic.  In that case the same A1 root equation is used, but
`G_B1` returns the unchanged B1 choked mass-flow plateau evaluated from the
trial upstream stagnation state.

The pipe-side state must satisfy

$$
0\le u_P<c_P
$$

for the present subsonic characteristic count to remain valid.

The next numerical model review must therefore determine, for each locked B2
state family:

```text
root exists
root is unique in the admissible bracket
root remains single phase
rho_P > 0
c_P > 0
0 <= u_P < c_P
B1 outcome is the expected unchoked/choked class
mass residual is zero to the future locked root tolerance
```

If no subsonic root exists, the model must **stop and reclassify the boundary
regime**; it must not silently continue the subsonic formula.

No sonic/supersonic pipe-side rule is approved by this note.

---

## 13. Candidate pressure bracket

For forward discharge from an adjacent single-phase state, a natural
result-independent search interval is conceptually

$$
p_{\min}<p_P\le p_i,
$$

with the lower endpoint chosen only from physically admissible single-phase
states and the B1 forward-flow domain.  The exact bracket and root algorithm
must be locked before numerical results are used for acceptance.

The model review must not choose a bracket after observing which interval makes
the baseline pass.

For the exact zero-drop state, `p_P=p_i` is handled analytically rather than by
numerical root search.

---

## 14. What changes relative to current B2 — concept only

Current B2 v1 does:

```text
adjacent cell state
→ reconstruct stagnation state from cell centre
→ B1 calculates downstream stream
→ downstream stream momentum + pressure terms
→ used directly as pipe external momentum flux
```

A1 would instead do:

```text
adjacent cell state
→ inherit entropy + outgoing acoustic invariant
→ trial p_P
→ solve pipe-side state P
→ reconstruct h0_P,s_P
→ unchanged B1 component law
→ enforce rho_P*u_P*A = m_dot_B1
→ Euler-consistent pipe flux at P

separately:
B1 downstream stream diagnostic E
minus
pipe-side momentum port P
=
restriction reaction R_w
```

Thus A1 changes the **coupling interpretation**, not the accepted B1 discharge
component equation.

---

## 15. Five mandatory checks revisited

```text
C1 closed identity:
  PASS by explicit exact wall branch

C2 zero-drop identity:
  PASS analytically at p_P=p_i, u_P=0

C3 small-drop forward sign:
  PASS analytically in the infinitesimal limit;
  delta u = -delta p/(rho*c) > 0 for rarefaction

C4 choked compatibility:
  B1 law unchanged;
  root existence / subsonic admissibility still requires numerical review

C5 global momentum conservation:
  explicit R_w = Pi_E - Pi_P ledger closes the restriction CV
```

Therefore A1 is sufficiently specified to justify a **diagnostic root-existence
study**, but not yet a Contract revision.

---

## 16. Next controlled action

The next increment remains model-review-only and should execute no finite-pipe
acceptance test.  It should independently evaluate the A1 scalar residual over
the three locked baseline state families:

```text
LIQUID_SMALL_DROP
GAS_UNCHOKED
GAS_CHOKED
```

Required evidence before Contract drafting:

```text
residual vs p_P
root count
selected root only if unique
rho_P, u_P, p_P, T_P, h0_P, Mach_P
B1 formal outcome at root
m_dot_pipe vs m_dot_B1
Pi_P
Pi_E
R_w
closed exact identity
zero-drop exact identity
small-drop sign check
single-phase admissibility
```

The diagnostic must not alter any B1/B2 tolerance or formal state.

---

## 17. Formal state remains unchanged

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

# Stage 7 U3 B2 — momentum control-volume model review

## 1. Status and claim boundary

```text
review type:                       MODEL_REVIEW_ONLY
source main:                       aa108961762c9ae70ee9940405024eb5188064b8
B2 contract modification:          none
B1 modification:                   none
Adapter modification:              none
solver modification:               none
tolerance modification:            none
formal finite-pipe promotion:      none
physical validation:               false
design use:                        false
production activation:             false
```

This note re-derives the momentum bookkeeping around the U3 B2 discharge boundary after the locked finite-pipe baseline exposed a deterministic reverse-velocity Guard in B2-10A and B2-10B. It does not select a replacement boundary law and does not change the locked Contract.

Observed diagnostic evidence used here:

```text
baseline preflight run:             31440560939
reverse-guard diagnostic run:       31440999798
family-balance diagnostic V2 run:   31441481104
family-balance artifact:            9083010542
artifact ZIP SHA256:                12846078bd29a199ceb223e12f369073d446d324e4e8f77243cf20f766aea97c
```

---

## 2. Separate the physical locations

The present review distinguishes three locations which must not be silently identified with one another.

```text
upstream FVM pipe                  restriction / nozzle                 discharge stream

--------------------- P | R -------------------------------- E -------------------->
                         ^                                           ^
                         upstream-side port                          downstream/jet section
```

Definitions:

```text
P: upstream FVM-side interface plane
R: unresolved restriction / orifice / nozzle region
E: downstream discharge-stream section
A_pipe: full pipe area
A_open: open/effective geometric area used by B1/B2
A_closed = A_pipe - A_open
p_i: adjacent FVM-cell static pressure
p_d: B1 retained discharge-state pressure
u_i: adjacent FVM-cell velocity
u_eff: B1 effective stream velocity
m_dot: positive outward B1 mass transfer
R_w: net unresolved axial force exerted by restriction walls/geometry on the fluid,
     positive in the downstream direction
```

The critical question is whether the B1 downstream stream transfer can be used directly as the Euler momentum flux at P.

---

## 3. CV-A — final FVM cell

For the one-dimensional Euler momentum equation, the integrated momentum flux through a uniform cross-section is

$$
\Pi = (\rho u^2 + p)A.
$$

For the final FVM cell,

$$
\frac{dP_{\mathrm{cell}}}{dt}
= -\left(\Pi_R-\Pi_L\right)
$$

when there is no separate momentum source inside that cell.

At the initial locked baseline state, the pipe is uniform and stationary, so

$$
\Pi_L \simeq p_i A_{\mathrm{pipe}}.
$$

The current B2 direct mapping imposes

$$
\Pi_R^{\mathrm{B2}}
= \dot m u_{\mathrm{eff}}
+ p_d A_{\mathrm{open}}
+ p_i A_{\mathrm{closed}}.
$$

Using

$$
A_{\mathrm{pipe}}=A_{\mathrm{open}}+A_{\mathrm{closed}},
$$

the initial flux difference becomes

$$
\boxed{
\Pi_R^{\mathrm{B2}}-\Pi_L
= \dot m u_{\mathrm{eff}}
- (p_i-p_d)A_{\mathrm{open}}
}
$$

Therefore the initial momentum sign is controlled by a competition between:

```text
outward B1 stream momentum        m_dot*u_eff
versus
open-area pressure-drop force     (p_i-p_d)*A_open
```

If the stream-momentum term is larger, the Euler update makes the initially stationary final cell acquire negative momentum.

This is exactly what the diagnostic run measured.

---

## 4. Small-pressure-drop limit exposes a structural sign criterion

B0/B1 define the liquid small-drop limit as

$$
\dot m
= C_d A_{\mathrm{open}}\sqrt{2\rho\Delta p},
$$

with

$$
u_{\mathrm{eff}}
= C_d\sqrt{\frac{2\Delta p}{\rho}},
$$

where

$$
\Delta p=p_i-p_d>0.
$$

Hence

$$
\dot m u_{\mathrm{eff}}
= 2C_d^2\Delta p A_{\mathrm{open}}.
$$

Substituting into the B2 initial flux difference gives

$$
\boxed{
\Pi_R^{\mathrm{B2}}-\Pi_L
= (2C_d^2-1)\Delta p A_{\mathrm{open}}
}
$$

For any finite forward opening and pressure drop, the sign changes at

$$
C_d=\frac{1}{\sqrt{2}}\approx0.7071.
$$

The locked value is

$$
C_d=0.8,
$$

so

$$
2C_d^2-1=0.28>0.
$$

Thus, under the current direct mapping, the B2-10A initial momentum derivative is negative by construction. Reducing CFL changes the magnitude per step but not this sign. Reducing the opening fraction scales the magnitude toward zero but also does not change the sign for any nonzero opening.

This is a structural model result, not a time-step accident.

---

## 5. Diagnostic values

The V2 diagnostic reproduced the first-step momentum update exactly.

### B2-10A — LIQUID_SMALL_DROP

```text
left internal momentum flux:              5,000,000.000037119 Pa
right mapped momentum flux:               5,006,995.789536312 Pa
right-left flux difference:                   6,995.78949919343 Pa
pressure-drop force on open area:             2.50000000185594 N
B1 advective stream momentum rate:             3.1995789517752464 N
stream minus pressure-drop force:               +0.6995789499193066 N
first-step predicted rho*u:                    -1.4991399237517937
first-step actual rho*u:                       -1.4991399237517937
prediction residual:                            0.0
first-step adjacent velocity:                  -0.0017155240937878258 m/s
```

### B2-10B — GAS_UNCHOKED

```text
left internal momentum flux:              1,000,000.0000000002 Pa
right mapped momentum flux:               1,017,062.9332952544 Pa
right-left flux difference:                  17,062.93329525413 Pa
pressure-drop force on open area:            10.000000000000012 N
B1 advective stream momentum rate:            11.706293329525419 N
stream minus pressure-drop force:              +1.7062933295254066 N
first-step predicted rho*u:                    -6.277643612010098
first-step actual rho*u:                       -6.277643612010098
prediction residual:                            0.0
first-step adjacent velocity:                  -0.37155239709178073 m/s
```

### B2-10C — GAS_CHOKED

```text
left internal momentum flux:              1,000,000.0000000002 Pa
right mapped momentum flux:                 999,470.0084519719 Pa
right-left flux difference:                    -529.9915480283089 Pa
stream minus pressure-drop force:               -0.05299915480283701 N
first-step adjacent velocity:                   +0.011586861378342443 m/s
16-step short baseline:                         SUCCESS_FINITE_PIPE_SINGLE_PHASE_COUPLING
```

B2-10C shows that the solver and budget machinery can complete a finite-pipe run when the imposed momentum balance has the outward sign. It does not by itself prove that the present momentum closure is physically correct.

---

## 6. CV-B — restriction / nozzle / orifice region

Now place a separate steady control volume around the unresolved restriction region R, with upstream section P and downstream section E.

With downstream-positive sign convention, the one-dimensional momentum balance is

$$
p_P A_P - p_E A_E + R_w
= \dot m u_E - \dot m u_P.
$$

Rearranging,

$$
\boxed{
\dot m u_E + p_E A_E
= \dot m u_P + p_P A_P + R_w
}
$$

or, defining momentum-flux ports,

$$
\boxed{
\Pi_E=\Pi_P+R_w.
}
$$

Therefore the downstream stream-plus-pressure flux and the upstream Euler flux are generally not equal. Their difference is the unresolved axial force exerted by restriction geometry/walls on the fluid.

For a converging nozzle, sharp-edged restriction, valve, or vena-contracta region, this axial force need not be zero. The detailed pressure distribution and wall geometry determine it.

The present B1 component does not provide an independent value of $R_w$ or an upstream-side momentum port $\Pi_P$.

---

## 7. CV-C — pipe plus restriction

If the pipe fluid and the restriction fluid region are combined into one larger control volume, the artificial internal interface P disappears from the global momentum balance.

The global balance then contains:

```text
left pipe boundary momentum flux
external downstream discharge flux at E
forces exerted by the restriction/pipe walls on the modeled fluid
```

The downstream quantity

$$
\dot m u_E+p_EA_E
$$

is appropriate as an external outlet term only when the associated wall/restriction force is also represented consistently in the same control-volume bookkeeping.

If only the upstream pipe is modeled, then the pipe boundary needs the upstream-side momentum port $\Pi_P$, not automatically the downstream quantity $\Pi_E$.

Using

$$
\Pi_P=\Pi_E
$$

implicitly assumes

$$
R_w=0,
$$

which is an additional physical closure. The finite-pipe diagnostic shows that this closure is not benign for B2-10A/B.

---

## 8. What B0/B1 actually establish about Cd

B0 defines

```text
mass_flow_rate = Cd*Aeff*sqrt(2*rho*delta_p)
exit_velocity  = m_dot/(rho*Aeff)
momentum_stream_transfer = m_dot*u_exit
```

and explicitly labels this momentum term as `advective_stream_transfer_only`, with static pressure force deferred to later FVM mapping.

B1 retains the same conceptual split and defines

```text
effective_stream_velocity = Cd*thermodynamic_ideal_velocity
momentum_stream_transfer  = m_dot*effective_stream_velocity
static_pressure_force      = not_included; deferred_to_future_FVM_face_mapping
```

This is internally well-defined as a lumped component transfer.

However, classical orifice treatment distinguishes effects such as jet contraction and velocity loss; a discharge coefficient can combine multiple corrections rather than uniquely identifying one physical downstream area and one physical stream velocity. Therefore a calibrated/lumped `Cd` and `m_dot` do not by themselves determine the upstream Euler momentum port of a restriction.

This does not invalidate the accepted B0/B1 component benchmarks. It limits what can be inferred from their stream-transfer output when constructing B2's pipe-side momentum closure.

---

## 9. Mass and energy are not showing the same ambiguity

### Mass

The pipe-side mass removal

$$
\dot m
$$

is a scalar transfer across the component and does not require a wall-reaction closure. No analogous sign inconsistency has been identified in the mass ledger.

### Energy

For an adiabatic flow port, total-energy transfer naturally has the form

$$
\dot E=\dot m h_t.
$$

B1 uses

$$
\dot E=\dot m h_0.
$$

That is structurally suitable as a lumped energy port. The B2 specification already notes that the B1 tuple cannot in general be represented by one Euler primitive ghost state because the retained $C_d$ placement and $\dot m h_0$ transfer do not define one unique local state.

The present blocker is therefore localized primarily to **momentum closure at the pipe/component interface**, not to a demonstrated mass- or energy-conservation failure.

---

## 10. Model-review conclusion

The review currently supports the following classification.

```text
FVM conservative update sign error:          NOT INDICATED
CFL-only failure:                             NOT INDICATED
reverse-flow Guard defect:                    NOT INDICATED
B0/B1 component implementation defect:        NOT ESTABLISHED
mass-transfer closure defect:                 NOT ESTABLISHED
energy-transfer closure defect:               NOT ESTABLISHED
B1 stream momentum = pipe Euler face flux:    NOT JUSTIFIED
restriction axial reaction closure:           MISSING / UNRESOLVED
B2 direct momentum mapping:                   REQUIRES CONTRACT-LEVEL REVIEW
```

The current B2 Contract also expects the LIQUID_SMALL_DROP finite pipe to produce a direct rarefaction with positive outward velocity. For the locked $C_d=0.8$, the current direct momentum mapping instead gives negative initial velocity analytically. The expected wave sign and the current momentum closure are therefore internally inconsistent for the small-drop limit.

---

## 11. Candidate next model paths — no selection yet

The next Contract review should compare, without result-driven tolerance changes, at least these physically distinct formulations:

1. **Upstream momentum-port formulation**
   - B1 supplies mass and energy transfers.
   - A separate constitutive closure supplies the pipe-side momentum port $\Pi_P$.
   - Restriction reaction is $R_w=\Pi_E-\Pi_P$.

2. **Localized restriction source / interface formulation**
   - Keep distinct upstream and downstream momentum fluxes.
   - Represent their jump as the restriction/wall momentum source.

3. **Explicit short nozzle/orifice control-volume formulation**
   - Introduce a small resolved or lumped region R so the acceleration and reaction are not collapsed onto one FVM face.

4. **Coefficient-decomposition formulation**
   - If physically justified and supported by the intended component geometry, separate contraction/velocity/loss effects rather than treating one `Cd` as sufficient to identify a local Euler face state.

No option is approved by this note.

---

## 12. External physical references used for this review

- NASA Glenn Research Center, *General Thrust Equation*: momentum-flow and pressure-area terms must be kept in one consistent control-volume balance.
- NASA Glenn Research Center, *Euler Equations* / *Conservation of Momentum*: pressure and advective transport form the momentum balance of inviscid flow.
- U.S. Bureau of Reclamation, *Water Measurement Manual*, orifice sections: discharge coefficients can include contraction and velocity-loss effects; jet contraction means geometric opening area and contracted stream area need not be identical.

These references support the control-volume structure only. They do not by themselves select the project-specific replacement B2 boundary law.

# Stage 7 U3 B2 A1 finite-compression Increment 5 numerical tolerances

## Status

`MODEL_REVIEW_ONLY / FIXED_BEFORE_EXECUTION_RESULT`

This note fixes numerical closure tolerances omitted from the initial Increment 5 model-selection specification. It does not change the diagnostic pressure nodes, physical equations, B1 behavior, approved Weak Compression scope, or formal project states.

## Hugoniot closure

At every completed Hugoniot density root, require both equivalent Rankine-Hugoniot energy forms:

```text
H_e = e_P - e_i + 0.5 (p_P + p_i) (v_P - v_i)

H_h = h_P - h_i - 0.5 (p_P - p_i) (v_i + v_P)
```

with fixed absolute tolerances:

```text
abs(H_e) <= 1.0e-6 J/kg
abs(H_h) <= 1.0e-6 J/kg
abs(H_e - H_h) <= 1.0e-8 J/kg
```

The two forms must be evaluated from the same CoolProp state.

## Density root

After exactly 64 Hugoniot density bisection iterations, require:

```text
rho_upper > rho_lower > rho_i
relative density bracket width
= (rho_upper - rho_lower) / rho_i
<= 1.0e-12
```

The selected density root is the bracket endpoint with the smaller absolute `H_e` residual. No residual sign or density tolerance may be relaxed after observing the result.

## Compatibility root

The existing B1 compatibility root retains:

```text
absolute mass residual tolerance:
1.0e-8 kg/s

maximum requested-chi bisection iterations:
48
```

The local residual slope is computed from the final successful bracket endpoints in physical pressure coordinates. It must be strictly negative for a supported Hugoniot root.

## Entropy

The pre-fixed entropy diagnostic bound remains:

```text
s_P - s_i >= -1.0e-7 J/(kg K)
```

This is a numerical fail-closed bound, not a claim of resolved experimental entropy production.

## Formal-state boundary

All project approval states remain false regardless of result.
